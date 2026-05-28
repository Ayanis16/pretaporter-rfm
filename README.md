# 👗 Prêt-à-Porter — Analyse RFM & Dashboard Marketing

> **Projet final — Algo & Bases de Données | MSc2 Manager Data Marketing | INSEEC 2026**

---

## 📌 Problématique métier

Une enseigne de prêt-à-porter homme & femme souhaite **identifier et cibler ses segments clients** pour optimiser ses campagnes marketing.  
L'objectif : calculer automatiquement le score **RFM (Récence · Fréquence · Montant)** de chaque client, les segmenter en 5 profils actionnables, et visualiser les performances dans un dashboard interactif.

---

## 🗂️ Structure du projet

```
pretaporter-rfm/
├── sql/
│   ├── schema.sql        ← Création des tables + insertion des données (200 cmds, 384 lignes)
│   └── queries.sql       ← Requêtes analytiques, VIEW, FUNCTION, PROCÉDURE
├── python/
│   ├── config.py         ← Connexion MySQL via .env
│   ├── pipeline.py       ← Pipeline RFM : Pandas + API + écriture MySQL
│   ├── dashboard.py      ← Dashboard Plotly Dash interactif
│   └── requirements.txt
├── assets/
│   └── schema.png        ← Capture du schéma dbdiagram.io
├── .env.example          ← Template de configuration (à renommer en .env)
├── .gitignore
└── README.md
```

---

## 🗄️ Modélisation de la base de données

### Schéma

![Schéma de la base](assets/schema.png)

