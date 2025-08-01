import os
import json
import pandas as pd
import gspread
import requests
import random
import humanize
from admin import admin_bp
from flask import Flask, session, request, redirect, url_for, render_template, abort, flash, send_from_directory, Response, jsonify, make_response
from flask_mail import Mail, Message
from datetime import datetime, timedelta
from oauth2client.service_account import ServiceAccountCredentials
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_required, LoginManager
from database import utilisateurs  # Modification ici - Import depuis database.py
from functionality import functionality_bp
from admin_seed import admin_seed_bp
from dotenv import load_dotenv
from admin import init_app
#from flask_wtf.csrf import CSRFProtect  # Ajoutez cette importat

load_dotenv()

# 📦 --- CONFIGURATION ---
SCOPE = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
SHEET_ID = "1hLPKx-HIfAmQIcePC_owhEklo5Bd-BXviqxQvCO-kMc"
DATA_FOLDER = 'data'
os.makedirs(DATA_FOLDER, exist_ok=True)
# ###Creation App Flask#####
app = Flask(__name__)
##Initialisation du Key#####
app.secret_key = os.environ.get("FLASK_SECRET", "clé-temporaire-par-défaut")
# Après app.secret_key
#app.config['WTF_CSRF_SECRET_KEY'] =os.environ.get("FLASK_SECRET")
###########NOUVELLE AJOUT####
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax"
)
# Après avoir créé  application Flask
#csrf = CSRFProtect(app)
############################
app.register_blueprint(admin_seed_bp)

# 📧 --- CONFIGURATION FLASK-MAIL --
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'alexcardosydonie@gmail.com'
app.config['MAIL_PASSWORD'] = 'vysl egbx ybpd ecjr'
app.config['MAIL_DEFAULT_SENDER'] = 'alexcardosydonie@gmail.com'
mail = Mail(app)

###### #Constantes Admin#######
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_PASSWORD_HASH = generate_password_hash(ADMIN_PASSWORD)
MAX_ATTEMPTS = 6
BLOCK_DURATION = timedelta(hours=1)
login_attempts = {}  # Stockage des tentatives de connexion

###INITIALIZATION LOGINMANAGER##
login_manager=LoginManager()
login_manager.init_app(app)
login_manager.login_view="login"
######Fonctions utilitaires########
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

