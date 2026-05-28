"""
pipeline.py — Pipeline Data Marketing Prêt-à-Porter RFM
========================================================
Étapes :
  1. Connexion à MySQL
  2. Chargement des données avec Pandas
  3. Calcul RFM (Récence / Fréquence / Montant)
  4. Enrichissement via l'API Geo du gouvernement français
     (https://geo.api.gouv.fr) → région de chaque client
  5. Écriture des segments dans la table `segments_rfm`

Exécution :  python pipeline.py
"""

import sys
import requests
import pandas as pd
import numpy as np
import mysql.connector
from datetime import datetime, date
from config import DB_CONFIG


# ═══════════════════════════════════════════════════════════════════════════════
# 1. CONNEXION À LA BASE DE DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

def get_connection():
    """Retourne une connexion active à MySQL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print(f"✅ Connecté à MySQL : {DB_CONFIG['database']}@{DB_CONFIG['host']}")
        return conn
    except mysql.connector.Error as err:
        print(f"❌ Erreur de connexion : {err}")
        sys.exit(1)


def load_dataframe(conn, query: str) -> pd.DataFrame:
    """Charge une requête SQL dans un DataFrame Pandas."""
    return pd.read_sql(query, conn)


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CHARGEMENT DES DONNÉES
# ═══════════════════════════════════════════════════════════════════════════════

QUERY_COMMANDES = """
SELECT
    co.commande_id,
    co.client_id,
    co.date_commande,
    co.statut,
    cp.produit_id,
    cp.quantite,
    cp.prix_unitaire,
    (cp.quantite * cp.prix_unitaire) AS montant_ligne,
    c.nom,
    c.prenom,
    c.email,
    c.genre,
    c.ville
