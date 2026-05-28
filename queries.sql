-- ============================================================
-- PretAPorter RFM — Requêtes analytiques
-- ============================================================
USE pretaporter_db;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 1 : Top 10 clients par chiffre d'affaires
--             (WHERE + GROUP BY + ORDER BY + LIMIT)
-- ────────────────────────────────────────────────────────────
SELECT
    c.client_id,
    CONCAT(c.prenom, ' ', c.nom)          AS client,
    c.genre,
    c.ville,
    COUNT(DISTINCT co.commande_id)         AS nb_commandes,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_total
FROM clients c
JOIN commandes co      ON co.client_id  = c.client_id
JOIN commandes_produits cp ON cp.commande_id = co.commande_id
WHERE co.statut = 'livree'
GROUP BY c.client_id, c.nom, c.prenom, c.genre, c.ville
ORDER BY ca_total DESC
LIMIT 10;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 2 : Chiffre d'affaires par catégorie
--             (GROUP BY + HAVING + ORDER BY)
-- ────────────────────────────────────────────────────────────
SELECT
    cat.nom                                    AS categorie,
    COUNT(DISTINCT cp.commande_id)             AS nb_ventes,
    SUM(cp.quantite)                           AS unites_vendues,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_total,
    ROUND(AVG(cp.prix_unitaire), 2)            AS prix_moyen
FROM categories cat
JOIN produits p     ON p.categorie_id = cat.categorie_id
JOIN commandes_produits cp ON cp.produit_id = p.produit_id
JOIN commandes co   ON co.commande_id = cp.commande_id
WHERE co.statut = 'livree'
GROUP BY cat.categorie_id, cat.nom
HAVING ca_total > 1000
ORDER BY ca_total DESC;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 3 : Commandes des 90 derniers jours avec détail
--             (WHERE sur date + 3 tables jointes)
-- ────────────────────────────────────────────────────────────
SELECT
    co.commande_id,
    co.date_commande,
    CONCAT(c.prenom, ' ', c.nom)  AS client,
    c.genre,
    p.nom                          AS produit,
    cat.nom                        AS categorie,
    cp.quantite,
    cp.prix_unitaire,
    ROUND(cp.quantite * cp.prix_unitaire, 2) AS sous_total
FROM commandes co
JOIN clients c             ON c.client_id   = co.client_id
JOIN commandes_produits cp ON cp.commande_id = co.commande_id
JOIN produits p            ON p.produit_id  = cp.produit_id
JOIN categories cat        ON cat.categorie_id = p.categorie_id
WHERE co.statut = 'livree'
  AND co.date_commande >= DATE_SUB(NOW(), INTERVAL 90 DAY)
ORDER BY co.date_commande DESC
LIMIT 50;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 4 : Top 10 produits les plus vendus par genre
--             (GROUP BY + ORDER BY + LIMIT)
-- ────────────────────────────────────────────────────────────
SELECT
    p.nom                                      AS produit,
    p.genre                                    AS genre_produit,
    cat.nom                                    AS categorie,
    p.prix,
    SUM(cp.quantite)                           AS unites_vendues,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_genere
FROM produits p
JOIN categories cat        ON cat.categorie_id = p.categorie_id
JOIN commandes_produits cp ON cp.produit_id   = p.produit_id
JOIN commandes co          ON co.commande_id  = cp.commande_id
WHERE co.statut = 'livree'
GROUP BY p.produit_id, p.nom, p.genre, cat.nom, p.prix
ORDER BY ca_genere DESC
LIMIT 10;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 5 : Clients ayant dépensé plus que la moyenne
--             (sous-requête scalaire)
-- ────────────────────────────────────────────────────────────
SELECT
    CONCAT(c.prenom, ' ', c.nom)               AS client,
    c.ville,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_client
FROM clients c
JOIN commandes co      ON co.client_id   = c.client_id
JOIN commandes_produits cp ON cp.commande_id = co.commande_id
WHERE co.statut = 'livree'
GROUP BY c.client_id, c.nom, c.prenom, c.ville
HAVING ca_client > (
    SELECT AVG(total_client)
    FROM (
        SELECT SUM(cp2.quantite * cp2.prix_unitaire) AS total_client
        FROM commandes co2
        JOIN commandes_produits cp2 ON cp2.commande_id = co2.commande_id
        WHERE co2.statut = 'livree'
        GROUP BY co2.client_id
    ) AS sous
)
ORDER BY ca_client DESC;