########### Routes#####(((())))####
"""@app.route('/')
def accueil():
    return render_template('index.html') 
    
###########Nouvelle####
@app.before_request
def csrf_protect():
    if request.method in ("POST", "PUT", "DELETE"):
        csrf_token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        if not csrf_token or csrf_token != session.get('csrf_token'):
            abort(400, description="CSRF token invalide")
##########################
"""
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
    response = make_response(render_template('saisie.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
    
    
# A Effacer si Cause de probleme
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)
#=================================
@app.route('/voir_liste')
def voir_liste():
    if 'username' not in session:
        return redirect(url_for('login'))

    try:
        creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(SHEET_ID).worksheet("Donnees_Site_Users")
        raw_data = sheet.get_all_values()
        #print(raw_data)

        # 🧹 Standardisation des en-têtes (colonne A à P = 0 à 15)
        headers = [col.strip() for col in raw_data[1][:16]]

        # 🧠 Transformation en dictionnaire robuste
        records = []
        for row in raw_data[2:]:
            values = row[:16] + [None] * (16 - len(row))  # Complète la ligne si elle est trop courte
            record = dict(zip(headers, values))
            records.append(record)

    except Exception as e:
        print("⚠️ Erreur lecture Google Sheets :", e)
        records = []

    return render_template('liste.html', records=records)
#######CREATION DE COMPTE######
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

    # Méthode GET : affichage du formulaire avec désactivation du cache
    response = make_response(render_template('create_account.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
    
#####VERIFICATION DU COMPTE#####
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
#######REDEMANDER LE CODE######
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
########CONECTION INITIALE######
@app.route('/', methods=['GET', 'POST'])
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
                session.update({
                    'user_id': str(utilisateurs.find_one({"username": username})["_id"]),
                    'username': username,
                    'is_admin': True,
                    'login_time': datetime.utcnow().isoformat(),
                    '_fresh': True
                })
                utilisateurs.update_one(
                    {"username": username},
                    {"$set": {"last_login": datetime.utcnow(), "ip_address": client_ip}}
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

    # GET : affichage du formulaire de login avec headers anti-cache
    response = make_response(render_template('login.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response
    
######CONTACTER L' ADMIN#######
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
    
"""    
#DEBUG POUR ADMIN
@app.route('/debug_admin')
def debug_admin():
    from database import utilisateurs
    admin = utilisateurs.find_one({"username": " "})
    return {
        'in_db': bool(admin),
        'is_admin_in_db': admin.get('admin') if admin else None,
        'session': dict(session),
        'session_is_admin': session.get('is_admin')
    } """
    
#########CHATGI REPORT ########
@app.route('/chatgi', methods=['GET', 'POST'])
def chatgi():
    if request.method == 'POST':
        # 📦 Récupération des données du formulaire
        data = {
            'nom': request.form.get('hazonaina'),
            'cell': request.form.get('sela'),
            'fruit': request.form.get('voankazo'),
            'num_fruit': request.form.get('nomerao'),
            'adresse': request.form.get('adiresy'),
            'gender': request.form.get('genre'),
            'Fotoana': request.form.get('fotoana'),
        }

        try:
            # 🔐 Connexion sécurisée à Google Sheets
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
            client = gspread.authorize(creds)

            # 📄 Accès à la feuille "AllChatgi"
            sheet = client.open_by_key(SHEET_ID).worksheet("AllChatgi")
            existing_data = sheet.get_all_values()[1:]  # Ignore l'en-tête

            # 🔍 Vérification des doublons sur fruit + num_fruit
            for row in existing_data:
                if len(row) >= 4:
                    existing_fruit = row[2].strip()
                    existing_num = row[3].strip()
                    if (existing_fruit == data['fruit'].strip() and
                        existing_num == data['num_fruit'].strip()):
                        flash("⚠️ Ce fruit avec ce numéro a déjà été enregistré.")
                        return redirect(url_for('chatgi'))

            # 📝 Ajout des données si pas de doublon
            sheet.append_row(list(data.values()))
            flash("✅ Rapport enregistré avec succès.")
            return redirect(url_for('success'))

        except Exception as e:
            print("⚠️ Erreur Google Sheets :", e)
            flash("Une erreur est survenue lors de l'enregistrement.")
            return redirect(url_for('chatgi'))

    # Affiche le formulaire si GET
    return render_template("chatgi.html") 
    
### PAGE DE CONNEXION REUSSITE##
@app.route('/success')
def success():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('success.html')

# Page de CONNEXION VIA PAGE D'ACCEUIL
@app.route('/communaute')
def communaute():
    return redirect(url_for('login'))

#####AVANT CONNEXION ##########
@app.before_request
def clear_flash_if_redirect():
    if request.referrer and request.referrer != request.url:
        if session.get('_flashes'):
            session['_flashes'] = []
            
@app.route('/hard_logout')
def hard_logout():
    session.clear()
    return redirect(url_for('login'))
### CHOIX POUR UTILISATEURS######
@app.route('/choix')
def choix():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('choix.html')
 
#### Redirection pour REPORT BBT ###
@app.route('/report')
def report():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('report.html')
       
 #### Route pour DECONNEXION######
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

@app.route('/sitemap.xml')
def serve_sitemap():
    return send_from_directory(app.static_folder, 'sitemap.xml')

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

#Transfert UPDATE VERS TELEGRAM
""" TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Garde-le dans un fichier .env ou variables d'env
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") """

@app.route('/envoyer_telegram', methods=['POST'])
def envoyer_message():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHATS_ID")
    data = request.json

    message = f"""📢 Nouveau formulaire soumis:

🏷️ Team: {data.get('team', 'Non spécifié')}
👤 BBS: {data.get('bbs', 'Non spécifié')}
🚻 Sexe: {data.get('sexe', 'Non spécifié')}
📞 Tel: {data.get('tel', 'Non spécifié')}
📚 Lesona natao: {data.get('lesona', 'Non spécifié')}
🌳 Tree + Cell: {data.get('tree_cell', 'Non spécifié')}
📲 Contact Tree: {data.get('contact_tree', 'Non spécifié')}
🏆 Catégorie: {data.get('categorie', 'Non spécifié')}
👥 BBT nandray: {data.get('BBT', 'Non spécifié')}
⏰ Fotoana manaraka: {data.get('next_date', 'Non spécifié')}"""

    telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(telegram_url, json={
        "chat_id": chat_id,
        "text": message
    })

    if response.ok:
        return jsonify({"message": "Message bien envoyé!"})
    else:
        return jsonify({"error": "Échec de l'envoi Telegram"}), 500


app.register_blueprint(admin_bp, url_prefix='/admin', template_folder='templates')
init_app(app)  # Initialise les filtres
app.register_blueprint(functionality_bp)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
    

