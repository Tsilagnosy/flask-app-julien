import os
import json
import pandas as pd
import gspread
import requests
import random
import humanize
from admin import admin_bp
from flask import Flask, session, request, redirect, url_for, render_template, abort, flash, send_from_directory, Response
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from werkzeug.security import generate_password_hash, check_password_hash
from database import utilisateurs  # Modification ici - Import depuis database.py
from admin_seed import admin_seed_bp
from dotenv import load_dotenv
from admin import init_app

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
app.register_blueprint(admin_seed_bp)

# 📧 --- CONFIGURATION FLASK-MAIL --
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alexcardosydonie@gmail.com'
app.config['MAIL_PASSWORD'] = 'vysl egbx ybpd ecjr'
app.config['MAIL_DEFAULT_SENDER'] = 'alexcardosydonie@gmail.com'
mail = Mail(app)

# Constantes Admin
ADMIN_USERNAME = "@Julien_Huller"
ADMIN_PASSWORD = "silentehacking!?#"
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)
MAX_ATTEMPTS = 6
BLOCK_DURATION = timedelta(hours=1)
login_attempts = {}  # Stockage des tentatives de connexion

# Fonctions utilitaires
def generate_validation_code():
    return str(random.randint(100000, 999999))

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

def alerter_connexion_admin(username):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            msg = f"👑 *Connexion admin détectée*\nUtilisateur : `{username}`\n⏱️ {datetime.utcnow().strftime('%d/%m/%Y %H:%M:%S')} UTC"
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}
            )
        except Exception as e:
            print("⚠️ Erreur Telegram admin :", e)

# Fonction pour vérifier les credentials (remplace l'import depuis db.py)
def verifier_credentiels(username, mot_de_passe_clair, check_password_hash):
    utilisateur = utilisateurs.find_one({"username": username})
    # Vérifiez d'abord si l'utilisateur existe et a un champ password
    if not utilisateur or "password" not in utilisateur:
        return None
    if check_password_hash(utilisateur["password"], mot_de_passe_clair):
        return utilisateur
    return None

# Fonction pour insérer un utilisateur (remplace l'import depuis db.py)
def inserer_utilisateur(data):
    data.setdefault("admin", False)
    data.setdefault("created_at", datetime.utcnow())
    return utilisateurs.insert_one(data)

# Routes
@app.route('/')
def accueil():
    return render_template('index.html')

@app.route('/saisie', methods=['GET', 'POST'])
def saisie():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        data = {
            'nom': request.form.get('nom'),
            'cell': request.form.get('cell'),
            'numero': request.form.get('numero'),
            'fruit': request.form.get('fruit'),
            'num_fruit': request.form.get('num_fruit'),
            'adresse': request.form.get('adresse'),
            'occupation': request.form.get('occupation'),
            'Fotoana': request.form.get('Fotoana'),
            'gender': request.form.get('gender'),
            'dob': request.form.get('dob'),
            'religion': request.form.get('religion')
        }

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
            sheet.append_row(list(data.values()))
        except Exception as e:
            print("⚠️ Erreur Google Sheets :", e)

        return redirect(url_for('success'))

    return render_template('saisie.html')

@app.route('/voir_liste')
def voir_liste():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)
        records = client.open_by_key(SHEET_ID).worksheet("Donnees_Site_Users").get_all_records()
    except Exception as e:
        print("⚠️ Erreur lecture Google Sheets :", e)
        records = []

    return render_template('liste.html', records=records)

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
        delai = timedelta(minutes=2)

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

            signature = request.headers.get('User-Agent', 'Inconnu')
            creation_date = datetime.utcnow()

            try:
                ip_info = requests.get("https://ipinfo.io").json()
                localisation = f"{ip_info.get('city', 'Inconnu')}, {ip_info.get('country', 'Inconnu')}"
            except Exception as e:
                print("⚠️ Erreur localisation :", e)
                localisation = "Localisation inconnue"

            inserer_utilisateur({
                "username": username,
                "email": email,
                "telegram": telegram,
                "password": hashed_password,
                "via": "email" if email else "telegram",
                "signature": signature,
                "created_at": creation_date,
                "location": localisation,
                "admin": False
            })

            session['username'] = username
            session['is_admin'] = False
            session.pop('validation_code', None)
            session.pop('code_start_time', None)
            session.pop('attempts', None)

            return redirect(url_for('choix'))

        else:
            flash(f"❌ Code incorrect ({session['attempts']} / 5)", "warning")
            return redirect(url_for('verify'))
    
    resend_history = session.get('resend_history', [])
    nb_demandes = len([ts for ts in resend_history if datetime.utcnow() - datetime.fromisoformat(ts) < timedelta(minutes=30)])
    return render_template('verify.html', nb_demandes=nb_demandes)