> **Code dbdiagram.io** — coller sur [dbdiagram.io](https://dbdiagram.io) pour visualiser :

```
Table clients {
  client_id       int [pk, increment]
  nom             varchar(100) [not null]
  prenom          varchar(100) [not null]
  email           varchar(255) [unique, not null]
  genre           enum('H','F') [not null]
  ville           varchar(100) [not null]
  date_inscription date [not null]
}

Table categories {
  categorie_id  int [pk, increment]
  nom           varchar(100) [unique, not null]
  description   text
}

Table produits {
  produit_id    int [pk, increment]
  nom           varchar(200) [not null]
  categorie_id  int [ref: > categories.categorie_id]
  genre         enum('homme','femme','mixte') [not null]
  prix          decimal(10,2) [not null]
  stock         int [not null]
}

Table commandes {
  commande_id   int [pk, increment]
  client_id     int [ref: > clients.client_id]
  date_commande datetime [not null]
  statut        enum('livree','en_cours','annulee') [not null]
}

Table commandes_produits {
  commande_id   int [ref: > commandes.commande_id]
  produit_id    int [ref: > produits.produit_id]
  quantite      int [not null]
  prix_unitaire decimal(10,2) [not null]
  indexes {
    (commande_id, produit_id) [pk]
  }
}

Table segments_rfm {
  segment_id  int [pk, increment]
  client_id   int [unique, ref: > clients.client_id]
  recence     int [not null]
  frequence   int [not null]
  montant     decimal(10,2) [not null]
  score_r     int [not null]
  score_f     int [not null]
  score_m     int [not null]
  score_rfm   varchar(10) [not null]
  segment     varchar(50) [not null]
  region      varchar(100)
  date_calcul datetime
}
```

### Choix de modélisation

| Décision | Justification |
|---|---|
| Table `commandes_produits` | Relation **many-to-many** entre commandes et produits — un client peut commander plusieurs produits, un produit peut figurer dans plusieurs commandes |
| Champ `genre` sur `clients` ET `produits` | Permet de filtrer les ventes par genre client ET par ligne de produits (homme/femme/mixte) |
| Table `segments_rfm` séparée | Les résultats Python sont isolés des données transactionnelles, facilitant la recalcul et le versioning |
| `email UNIQUE` | Contrainte métier : un email = un compte client |

---

## 🔧 Lancement du projet

### Prérequis
- MySQL 8+ en local
- Python 3.10+

### 1. Configuration
```bash
cp .env.example .env
# Éditez .env avec vos identifiants MySQL
```

### 2. Base de données
```bash
mysql -u root -p < sql/schema.sql
mysql -u root -p pretaporter_db < sql/queries.sql
```

### 3. Dépendances Python
```bash
cd python
pip install -r requirements.txt
```

### 4. Pipeline RFM
```bash
python pipeline.py
```
Ce script :
- Se connecte à MySQL
- Calcule les scores RFM avec Pandas
- Appelle l'**API Geo gouv.fr** pour enrichir chaque client avec sa région
- Insère les résultats dans la table `segments_rfm`

### 5. Dashboard
```bash
python dashboard.py
# → http://127.0.0.1:8050
```

---

## 🧮 Algorithme RFM

| Métrique | Définition | Score |
|---|---|---|
| **R**écence | Jours depuis la dernière commande livrée | 5 = très récent |
| **F**réquence | Nombre de commandes livrées | 5 = très fréquent |
| **M**ontant | CA total généré par le client | 5 = gros acheteur |

Les scores sont attribués par **quintiles** (`pd.qcut`) pour une distribution équitable.

### Segments

| Segment | Critère |
|---|---|
| 🏆 Champion | R≥4, F≥4, M≥4 |
| 💛 Client Fidèle | R≥3, F≥3 |
| 🌱 Loyaliste Potentiel | R≥3, F≤2 |
| ⚠️ A Risque | R≤2, F≥3 |
| 👋 Nouveau Client | autres |
| 💤 Perdu | R=1, F=1 |

---

## 🌐 API externe utilisée

**Geo API — gouvernement français**  
`https://geo.api.gouv.fr/communes?nom={ville}&fields=region`

- Gratuite, sans clé API
- Retourne la région administrative pour chaque ville client
- Utilisée pour enrichir la table `segments_rfm` avec la colonne `region`

---

## 📊 Dashboard

Accessible sur `http://127.0.0.1:8050` après lancement de `dashboard.py`.

**KPIs** : Chiffre d'affaires total · Clients actifs · Nombre de commandes · Panier moyen  
**Graphiques** : Donut segments RFM · CA mensuel · Top 10 produits · CA par région  
**Filtres** : Segment RFM · Genre produit · Catégorie

---

## ✅ Checklist technique

### Partie 1 — Base de données
- [x] Schéma dbdiagram.io (6 tables avec relations)
- [x] Relation many-to-many (`commandes` ↔ `produits` via `commandes_produits`)
- [x] Fichier SQL complet (CREATE + INSERT)
- [x] Contraintes FOREIGN KEY (4 tables)
- [x] Contraintes NOT NULL et UNIQUE (`email`)
- [x] 6 requêtes SELECT avec WHERE, GROUP BY, HAVING, ORDER BY, LIMIT
- [x] Jointure sur 5 tables (clients + commandes + commandes_produits + produits + categories)
- [x] Sous-requête (clients > moyenne) + CTE (CA mensuel avec LAG)
- [x] Vue `vue_stats_clients`
- [x] Fonction `fn_rfm_label` + Procédure `sp_rapport_categories`

### Partie 2 — Pipeline Python
- [x] Connexion MySQL (`mysql-connector-python` + `.env`)
- [x] Manipulation Pandas (groupby, qcut, merge...)
- [x] Appel API externe (Geo gouv.fr)
- [x] Algorithme RFM avec scoring par quintiles
- [x] Écriture dans `segments_rfm`
- [x] Code commenté avec fonctions paramétrées

### Partie 3 — Dashboard
- [x] Dashboard Plotly Dash fonctionnel
- [x] 4 KPIs (CA, clients, commandes, panier moyen)
- [x] 4 graphiques (donut, barres, horizontal, régions)
- [x] 3 filtres (segment, genre, catégorie)
- [x] Callback principal qui met à jour tout le dashboard

### Partie 4 — Documentation
- [x] README complet
- [x] Schéma dbdiagram
- [x] Présentation prête

---

*Projet réalisé dans le cadre du MSc2 Manager Data Marketing — INSEEC 2026*
