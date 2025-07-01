from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from functools import wraps
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

admin_bp = Blueprint('admin', __name__)
client = MongoClient(os.getenv("MONGO_URI"))
db = client["Cluster0"]

# 🔐 Décorateur pour restreindre l'accès aux administrateurs
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        username = session.get('username')
        print("👤 Session username:", username)

        user = db.utilisateurs.find_one({"username": username})
        print("🔍 Utilisateur trouvé:", user)

        if not user or user.get('admin') is not True:
            print("🚫 Accès refusé — pas admin")
            return redirect(url_for('login'))

        print("✅ Accès autorisé — admin confirmé")
        return f(*args, **kwargs)
    return wrapper
    

# 📊 Dashboard Admin (liste des utilisateurs)
@admin_bp.route('/')
@admin_required
def admin_dashboard():
    from db import utilisateurs, est_admin

    username = session.get('username')

    if not est_admin(username):
        flash("⛔ Accès refusé — réservé aux admins.", "danger")
        return redirect(url_for("login"))

    all_users = list(utilisateurs.find())

    # 🧮 Statistiques utiles
    total = len(all_users)
    admins = sum(1 for u in all_users if u.get("admin") is True)
    standards = total - admins

    # Inscrits aujourd’hui
    today = datetime.utcnow().date()
    recent = sum(1 for u in all_users if u.get("created_at") and u["created_at"].date() == today)

    return render_template(
        'admin_dashboard.html',
        utilisateurs=all_users,
        stats={
            "total": total,
            "admins": admins,
            "standards": standards,
            "today": recent
        }
    )
    

# 🗑️ Supprimer un utilisateur
@admin_bp.route('/admin/supprimer/<username>')
@admin_required
def supprimer_utilisateur(username):
    db.utilisateurs.delete_one({'username': username})
    flash(f"✅ Utilisateur {username} supprimé.")
    return redirect(url_for('admin.admin_dashboard'))

# 🔒 Restreindre un utilisateur par signature
@admin_bp.route('/admin/restreindre/<signature>')
@admin_required
def restreindre_acces(signature):
    db.utilisateurs.update_many({'signature': signature}, {'$set': {'restreint': True}})
    flash(f"⛔ Accès restreint pour signature : {signature}")
    return redirect(url_for('admin.admin_dashboard'))
    
@admin_bp.route('/admin/reset_utilisateurs', methods=['POST'])
@admin_required
def reset_utilisateurs():
    # Supprime tous les utilisateurs sauf ceux marqués admin=True
    result = db.utilisateurs.delete_many({"admin": {"$ne": True}})
    flash(f"🧼 {result.deleted_count} utilisateur(s) supprimé(s), les admins ont été conservés.", "info")
    return redirect(url_for('admin.admin_dashboard'))