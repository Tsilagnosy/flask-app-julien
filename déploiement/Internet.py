import os
import pandas as pd
import secrets
from flask import Flask, session, request, redirect, url_for, render_template
from pyngrok import ngrok  # Pour créer un tunnel réseau externe
import threading

# 🔐 Génération d'une clé secrète pour la session
secret_key = secrets.token_hex(16)

# ⚙️ Création de l'application Flask
app = Flask(__name__)
app.secret_key = secret_key

# 📁 Répertoire de stockage pour les fichiers Excel
DATA_FOLDER = 'data'
if not os.path.exists(DATA_FOLDER):
    os.makedirs(DATA_FOLDER)

# 🔗 Route racine : redirige vers la page de login
@app.route('/')
def index():
    return redirect(url_for('login'))

# 👤 Page de connexion utilisateur
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if username:
            session['username'] = username
            return redirect(url_for('saisie'))
    return render_template('login.html')

# 📝 Page de saisie sécurisée
@app.route('/saisie', methods=['GET', 'POST'])
def saisie():
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Récupération des champs du formulaire
        nom = request.form.get('nom')
        cell = request.form.get('cell')
        numero = request.form.get('numero')
        fruit = request.form.get('fruit')
        num_fruit = request.form.get('num_fruit')
        adresse = request.form.get('adresse')
        occupation = request.form.get('occupation')
        Fotoana = request.form.get('Fotoana')
        gender = request.form.get('gender')
        dob = request.form.get('dob')
        religion = request.form.get('religion')

        username = session['username']
        excel_file_path = os.path.join(DATA_FOLDER, f"{username}.xlsx")

        new_entry = {
            'nom': nom, 'cell': cell, 'numero': numero,
            'fruit': fruit, 'num_fruit': num_fruit,
            'adresse': adresse, 'occupation': occupation,
            'Fotoana': Fotoana, 'gender': gender,
            'dob': dob, 'religion': religion
        }

        # ⚠️ Ajout si "numero" unique
        if os.path.exists(excel_file_path):
            df = pd.read_excel(excel_file_path)
            if numero in df['numero'].astype(str).values:
                return redirect(url_for('success'))  # Déjà enregistré
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
        else:
            df = pd.DataFrame([new_entry])

        df.to_excel(excel_file_path, index=False)
        return redirect(url_for('success'))

    return render_template('saisie.html')

# ✅ Page de confirmation après saisie
@app.route('/success')
def success():
    return render_template('success.html')

# 🔓 Déconnexion
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# 💻 Lancement du serveur Flask + tunnel Ngrok
def run_ngrok():
    # Lance le tunnel sur le port 5000 (Flask)
    public_url = ngrok.connect(5000)
    print(f"\n🔗 Ton app est disponible à cette adresse : {public_url}\n")

if __name__ == '__main__':
    # Lancement du tunnel Ngrok dans un thread séparé
    threading.Thread(target=run_ngrok).start()

    # Démarrage de l’app Flask
    app.run(host='0.0.0.0', port=5000, debug=True)