-- ────────────────────────────────────────────────────────────
-- REQUÊTE 6 : Évolution du CA mensuel (CTE)
-- ────────────────────────────────────────────────────────────
WITH ca_mensuel AS (
    SELECT
        DATE_FORMAT(co.date_commande, '%Y-%m') AS mois,
        ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca
    FROM commandes co
    JOIN commandes_produits cp ON cp.commande_id = co.commande_id
    WHERE co.statut = 'livree'
    GROUP BY mois
),
ca_avec_croissance AS (
    SELECT
        mois,
        ca,
        LAG(ca) OVER (ORDER BY mois) AS ca_mois_precedent
    FROM ca_mensuel
)
SELECT
    mois,
    ca,
    ca_mois_precedent,
    ROUND((ca - ca_mois_precedent) / ca_mois_precedent * 100, 1) AS croissance_pct
FROM ca_avec_croissance
ORDER BY mois;

-- ────────────────────────────────────────────────────────────
-- VUE : Statistiques consolidées par client
-- ────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW vue_stats_clients AS
SELECT
    c.client_id,
    CONCAT(c.prenom, ' ', c.nom)               AS client,
    c.genre,
    c.ville,
    c.date_inscription,
    COUNT(DISTINCT co.commande_id)             AS nb_commandes,
    ROUND(SUM(cp.quantite * cp.prix_unitaire), 2) AS ca_total,
    ROUND(AVG(cp.quantite * cp.prix_unitaire), 2) AS panier_moyen,
    MAX(co.date_commande)                      AS derniere_commande,
    DATEDIFF(NOW(), MAX(co.date_commande))     AS jours_inactif
FROM clients c
LEFT JOIN commandes co       ON co.client_id   = c.client_id AND co.statut = 'livree'
LEFT JOIN commandes_produits cp ON cp.commande_id = co.commande_id
GROUP BY c.client_id, c.nom, c.prenom, c.genre, c.ville, c.date_inscription;

-- Utilisation de la vue
SELECT * FROM vue_stats_clients ORDER BY ca_total DESC;

-- ────────────────────────────────────────────────────────────
-- FONCTION : Attribution d'un label de segment RFM
-- ────────────────────────────────────────────────────────────
DELIMITER $$

CREATE FUNCTION IF NOT EXISTS fn_rfm_label(
    score_r INT,
    score_f INT,
    score_m INT
) RETURNS VARCHAR(50)
DETERMINISTIC
BEGIN
    DECLARE rfm_score INT;
    SET rfm_score = score_r * 100 + score_f * 10 + score_m;

    IF score_r >= 4 AND score_f >= 4 AND score_m >= 4 THEN
        RETURN 'Champion';
    ELSEIF score_r >= 3 AND score_f >= 3 THEN
        RETURN 'Client Fidèle';
    ELSEIF score_r >= 3 AND score_f <= 2 THEN
        RETURN 'Loyaliste Potentiel';
    ELSEIF score_r <= 2 AND score_f >= 3 THEN
        RETURN 'A Risque';
    ELSEIF score_r = 1 AND score_f = 1 THEN
        RETURN 'Perdu';
    ELSE
        RETURN 'Nouveau Client';
    END IF;
END$$

DELIMITER ;

-- ────────────────────────────────────────────────────────────
-- PROCÉDURE : Rapport de performance par catégorie
-- ────────────────────────────────────────────────────────────
DELIMITER $$

CREATE PROCEDURE sp_rapport_categories(IN p_annee INT)
BEGIN
    SELECT
        cat.nom                                        AS categorie,
        p.genre                                        AS genre_produit,
        COUNT(DISTINCT co.commande_id)                 AS nb_commandes,
        SUM(cp.quantite)                               AS unites_vendues,
        ROUND(SUM(cp.quantite * cp.prix_unitaire), 2)  AS ca_total,
        ROUND(AVG(cp.prix_unitaire), 2)                AS prix_moyen_vente
    FROM categories cat
    JOIN produits p         ON p.categorie_id  = cat.categorie_id
    JOIN commandes_produits cp ON cp.produit_id   = p.produit_id
    JOIN commandes co       ON co.commande_id   = cp.commande_id
    WHERE co.statut = 'livree'
      AND YEAR(co.date_commande) = p_annee
    GROUP BY cat.categorie_id, cat.nom, p.genre
    ORDER BY ca_total DESC;
END$$

DELIMITER ;

-- Appel de la procédure
CALL sp_rapport_categories(2024);
