"""
config.py — Chargement des variables d'environnement
Utilise python-dotenv pour lire le fichier .env (jamais commité sur Git)
"""
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "user":     os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD", ""),
    "database": os.getenv("DB_NAME", "pretaporter_db"),
    "charset":  "utf8mb4",
}
