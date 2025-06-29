import os
import json
import pandas as pd
import gspread
import requests
import random
from admin import admin_bp
from flask import Flask, session, request, redirect, url_for, render_template, abort, flash, send_from_directory, Response
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient 
from db import inserer_utilisateur, verifier_credentiels
from dotenv import load_dotenv
load_dotenv()

# 📦 --- CONFIGURATION ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_ID = "1hLPKx-HIfAmQIcePC_owhEklo5Bd-BXviqxQvCO-kMc"
DATA_FOLDER = 'data'
os.makedirs(DATA_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "clé-temporaire-par-défaut")
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# 📧 --- CONFIGURATION FLASK-MAIL ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alexcardosydonie@gmail.com'
app.config['MAIL_PASSWORD'] = 'vysl egbx ybpd ecjr'
app.config['MAIL_DEFAULT_SENDER'] = 'alexcardosydonie@gmail.com'
mail = Mail(app)

@app.route('/')
def accueil():
    return render_template('index.html')

# 🎲 --- GÉNÉRATION CODE DE VALIDATION ---
def generate_validation_code():
    return str(random.randint(100000, 999999))

# 📤 --- ENVOI DU CODE PAR EMAIL ---
def envoyer_code_par_mail(destinataire, code, nom):
    try:
        msg = Message(
            subject="Votre code de validation",
            recipients=[destinataire],
            body=f"Bonjour {nom},\n\nVoici votre code : {code}"
        )
        mail.send(msg)
    except Exception as e:
        print(f"❌ Erreur email : {e}")

# 🤖 --- ENVOI DU CODE PAR TELEGRAM ---
def envoyer_code_par_telegram(chat_id, code):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Token Telegram manquant")
        return

    message = f"👋 Bonjour ! Voici votre code de validation : *{code}*"
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }

    try:
        requests.post(url, data=data)
    except Exception as e:
        print(f"❌ Exception Telegram : {e}")

