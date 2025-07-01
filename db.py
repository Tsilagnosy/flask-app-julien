import os
from datetime import datetime
from typing import Optional, Dict, List
from pymongo import MongoClient, ReturnDocument
from pymongo.collection import Collection
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

load_dotenv()

class DatabaseManager:
    def __init__(self):
        self.client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"))
        self.db = self.client[os.getenv("MONGO_DB_NAME", "Cluster0")]
        self.utilisateurs = self.db[os.getenv("MONGO_COLLECTION", "utilisateurs")]

    # 🔍 Opérations CRUD de base
    def creer_utilisateur(self, data: Dict) -> Dict:
        """Insère un nouvel utilisateur avec des valeurs par défaut"""
        data.update({
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "role": data.get("role", "user"),
            "admin": data.get("admin", False),
            "active": data.get("active", True)
        })
        result = self.utilisateurs.insert_one(data)
        return self.trouver_utilisateur_par_id(result.inserted_id)

    def trouver_utilisateur_par_id(self, user_id: str) -> Optional[Dict]:
        """Trouve un utilisateur par son _id"""
        return self.utilisateurs.find_one({"_id": user_id})

    def trouver_utilisateur_par_username(self, username: str) -> Optional[Dict]:
        """Trouve un utilisateur par son username"""
        return self.utilisateurs.find_one({"username": username})

    def mettre_a_jour_utilisateur(self, username: str, updates: Dict) -> Optional[Dict]:
        """Met à jour un utilisateur et retourne la nouvelle version"""
        updates["updated_at"] = datetime.utcnow()
        return self.utilisateurs.find_one_and_update(
            {"username": username},
            {"$set": updates},
            return_document=ReturnDocument.AFTER
        )

    # 🔐 Fonctions d'authentification
    def verifier_credentiels(self, username: str, mot_de_passe_clair: str) -> Optional[Dict]:
        """Vérifie les identifiants et retourne l'utilisateur si valide"""
        user = self.trouver_utilisateur_par_username(username)
        if user and check_password_hash(user["password"], mot_de_passe_clair):
            self.utilisateurs.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )
            return user
        return None

    # 📊 Fonctions de requêtage
    def get_utilisateurs_admins(self) -> List[Dict]:
        """Retourne tous les utilisateurs admin"""
        return list(self.utilisateurs.find({"admin": True}))

    def get_tous_utilisateurs(self, filtre: Dict = None) -> List[Dict]:
        """Retourne tous les utilisateurs avec un filtre optionnel"""
        filtre = filtre or {}
        return list(self.utilisateurs.find(filtre))

    def est_admin(self, username: str) -> bool:
        """Vérifie si un utilisateur est admin"""
        user = self.trouver_utilisateur_par_username(username)
        return user and user.get("admin", False)

    # 🔄 Méthodes utilitaires
    def compter_utilisateurs(self, filtre: Dict = None) -> int:
        """Compte les utilisateurs selon un filtre"""
        filtre = filtre or {}
        return self.utilisateurs.count_documents(filtre)

    def desactiver_utilisateur(self, username: str) -> bool:
        """Désactive un compte utilisateur"""
        result = self.utilisateurs.update_one(
            {"username": username},
            {"$set": {"active": False, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

# Instance globale pour une utilisation facile
db_manager = DatabaseManager()

# Export des fonctions principales pour compatibilité ascendante
inserer_utilisateur = db_manager.creer_utilisateur
trouver_utilisateur_par_username = db_manager.trouver_utilisateur_par_username
verifier_credentiels = db_manager.verifier_credentiels
get_utilisateurs_admins = db_manager.get_utilisateurs_admins
get_tous_les_utilisateurs = db_manager.get_tous_utilisateurs
est_admin = db_manager.est_admin
utilisateurs = db_manager.utilisateurs

__all__ = [
    "db_manager",
    "utilisateurs",
    "inserer_utilisateur",
    "trouver_utilisateur_par_username",
    "verifier_credentiels",
    "get_utilisateurs_admins",
    "get_tous_les_utilisateurs",
    "est_admin"
]