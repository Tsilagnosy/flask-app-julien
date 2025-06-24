import os
import requests
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env en local
load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATA_FOLDER = "data"

def send_file_to_telegram(file_path):
    TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": f"Sauvegarde : {os.path.basename(file_path)}"
    }

    with open(file_path, "rb") as doc:
        files = {"document": doc}
        response = requests.post(TELEGRAM_API, data=payload, files=files)

    if response.ok:
        print(f"✅ Fichier envoyé : {file_path}")
        os.remove(file_path)
        print(f"🗑️ Supprimé après envoi : {file_path}")
    else:
        print(f"❌ Échec de l'envoi : {file_path}")
        print(f"🔎 Code: {response.status_code}, Message: {response.text}")

def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Les variables d'environnement TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont obligatoires.")
        return

    files_sent = False

    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".xlsx") and not filename.startswith("."):
            file_path = os.path.join(DATA_FOLDER, filename)
            send_file_to_telegram(file_path)
            files_sent = True

    if not files_sent:
        print("📭 Aucun fichier à envoyer dans /data")

if __name__ == "__main__":
    main()