@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        username = request.form.get('nom', '').strip()
        email = request.form.get('email', '').strip()
        telegram = request.form.get('telegram', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if password != confirm_password:
            flash("⚠️ Les mots de passe ne correspondent pas.", "danger")
            return redirect(url_for('create_account'))

        hashed_password = generate_password_hash(password)
        session['pending_password'] = hashed_password

        code = generate_validation_code()
        session.update({
            'validation_code': code,
            'code_start_time': datetime.utcnow().isoformat(),
            'attempts': 0,
            'pending_username': username,
            'email': email,
            'telegram': telegram
        })

        if email:
            envoyer_code_par_mail(email, code, username)
        elif telegram:
            envoyer_code_par_telegram(telegram, code)
        else:
            flash("❗ Fournissez un e-mail ou identifiant Telegram.", "danger")
            return redirect(url_for('create_account'))

        return redirect(url_for('verify'))

    return render_template('create_account.html')

@app.route('/verify', methods=['GET', 'POST'])
def verify():
    code_attendu = session.get('validation_code')
    start_time = session.get('code_start_time')
    tentative = session.get('attempts', 0)

    if not code_attendu or not start_time:
        flash("⛔ Session invalide. Recommencez.", "danger")
        return redirect(url_for('create_account'))

    if request.method == 'POST':
        now = datetime.utcnow()
        creation_time = datetime.fromisoformat(start_time)
        delai = timedelta(minutes=1)

        if now - creation_time > delai:
            session.clear()
            flash("⏱️ Code expiré. Réinscription requise.", "warning")
            return redirect(url_for('create_account'))

        session['attempts'] = tentative + 1
        if session['attempts'] > 5:
            session.clear()
            flash("🚫 Trop de tentatives échouées.", "danger")
            return redirect(url_for('create_account'))

        code_saisi = request.form.get('code', '').strip()
        if code_saisi == code_attendu:
            username = session.pop('pending_username')
            email = session.pop('email', None)
            telegram = session.pop('telegram', None)
            hashed_password = session.pop('pending_password')

            # 📌 [NOUVEAU] Signature de l'appareil (user-agent)
            signature = request.headers.get('User-Agent', 'Inconnu')

            # 📌 [NOUVEAU] Date de création du compte
            creation_date = datetime.utcnow()

            # 📌 [NOUVEAU] Localisation par IP publique
            try:
                ip_info = requests.get("https://ipinfo.io").json()
                localisation = f"{ip_info.get('city', 'Inconnu')}, {ip_info.get('country', 'Inconnu')}"
            except Exception as e:
                print("⚠️ Erreur localisation :", e)
                localisation = "Localisation inconnue"

            # ✅ Insertion complète de l'utilisateur
            inserer_utilisateur({
                "username": username,
                "email": email,
                "telegram": telegram,
                "password": hashed_password,
                "via": "email" if email else "telegram",
                "signature": signature,
                "created_at": creation_date,
                "location": localisation
            })

            session['username'] = username
            session.pop('validation_code', None)
            session.pop('code_start_time', None)
            session.pop('attempts', None)

            return redirect(url_for('choix'))
        else:
            flash(f"❌ Code incorrect ({session['attempts']} / 5)", "warning")
            return redirect(url_for('verify'))

    return render_template('verify.html')
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("Merci de remplir tous les champs.", "warning")
            return redirect(url_for('login'))

        user = verifier_credentiels(username, password, check_password_hash)

        if user:
            session['username'] = user['username']
            session['is_admin'] = user.get('admin', False)
            flash("✅ Connexion réussie", "success")

            if user.get('admin'):
                return redirect(url_for('admin.admin_dashboard'))
            else:
                return redirect(url_for('formulaire'))

        flash("❌ Identifiants incorrects.", "danger")
        return redirect(url_for('login'))

    return render_template('login.html')
    
    
@app.route('/formulaire', methods=['GET', 'POST'])
def formulaire():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {key: request.form.get(key) for key in [
            'nom', 'cell', 'numero', 'fruit', 'num_fruit',
            'adresse', 'occupation', 'Fotoana', 'gender', 'dob', 'religion'
        ]}

        username = session['username']
        file_path = os.path.join(DATA_FOLDER, f"{username}.xlsx")

        if os.path.exists(file_path):
            df = pd.read_excel(file_path)
            if data['numero'] in df['numero'].astype(str).values:
                return redirect(url_for('success'))
            df = pd.concat([df, pd.DataFrame([data])], ignore_index=True)
        else:
            df = pd.DataFrame([data])

        df.to_excel(file_path, index=False)

        try:
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            client = gspread.authorize(creds)
            sheet = client.open_by_key(SHEET_ID).worksheet("Donnees_Site_Users")
            row = [
                data['nom'], data['cell'], data['numero'], data['fruit'],
                data['num_fruit'], data['adresse'], data['occupation'],
                data['Fotoana'], data['gender'], data['dob'], data['religion']
            ]
            sheet.append_row(row)
        except Exception as e:
            print("⚠️ Erreur Google Sheets :", e)

        return redirect(url_for('success'))

    return render_template('formulaire.html')
    
@app.route('/success')
def success():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('success.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        nom = request.form.get("nom")
        message = request.form.get("message")

        if not nom or not message:
            flash("Merci de remplir tous les champs.", "warning")
            return redirect(url_for("contact"))

        final_message = f"📩 *Nouveau message reçu*\n👤 Nom : {nom}\n💬 {message}"
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

        if not token or not chat_id:
            flash("❌ Configuration Telegram manquante", "danger")
            return redirect(url_for("contact"))

        payload = {
            "chat_id": chat_id,
            "text": final_message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data=payload)
            if response.ok:
                flash("✅ Votre message a été transmis avec succès !", "success")
            else:
                flash("❌ Échec d’envoi à Telegram", "danger")
        except Exception as e:
            flash(f"⚠️ Erreur réseau : {e}", "danger")

        return redirect(url_for("contact"))

    return render_template("contact.html")

@app.route('/communaute')
def communaute():
    return redirect(url_for('login'))

@app.route('/google2b9208b1f9fa091c.html')
def google_verification():
    return send_from_directory('static', 'google2b9208b1f9fa091c.html')

@app.route('/debug-static')
def debug_static():
    return str(os.listdir('static'))

@app.route("/sitemap.xml")
def sitemap():
    sitemap_xml = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://flask-app-julien.onrender.com/</loc><priority>1.0</priority></url>
  <url><loc>https://flask-app-julien.onrender.com/login</loc><priority>0.9</priority></url>
  <url><loc>https://flask-app-julien.onrender.com/contact</loc><priority>0.7</priority></url>
  <url><loc>https://flask-app-julien.onrender.com/communaute</loc><priority>0.6</priority></url>
</urlset>
"""
    return Response(sitemap_xml, mimetype='application/xml')

@app.route('/robots.txt')
def robots():
    return send_from_directory('static', 'robots.txt')

@app.route('/ping')
def ping():
    return "🟢 Appli Flask en ligne et connectée à Google Sheets"

@app.route('/trigger-backup')
def trigger_backup():
    secret = request.args.get("key")
    expected = os.environ.get("BACKUP_SECRET")
    if not secret or secret != expected:
        return abort(403, description="Clé de sécurité invalide")
    os.system("python send_backups.py")
    return "📤 Backup déclenché avec succès", 200

app.register_blueprint(admin_bp)

# ▶️ Lancement
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)