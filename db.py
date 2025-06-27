# db.py
from pymongo import MongoClient
from datetime import datetime
import os
from dotenv import load_dotenv
load_dotenv()

#client = MongoClient(os.environ.get("MONGO_URI"))
#db = client["ma_base"]
#users = db["utilisateurs_validés"]

def inserer_utilisateur(data):
    data["timestamp"] = datetime.utcnow()
    data["role"] = "user"
    users.insert_one(data)

def trouver_utilisateur_par_username(username):
    return users.find_one({"username": username})

def verifier_credentiels(username, mot_de_passe_clair, check_password_hash):
    user = trouver_utilisateur_par_username(username)
    if user and check_password_hash(user["password"], mot_de_passe_clair):
        return user
    return None
    
"""  
def get_all_utilisateurs():
    collection = db["utilisateurs"]
    return list(collection.find())  # ou .find({}, {"_id": 0}) pour ne pas exposer l'ID
 """
def get_all_utilisateurs():
    return [
        {
            "username": "julien_dev",
            "email": "julien@example.com",
            "telegram": None,
            "date_inscription": "2025-06-27",
            "active": True
        },
        {
            "username": "invite42",
            "email": None,
            "telegram": "123456789",
            "date_inscription": "2025-06-26",
            "active": False
        }
    ]