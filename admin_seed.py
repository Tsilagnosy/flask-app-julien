from flask import Blueprint, request
from werkzeug.security import generate_password_hash
from datetime import datetime
import os
from database import utilisateurs  # Utilisation de la connexion centralisée

admin_seed_bp = Blueprint('admin_seed', __name__)

SEED_KEY = os.getenv("SEED_KEY")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "silentehacking!?#")  # Valeur par défaut
SEED_STATUS_FILE = "admin_seeded.flag"

@admin_seed_bp.route('/seed-admin')
def seed_admin():
    """Endpoint pour créer l'admin initial de manière sécurisée"""
    
    # Vérification du verrou
    if os.path.exists(SEED_STATUS_FILE):
        return "🔒 Admin déjà créé - sécurité activée", 403

    # Vérification de la clé de sécurité
    if request.args.get("key") != SEED_KEY:
        return "🔑 Clé de sécurité invalide", 401

    # Vérification si l'admin existe déjà
    admin_username = "@Julien_Huller"
    if utilisateurs.find_one({"username": admin_username, "admin": True}):
        return "ℹ️ Compte admin existe déjà", 200

    # Création du compte admin
    admin_data = {
        "username": admin_username,
        "email": "tsilagnosyjulien@gmail.com",
        "password": generate_password_hash(ADMIN_PASSWORD),
        "admin": True,
        "role": "superadmin",
        "via": "seed_script",
        "created_at": datetime.utcnow(),
        "last_login": None,
        "signature": request.headers.get("User-Agent", "seed_script"),
        "ip_creation": request.remote_addr,
        "active": True
    }

    try:
        # Insertion avec vérification
        result = utilisateurs.replace_one(
            {"username": admin_username},
            admin_data,
            upsert=True
        )
        
        # Création du verrou
        with open(SEED_STATUS_FILE, 'w') as f:
            f.write(datetime.utcnow().isoformat())
            
        return f"👑 Admin créé avec succès (ID: {result.upserted_id})", 201
        
    except Exception as e:
        return f"❌ Erreur lors de la création: {str(e)}", 500