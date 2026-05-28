"""
dashboard.py — Dashboard interactif Prêt-à-Porter RFM
"""

import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import DB_CONFIG

def load_all_data():
    conn = mysql.connector.connect(**DB_CONFIG)
    df_cmds = pd.read_sql("""
        SELECT co.commande_id, co.client_id, co.date_commande,
            cp.produit_id, cp.quantite, cp.prix_unitaire,
            (cp.quantite * cp.prix_unitaire) AS montant_ligne,
            p.nom AS produit, p.genre AS genre_produit,
            cat.nom AS categorie, c.genre AS genre_client, c.ville
        FROM commandes co
        JOIN commandes_produits cp ON cp.commande_id = co.commande_id
        JOIN produits p ON p.produit_id = cp.produit_id
        JOIN categories cat ON cat.categorie_id = p.categorie_id
        JOIN clients c ON c.client_id = co.client_id
        WHERE co.statut = 'livree'
    """, conn)
    df_cmds["date_commande"] = pd.to_datetime(df_cmds["date_commande"])
    df_cmds["mois"] = df_cmds["date_commande"].dt.to_period("M").astype(str)

    df_rfm = pd.read_sql("""
        SELECT s.client_id, s.recence, s.frequence, s.montant,
            s.score_r, s.score_f, s.score_m, s.score_rfm,
            s.segment, s.region,
            CONCAT(c.prenom, ' ', c.nom) AS client,
            c.genre, c.ville
        FROM segments_rfm s
        JOIN clients c ON c.client_id = s.client_id
    """, conn)
    conn.close()
    return df_cmds, df_rfm

try:
    df_cmds, df_rfm = load_all_data()
    DATA_LOADED = True
except Exception as e:
    print(f"⚠️ Erreur : {e}")
    DATA_LOADED = False
    df_cmds = pd.DataFrame()
    df_rfm = pd.DataFrame()

SEGMENTS = ["Tous"] + (sorted(df_rfm["segment"].unique().tolist()) if DATA_LOADED else [])
GENRES = ["Tous", "homme", "femme", "mixte"]
CATEGORIES = ["Toutes"] + (sorted(df_cmds["categorie"].unique().tolist()) if DATA_LOADED else [])

PALETTE_SEGMENTS = {
    "Champion": "#1a1a2e",
    "Client Fidèle": "#16213e",
    "Loyaliste Potentiel": "#0f3460",
    "A Risque": "#e94560",
    "Nouveau Client": "#533483",
    "Perdu": "#adb5bd",
}

app = Dash(__name__, title="Prêt-à-Porter — Dashboard RFM")

