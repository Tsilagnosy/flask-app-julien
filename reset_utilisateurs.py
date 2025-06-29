from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client.get_default_database()

confirmation = input("⚠️ Es-tu sûr de vouloir tout supprimer ? (oui/non) : ").lower()
if confirmation == 'oui':
    result = db.utilisateurs.delete_many({})
    print(f"✅ {result.deleted_count} utilisateurs supprimés.")
else:
    print("❌ Opération annulée.")