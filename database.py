from pymongo import MongoClient
import os
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db = client["Cluster0"]  # Utilisez le même nom partout

# Collections
utilisateurs = db["utilisateurs"]