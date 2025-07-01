# db.py
import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["Cluster0"]

# 🎯 Collections
utilisateurs = db["utilisateurs_validés"]

# 🔍 Fonctions principales

def inserer_utilisateur(data):
    data["timestamp"] = datetime.utcnow()
    data.setdefault("role", "user")
    data.setdefault("admin", False)
    utilisateurs.insert_one(data)

def trouver_utilisateur_par_username(username):
    return utilisateurs.find_one({"username": username})

def verifier_credentiels(username, mot_de_passe_clair, check_password_hash):
    user = trouver_utilisateur_par_username(username)
    if user and check_password_hash(user["password"], mot_de_passe_clair):
        return user
    return None

def get_utilisateurs_admins():
    return list(utilisateurs.find({"admin": True}))

def get_tous_les_utilisateurs():
    return list(utilisateurs.find({}, {"_id": 0}))

def est_admin(username):
    user = trouver_utilisateur_par_username(username)
    return bool(user and user.get("admin"))

# Pour export clair
__all__ = [
    "utilisateurs",
    "inserer_utilisateur",
    "trouver_utilisateur_par_username",
    "verifier_credentiels",
    "get_utilisateurs_admins",
    "get_tous_les_utilisateurs",
    "est_admin"
]