@app.route('/resend_code', methods=['POST'])
def resend_code():
    tentative = session.get('attempts', 0)

    if tentative > 5:
        session.clear()
        flash("🚫 Trop de tentatives. Redirection vers la connexion.", "danger")
        return redirect(url_for('login'))

    username = session.get('pending_username')
    email = session.get('email')
    telegram = session.get('telegram')

    if not username or (not email and not telegram):
        flash("Session invalide. Merci de recommencer.", "warning")
        return redirect(url_for('create_account'))

    now = datetime.utcnow()
    historique = session.get('resend_history', [])
    historique_valide = [ts for ts in historique if now - datetime.fromisoformat(ts) < timedelta(minutes=30)]

    if len(historique_valide) >= 4:
        flash("⏳ Trop de demandes. Veuillez attendre avant de redemander un nouveau code.", "danger")
        return redirect(url_for('verify'))

    nouveau_code = generate_validation_code()
    session['validation_code'] = nouveau_code
    session['code_start_time'] = now.isoformat()
    session['attempts'] = 0
    session['resend_history'] = historique_valide + [now.isoformat()]

    try:
        if email:
            envoyer_code_par_mail(email, nouveau_code, username)
            flash("📧 Nouveau code envoyé par email.", "info")
        elif telegram:
            envoyer_code_par_telegram(telegram, nouveau_code)
            flash("📲 Nouveau code envoyé par Telegram.", "info")
    except Exception as e:
        flash(f"❌ Erreur d'envoi : {e}", "danger")

    return redirect(url_for('verify'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Réinitialisation sécurisée de la session
    session.clear()
    session.permanent = True  # Active les sessions persistantes

    client_ip = request.remote_addr

    # Gestion des tentatives bloquées
    if client_ip in login_attempts:
        if login_attempts[client_ip].get("blocked_until") and datetime.utcnow() < login_attempts[client_ip]["blocked_until"]:
            flash("Trop de tentatives. Réessayez plus tard.", "danger")
            return redirect(url_for('login'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Validation des entrées
        if not username or not password:
            flash("Tous les champs sont requis", "warning")
            return redirect(url_for('login'))

        # 🔐 Connexion Admin - Version renforcée
        if username == ADMIN_USERNAME:
            if check_password_hash(ADMIN_PASSWORD_HASH, password):
                # Configuration robuste de la session
                session.update({
                    'user_id': str(utilisateurs.find_one({"username": username})["_id"]),
                    'username': username,
                    'is_admin': True,
                    'login_time': datetime.utcnow().isoformat(),
                    '_fresh': True
                })

                # Mise à jour last login
                utilisateurs.update_one(
                    {"username": username},
                    {"$set": {
                        "last_login": datetime.utcnow(),
                        "ip_address": client_ip
                    }}
                )

                login_attempts.pop(client_ip, None)
                flash("Connexion admin réussie", "success")
                return redirect(url_for('admin.admin_dashboard'))
            else:
                flash("Accès refusé", "danger")
                return redirect(url_for('login'))

        # 👥 Connexion utilisateur standard
        user = verifier_credentiels(username, password, check_password_hash)
        if user:
            session.update({
                'user_id': str(user["_id"]),
                'username': user["username"],
                'is_admin': user.get("admin", False),
                'login_time': datetime.utcnow().isoformat()
            })

            utilisateurs.update_one(
                {"_id": user["_id"]},
                {"$set": {"last_login": datetime.utcnow()}}
            )

            login_attempts.pop(client_ip, None)
            flash("Connexion réussie", "success")
            return redirect(url_for('admin.admin_dashboard' if session['is_admin'] else 'choix'))

        # 🚨 Gestion des échecs
        flash("Identifiants incorrects", "danger")
        login_attempts[client_ip] = {
            "count": login_attempts.get(client_ip, {}).get("count", 0) + 1,
            "last_attempt": datetime.utcnow()
        }
        
        if login_attempts[client_ip]["count"] >= MAX_ATTEMPTS:
            login_attempts[client_ip]["blocked_until"] = datetime.utcnow() + BLOCK_DURATION

        return redirect(url_for('login'))

    return render_template('login.html')

#CONTACTER L' ADMIN
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
    
    
#DEBUG POUR ADMIN
@app.route('/debug_admin')
def debug_admin():
    from database import utilisateurs
    admin = utilisateurs.find_one({"username": "@Julien_Huller"})
    return {
        'in_db': bool(admin),
        'is_admin_in_db': admin.get('admin') if admin else None,
        'session': dict(session),
        'session_is_admin': session.get('is_admin')
    }
    
# PAGE DE CONNEXION REUSSITE
@app.route('/success')
def success():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('success.html')

# Page de CONNEXION VIA PAGE D'ACCEUIL
@app.route('/communaute')
def communaute():
    return redirect(url_for('login'))

#AVANT CONNEXION 
@app.before_request
def clear_flash_if_redirect():
    if request.referrer and request.referrer != request.url:
        if session.get('_flashes'):
            session['_flashes'] = []
            
@app.route('/hard_logout')
def hard_logout():
    session.clear()
    return redirect(url_for('login'))
# CHOIX POUR UTILISATEURS
@app.route('/choix')
def choix():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('choix.html')
 
# Redirection pour REPORT BBT 
@app.route('/report')
def report():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('report.html')
       
 # Route pour DECONNEXION  
@app.route('/logout')
def logout():
    session.clear()
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

app.register_blueprint(admin_bp, url_prefix='/admin', template_folder='templates')
init_app(app)  # Initialise les filtres

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
    

