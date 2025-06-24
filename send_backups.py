import os
import time
import requests
from dotenv import load_dotenv

# 🌱 Charge les variables depuis un fichier .env (évite de hardcoder tes clés)
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DATA_FOLDER = 'data'  # Dossier contenant les fichiers .xlsx

def send_file_to_telegram(file_path):
    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    with open(file_path, 'rb') as file_data:
        response = requests.post(url, data={'chat_id': CHAT_ID}, files={'document': file_data})
    if response.status_code != 200:
        print(f"❌ Erreur lors de l'envoi de {file_path} : {response.text}")
    else:
        print(f"✅ Fichier envoyé : {file_path}")

def main():
    if not TOKEN or not CHAT_ID:
        print("⚠️ Les variables d'environnement TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont obligatoires.")
        return

    if not os.path.exists(DATA_FOLDER):
        print("📂 Aucun dossier 'data' trouvé.")
        return

    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith('.xlsx'):
            file_path = os.path.join(DATA_FOLDER, filename)
            send_file_to_telegram(file_path)
            time.sleep(1.5)  # Pause entre les envois pour éviter d'être bloqué

if __name__ == '__main__':
    main()