app.layout = html.Div(style={"fontFamily": "Inter, sans-serif", "backgroundColor": "#f8f9fa", "minHeight": "100vh"}, children=[

    html.Div(style={"background": "linear-gradient(135deg,#1a1a2e,#0f3460)", "padding": "24px 40px", "color": "white"}, children=[
        html.H1("👗 Prêt-à-Porter — Analyse RFM", style={"margin": "0", "fontSize": "26px", "fontWeight": "700"}),
        html.P("Segmentation clients & performance commerciale", style={"margin": "4px 0 0", "opacity": "0.75", "fontSize": "14px"}),
    ]),

    html.Div(style={"display": "flex", "gap": "20px", "padding": "20px 40px", "backgroundColor": "white", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "flexWrap": "wrap"}, children=[
        html.Div([
            html.Label("Segment RFM", style={"fontSize": "12px", "fontWeight": "600", "color": "#6c757d", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(id="filter-segment", options=[{"label": s, "value": s} for s in SEGMENTS], value="Tous", clearable=False, style={"width": "220px"}),
        ]),
        html.Div([
            html.Label("Genre produit", style={"fontSize": "12px", "fontWeight": "600", "color": "#6c757d", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(id="filter-genre", options=[{"label": g.capitalize(), "value": g} for g in GENRES], value="Tous", clearable=False, style={"width": "180px"}),
        ]),
        html.Div([
            html.Label("Catégorie", style={"fontSize": "12px", "fontWeight": "600", "color": "#6c757d", "marginBottom": "6px", "display": "block"}),
            dcc.Dropdown(id="filter-categorie", options=[{"label": c, "value": c} for c in CATEGORIES], value="Toutes", clearable=False, style={"width": "220px"}),
        ]),
        html.Div([
            html.Label("🔍 Rechercher un client", style={"fontSize": "12px", "fontWeight": "600", "color": "#6c757d", "marginBottom": "6px", "display": "block"}),
            dcc.Input(id="filter-client", type="text", placeholder="Ex: Julie Durand...", debounce=True,
                      style={"width": "220px", "padding": "8px 12px", "borderRadius": "6px", "border": "1px solid #dee2e6", "fontSize": "14px"}),
        ]),
    ]),

    html.Div(id="fiche-client", style={"padding": "10px 40px"}),
    html.Div(id="kpi-cards", style={"display": "flex", "gap": "20px", "padding": "20px 40px", "flexWrap": "wrap"}),

    html.Div(style={"display": "flex", "gap": "20px", "padding": "0 40px 20px", "flexWrap": "wrap"}, children=[
        html.Div(dcc.Graph(id="graph-segments"), style={"flex": "1", "minWidth": "340px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "padding": "16px"}),
        html.Div(dcc.Graph(id="graph-ca-mensuel"), style={"flex": "2", "minWidth": "400px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "padding": "16px"}),
    ]),

    html.Div(style={"display": "flex", "gap": "20px", "padding": "0 40px 40px", "flexWrap": "wrap"}, children=[
        html.Div(dcc.Graph(id="graph-top-produits"), style={"flex": "2", "minWidth": "400px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "padding": "16px"}),
        html.Div(dcc.Graph(id="graph-regions"), style={"flex": "1", "minWidth": "340px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "padding": "16px"}),
    ]),
])


@app.callback(
    Output("fiche-client", "children"),
    Input("filter-client", "value"),
)
def search_client(nom_recherche):
    if not nom_recherche or not DATA_LOADED:
        return ""
    mask = df_rfm["client"].str.contains(nom_recherche, case=False, na=False)
    resultats = df_rfm[mask]
    if resultats.empty:
        return html.Div("❌ Aucun client trouvé.", style={"color": "#e94560", "fontWeight": "600"})
    cartes = []
    for _, r in resultats.iterrows():
        couleur = PALETTE_SEGMENTS.get(r["segment"], "#888")
        cartes.append(html.Div(style={
            "backgroundColor": "white", "borderRadius": "12px", "padding": "16px 24px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.08)", "borderLeft": f"5px solid {couleur}",
            "display": "flex", "gap": "30px", "flexWrap": "wrap", "alignItems": "center"
        }, children=[
            html.Div([html.H3(r["client"], style={"margin": "0", "color": "#1a1a2e"}), html.P(f"{r['ville']} — {r.get('region','')}", style={"margin": "2px 0", "color": "#6c757d", "fontSize": "13px"})]),
            html.Div([html.B("Segment"), html.P(r["segment"], style={"color": couleur, "fontWeight": "700", "margin": "2px 0"})]),
            html.Div([html.B("Score RFM"), html.P(r["score_rfm"], style={"fontSize": "20px", "fontWeight": "700", "margin": "2px 0"})]),
            html.Div([html.B("Récence"), html.P(f"{r['recence']} jours", style={"margin": "2px 0"})]),
            html.Div([html.B("Commandes"), html.P(str(r["frequence"]), style={"margin": "2px 0"})]),
            html.Div([html.B("CA Total"), html.P(f"{r['montant']:,.2f} €", style={"margin": "2px 0", "color": "#0f3460", "fontWeight": "700"})]),
        ]))
    return html.Div(cartes, style={"display": "flex", "flexDirection": "column", "gap": "10px"})


@app.callback(
    Output("kpi-cards", "children"),
    Output("graph-segments", "figure"),
    Output("graph-ca-mensuel", "figure"),
    Output("graph-top-produits", "figure"),
    Output("graph-regions", "figure"),
    Input("filter-segment", "value"),
    Input("filter-genre", "value"),
    Input("filter-categorie", "value"),
)
def update_dashboard(segment, genre, categorie):
    if not DATA_LOADED:
        empty = go.Figure()
        return [], empty, empty, empty, empty

    cmds = df_cmds.copy()
    rfm = df_rfm.copy()

    if segment != "Tous":
        ids = rfm[rfm["segment"] == segment]["client_id"].tolist()
        cmds = cmds[cmds["client_id"].isin(ids)]
        rfm = rfm[rfm["segment"] == segment]
    if genre != "Tous":
        cmds = cmds[cmds["genre_produit"] == genre]
    if categorie != "Toutes":
        cmds = cmds[cmds["categorie"] == categorie]

    ca_total = cmds["montant_ligne"].sum()
    nb_clients = cmds["client_id"].nunique()
    nb_commandes = cmds["commande_id"].nunique()
    panier_moyen = cmds.groupby("commande_id")["montant_ligne"].sum().mean() if nb_commandes > 0 else 0

    def kpi_card(titre, valeur, couleur, icone):
        return html.Div(style={"backgroundColor": "white", "borderRadius": "12px", "padding": "20px 28px",
            "boxShadow": "0 2px 8px rgba(0,0,0,0.06)", "borderTop": f"4px solid {couleur}", "flex": "1", "minWidth": "180px"}, children=[
            html.P(f"{icone} {titre}", style={"margin": "0 0 8px", "fontSize": "12px", "fontWeight": "600", "color": "#6c757d"}),
            html.H2(valeur, style={"margin": "0", "fontSize": "28px", "fontWeight": "700", "color": couleur}),
        ])

    cards = [
        kpi_card("Chiffre d'Affaires", f"{ca_total:,.0f} €", "#0f3460", "💶"),
        kpi_card("Clients actifs", f"{nb_clients}", "#533483", "👥"),
        kpi_card("Commandes", f"{nb_commandes}", "#1a1a2e", "🛍️"),
        kpi_card("Panier moyen", f"{panier_moyen:,.0f} €", "#e94560", "🛒"),
    ]

    seg_counts = rfm["segment"].value_counts().reset_index()
    seg_counts.columns = ["segment", "nb_clients"]
    fig_seg = px.pie(seg_counts, names="segment", values="nb_clients", hole=0.55,
                     color="segment", color_discrete_map=PALETTE_SEGMENTS, title="Répartition des segments RFM")
    fig_seg.update_traces(textposition="outside", textinfo="percent+label")
    fig_seg.update_layout(showlegend=False, margin=dict(t=50, b=20, l=20, r=20), paper_bgcolor="white")

    ca_mois = cmds.groupby("mois")["montant_ligne"].sum().reset_index()
    ca_mois.columns = ["mois", "ca"]
    ca_mois = ca_mois.sort_values("mois")
    fig_mois = px.bar(ca_mois, x="mois", y="ca", title="Chiffre d'affaires mensuel (€)",
                      labels={"mois": "Mois", "ca": "CA (€)"}, color_discrete_sequence=["#0f3460"])
    fig_mois.update_layout(paper_bgcolor="white", plot_bgcolor="#f8f9fa", margin=dict(t=50, b=40, l=40, r=20), xaxis_tickangle=-45)

    top_prods = cmds.groupby(["produit", "categorie"])["montant_ligne"].sum().reset_index().sort_values("montant_ligne", ascending=True).tail(10)
    fig_prods = px.bar(top_prods, x="montant_ligne", y="produit", orientation="h",
                       color="categorie", title="Top 10 produits par CA (€)", labels={"montant_ligne": "CA (€)", "produit": ""})
    fig_prods.update_layout(paper_bgcolor="white", plot_bgcolor="#f8f9fa", margin=dict(t=50, b=20, l=20, r=20))

    if not rfm.empty and "region" in rfm.columns:
        rfm_ids = rfm[["client_id", "region"]].drop_duplicates()
        cmds_reg = cmds.merge(rfm_ids, on="client_id", how="left")
        ca_reg = cmds_reg.groupby("region")["montant_ligne"].sum().reset_index()
        ca_reg.columns = ["region", "ca"]
        fig_reg = px.bar(ca_reg.sort_values("ca", ascending=False), x="ca", y="region",
                         orientation="h", title="CA par région (€)", color_discrete_sequence=["#533483"])
    else:
        fig_reg = go.Figure()
    fig_reg.update_layout(paper_bgcolor="white", plot_bgcolor="#f8f9fa", margin=dict(t=50, b=20, l=20, r=20))

    return cards, fig_seg, fig_mois, fig_prods, fig_reg


if __name__ == "__main__":
    print("🚀 Dashboard disponible sur http://127.0.0.1:8050")
    app.run(debug=True)