FROM commandes co
JOIN commandes_produits cp ON cp.commande_id = co.commande_id
JOIN clients c             ON c.client_id   = co.client_id
WHERE co.statut = 'livree'
"""


def load_data(conn) -> pd.DataFrame:
    """Charge toutes les commandes livrées avec leurs lignes."""
    df = load_dataframe(conn, QUERY_COMMANDES)
    df["date_commande"] = pd.to_datetime(df["date_commande"])
    print(f"📦 {len(df)} lignes de commandes chargées pour {df['client_id'].nunique()} clients")
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 3. ALGORITHME RFM
# ═══════════════════════════════════════════════════════════════════════════════

DATE_REFERENCE = pd.Timestamp(datetime(2025, 5, 1))   # date de référence fixe


def compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcule les métriques RFM par client :
      - Récence   : jours depuis la dernière commande
      - Fréquence : nombre de commandes distinctes
      - Montant   : chiffre d'affaires total

    Attribue un score 1-5 par quintile pour chaque métrique,
    puis détermine le segment marketing.

    Paramètres
    ----------
    df : DataFrame avec colonnes client_id, date_commande, commande_id, montant_ligne

    Retourne
    --------
    DataFrame rfm enrichi avec scores et segment
    """
    # ── Agrégation par client ────────────────────────────────
    rfm = (df.groupby("client_id")
             .agg(
                 nom          = ("nom",          "first"),
                 prenom       = ("prenom",       "first"),
                 genre        = ("genre",        "first"),
                 ville        = ("ville",        "first"),
                 derniere_cmd = ("date_commande", "max"),
                 frequence    = ("commande_id",   "nunique"),
                 montant      = ("montant_ligne", "sum"),
             )
             .reset_index())

    rfm["montant"] = rfm["montant"].round(2)

    # ── Récence en jours ────────────────────────────────────
    rfm["recence"] = (DATE_REFERENCE - rfm["derniere_cmd"]).dt.days

    # ── Scores 1-5 par quintile ──────────────────────────────
    # Récence  : plus c'est faible (récent), meilleur le score → ordre inversé
    rfm["score_r"] = pd.qcut(rfm["recence"],    q=5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["score_f"] = pd.qcut(rfm["frequence"].rank(method="first"), q=5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["score_m"] = pd.qcut(rfm["montant"].rank(method="first"),   q=5, labels=[1, 2, 3, 4, 5]).astype(int)

    # ── Score global concaténé ───────────────────────────────
    rfm["score_rfm"] = (rfm["score_r"].astype(str) +
                        rfm["score_f"].astype(str) +
                        rfm["score_m"].astype(str))

    # ── Attribution du segment ────────────────────────────────
    rfm["segment"] = rfm.apply(assign_segment, axis=1)

    print(f"\n🏷️  Distribution des segments RFM :")
    print(rfm["segment"].value_counts().to_string())

    return rfm


def assign_segment(row) -> str:
    """
    Attribue un label de segment à partir des scores R, F, M.

    Paramètres
    ----------
    row : ligne du DataFrame rfm avec score_r, score_f, score_m

    Retourne
    --------
    Nom du segment (str)
    """
    r, f, m = row["score_r"], row["score_f"], row["score_m"]

    if r >= 4 and f >= 4 and m >= 4:
        return "Champion"
    elif r >= 3 and f >= 3:
        return "Client Fidèle"
    elif r >= 3 and f <= 2:
        return "Loyaliste Potentiel"
    elif r <= 2 and f >= 3:
        return "A Risque"
    elif r == 1 and f == 1:
        return "Perdu"
    else:
        return "Nouveau Client"


# ═══════════════════════════════════════════════════════════════════════════════
# 4. ENRICHISSEMENT VIA API — Geo API du gouvernement français
#    https://geo.api.gouv.fr/communes?nom=<ville>&fields=region
# ═══════════════════════════════════════════════════════════════════════════════

GEO_API_URL = "https://geo.api.gouv.fr/communes"
_cache_regions: dict = {}   # cache pour éviter les appels redondants


def get_region_for_city(ville: str) -> str:
    """
    Appelle l'API Geo gouv.fr pour obtenir la région d'une ville française.

    Paramètres
    ----------
    ville : nom de la commune (str)

    Retourne
    --------
    Nom de la région (str) ou 'Inconnue' en cas d'erreur
    """
    if ville in _cache_regions:
        return _cache_regions[ville]

    try:
        resp = requests.get(
            GEO_API_URL,
            params={"nom": ville, "fields": "nom,region", "format": "json", "limit": 1},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        region = data[0]["region"]["nom"] if data else "Inconnue"
    except Exception:
        region = "Inconnue"

    _cache_regions[ville] = region
    return region


def enrich_with_regions(rfm: pd.DataFrame) -> pd.DataFrame:
    """
    Enrichit le DataFrame RFM avec la région de chaque client via l'API.

    Paramètres
    ----------
    rfm : DataFrame avec colonne 'ville'

    Retourne
    --------
    DataFrame avec colonne 'region' ajoutée
    """
    villes_uniques = rfm["ville"].unique()
    print(f"\n🌍 Enrichissement API Geo pour {len(villes_uniques)} villes…")

    for ville in villes_uniques:
        region = get_region_for_city(ville)
        print(f"   {ville:20s} → {region}")

    rfm["region"] = rfm["ville"].map(_cache_regions)
    return rfm


# ═══════════════════════════════════════════════════════════════════════════════
# 5. ÉCRITURE DANS LA TABLE segments_rfm
# ═══════════════════════════════════════════════════════════════════════════════

def write_segments(conn, rfm: pd.DataFrame):
    """
    Vide la table segments_rfm puis insère tous les segments calculés.

    Paramètres
    ----------
    conn : connexion MySQL active
    rfm  : DataFrame rfm enrichi
    """
    cursor = conn.cursor()

    # Nettoyage préalable
    cursor.execute("DELETE FROM segments_rfm")
    conn.commit()
    print("\n🗑️  Table segments_rfm vidée")

    insert_sql = """
        INSERT INTO segments_rfm
            (client_id, recence, frequence, montant,
             score_r, score_f, score_m, score_rfm, segment, region)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    rows = [
        (
            int(row["client_id"]),
            int(row["recence"]),
            int(row["frequence"]),
            float(row["montant"]),
            int(row["score_r"]),
            int(row["score_f"]),
            int(row["score_m"]),
            str(row["score_rfm"]),
            str(row["segment"]),
            str(row["region"]),
        )
        for _, row in rfm.iterrows()
    ]

    cursor.executemany(insert_sql, rows)
    conn.commit()
    cursor.close()
    print(f"✅ {len(rows)} segments insérés dans segments_rfm")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  PIPELINE RFM — Prêt-à-Porter")
    print("=" * 60)

    conn = get_connection()

    # Étape 1 : chargement
    df = load_data(conn)

    # Étape 2 : calcul RFM
    rfm = compute_rfm(df)

    # Étape 3 : enrichissement API
    rfm = enrich_with_regions(rfm)

    # Étape 4 : sauvegarde MySQL
    write_segments(conn, rfm)

    conn.close()
    print("\n🎉 Pipeline terminé avec succès !")

    # Aperçu final
    print("\nAperçu des segments calculés :")
    print(rfm[["prenom", "nom", "ville", "region",
               "recence", "frequence", "montant",
               "score_rfm", "segment"]].to_string(index=False))


if __name__ == "__main__":
    main()
