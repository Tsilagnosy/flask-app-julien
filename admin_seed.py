# admin_seed.py
from flask import Blueprint, request, abort
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime
import os

admin_seed_bp = Blueprint('admin_seed', __name__)
client = MongoClient(os.getenv("MONGO_URI"))
db = client["ma_base"]
utilisateurs = db["utilisateurs_validés"]

SEED_KEY = os.getenv("SEED_KEY")
SEED_STATUS_FILE = "admin_seeded.flag"

@admin_seed_bp.route('/seed-admin')
def seed_admin():
    # 🚫 Blocage si déjà semé
    if os.path.exists(SEED_STATUS_FILE):
        return "✅ Admin déjà injecté. Accès désactivé.", 403

    # 🔑 Vérifie la clé dans l'URL
    if request.args.get("key") != SEED_KEY:
        return "⛔ Clé invalide.", 401

    admin_username = "@Julien_Huller"
    if utilisateurs.find_one({"username": admin_username}):
        return "ℹ️ Utilisateur déjà en base.", 200

    plain_pwd = os.getenv("ADMIN_PASSWORD")
    if not plain_pwd:
        return "⚠️ Mot de passe admin non configuré.", 500

    utilisateurs.insert_one({
        "username": admin_username,
        "email": "tsilagnosyjulien@gmail.com",
        "telegram": "",
        "password": generate_password_hash(plain_pwd),
        "admin": True,
        "role": "admin",
        "via": "admin_seed.py",
        "created_at": datetime.utcnow(),
        "signature": request.headers.get("User-Agent", "inconnu"),
        "location": "Seed sécurisé",
        "timestamp": datetime.utcnow()
    })

    # 🔒 Désactive la route définitivement
    with open(SEED_STATUS_FILE, "w") as f:
        f.write("seeded")

    print("👑 Admin semé avec succès et verrouillé.")
    return "🚀 Admin initialisé et verrouillé.", 201