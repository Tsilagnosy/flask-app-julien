from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response, jsonify
from functools import wraps
import os
from datetime import datetime, timedelta
from database import utilisateurs  # Utilisation de la connexion centralisée
from db import db_manager  # Pour utiliser les nouvelles méthodes
import csv
from io import StringIO
from flask_moment import Moment
import humanize
from flask import current_app

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

admin_bp = Blueprint('admin', __name__)

def init_app(app):
    # Enregistrement direct du filtre sans décorateur
    app.jinja_env.filters['humanize'] = humanize_datetime
    
    # Ou pour une initialisation au démarrage :
    with app.app_context():
        app.jinja_env.filters['humanize'] = humanize_datetime

def humanize_datetime(dt):
    """Convertit un datetime en format "il y a X temps" """
    if not dt:
        return "Jamais"
    
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 365:
        return f"il y a {diff.days//365} an(s)"
    elif diff.days > 30:
        return f"il y a {diff.days//30} mois"
    elif diff.days > 0:
        return f"il y a {diff.days} jour(s)"
    elif diff.seconds > 3600:
        return f"il y a {diff.seconds//3600} heure(s)"
    elif diff.seconds > 60:
        return f"il y a {diff.seconds//60} minute(s)"
    else:
        return "à l'instant"
# ==============================================
# 🔐 DÉCORATEURS ET FONCTIONS UTILITAIRES
# ==============================================

def admin_required(f):
    """Décorateur pour restreindre l'accès aux admins"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            session['_flashes'] = []  # Vide les messages flash parasites
            flash("Accès admin requis", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def log_admin_action(action, target=None):
    """Journalise une action admin dans la base de données"""
    try:
        db_manager.get_db().admin_logs.insert_one({
            'admin': session.get('username'),
            'action': action,
            'target': target,
            'ip': request.remote_addr,
            'timestamp': datetime.utcnow()
        })
    except Exception as e:
        print(f"⚠️ Erreur de journalisation: {str(e)}")

# ==============================================
# 📊 ROUTES PRINCIPALES DU DASHBOARD
# ==============================================

@admin_bp.route('/')
@admin_required
def admin_dashboard():
    """
    Affiche le tableau de bord admin avec pagination
    Gère les filtres : /admin/?inactifs=1 ou /admin/?admins=1
    """
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Construction du filtre
    filtre = {}
    if request.args.get('inactifs'):
        filtre['active'] = False
    if request.args.get('admins'):
        filtre['admin'] = True
    
    # Récupération des utilisateurs avec pagination
    users = list(utilisateurs.find(filtre)
              .sort('created_at', -1)
              .skip((page-1)*per_page)
              .limit(per_page))
    
    # Calcul des statistiques
    stats = {
        'total': utilisateurs.count_documents({}),
        'admins': utilisateurs.count_documents({'admin': True}),
        'today': utilisateurs.count_documents({
            'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0)}
        }),
        'active': utilisateurs.count_documents({'active': True}),
        'inactive': utilisateurs.count_documents({'active': False})
    }
    stats['standards'] = stats['total'] - stats['admins']
    
    return render_template(
        'admin_dashboard.html',
        utilisateurs=users,
        stats=stats,
        current_page=page
    )

# ==============================================
# 🔄 ROUTES DE GESTION DES UTILISATEURS
# ==============================================

@admin_bp.route('/toggle-admin/<username>')
@admin_required
def toggle_admin(username):
    """Basculer le statut admin d'un utilisateur"""
    if username == session.get('username'):
        flash("❌ Impossible de modifier votre propre statut", "danger")
    else:
        user = utilisateurs.find_one({'username': username})
        if user:
            new_status = not user.get('admin', False)
            utilisateurs.update_one(
                {'username': username},
                {'$set': {'admin': new_status, 'updated_at': datetime.utcnow()}}
            )
            status = "promu admin" if new_status else "rétrogradé"
            flash(f"🔄 Utilisateur {username} {status}", "info")
            log_admin_action(f"Changement statut admin ({status})", username)
    return redirect(url_for('.admin_dashboard'))

@admin_bp.route('/toggle-active/<username>')
@admin_required
def toggle_active(username):
    """Activer/désactiver un compte utilisateur"""
    if username == session.get('username'):
        flash("❌ Impossible de désactiver votre propre compte", "danger")
    else:
        user = utilisateurs.find_one({'username': username})
        if user:
            new_status = not user.get('active', True)
            utilisateurs.update_one(
                {'username': username},
                {'$set': {'active': new_status, 'updated_at': datetime.utcnow()}}
            )
            status = "activé" if new_status else "désactivé"
            flash(f"🔄 Compte {username} {status}", "info")
            log_admin_action(f"Changement statut actif ({status})", username)
    return redirect(url_for('.admin_dashboard'))

@admin_bp.route('/supprimer/<username>')
@admin_required
def supprimer_utilisateur(username):
    """Supprimer un utilisateur non-admin"""
    user = utilisateurs.find_one({"username": username})
    if user and not user.get("admin"):
        utilisateurs.delete_one({"username": username})
        flash(f"❌ Utilisateur {username} supprimé", "warning")
        log_admin_action("Suppression utilisateur", username)
    else:
        flash("⚠️ Impossible de supprimer un administrateur ou utilisateur introuvable", "danger")
    return redirect(url_for('.admin_dashboard'))

@admin_bp.route('/promouvoir/<username>')
@admin_required
def promouvoir_admin(username):
    """Promouvoir un utilisateur en admin"""
    user = utilisateurs.find_one({"username": username})
    if not user:
        flash(f"❌ Utilisateur {username} introuvable", "danger")
        return redirect(url_for('.admin_dashboard'))

    if user.get("admin"):
        flash(f"ℹ️ {username} est déjà admin", "info")
        return redirect(url_for('.admin_dashboard'))

    utilisateurs.update_one(
        {"username": username},
        {"$set": {"admin": True, "role": "admin", "promu_le": datetime.utcnow()}}
    )
    flash(f"🚀 {username} promu au rang d'administrateur", "success")
    log_admin_action("Promotion admin", username)
    return redirect(url_for('.admin_dashboard'))

@admin_bp.route('/reset-users', methods=['POST'])
@admin_required
def reset_utilisateurs():
    """Supprimer tous les utilisateurs non-admins"""
    confirm = request.form.get('confirmation')
    if confirm == "CONFIRMER":
        result = utilisateurs.delete_many({"admin": {"$ne": True}})
        flash(f"🧹 {result.deleted_count} utilisateurs non-admins supprimés", "info")
        log_admin_action("Reset global des utilisateurs")
    else:
        flash("❌ Confirmation invalide - aucune action effectuée", "danger")
    return redirect(url_for('.admin_dashboard'))

# ==============================================
# 📊 API POUR LE DASHBOARD DYNAMIQUE
# ==============================================

@admin_bp.route('/api/user_activity')
@admin_required
def user_activity_data():
    """
    Endpoint API pour les données du graphique d'activité
    Retourne le nombre d'inscriptions par jour sur 30 jours
    """
    pipeline = [
        {
            '$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                'count': {'$sum': 1}
            }
        },
        {'$sort': {'_id': 1}},
        {'$limit': 30}
    ]
    
    try:
        data = list(utilisateurs.aggregate(pipeline))
        return jsonify({'status': 'success', 'data': data})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@admin_bp.route('/api/user_stats')
@admin_required
def user_stats():
    """Endpoint API pour les statistiques instantanées"""
    stats = {
        'total': utilisateurs.count_documents({}),
        'admins': utilisateurs.count_documents({'admin': True}),
        'active': utilisateurs.count_documents({'active': True}),
        'inactive': utilisateurs.count_documents({'active': False}),
        'today': utilisateurs.count_documents({
            'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0)}
        })
    }
    return jsonify({'status': 'success', 'stats': stats})

# ==============================================
# 🛠️ ROUTES DE GESTION AVANCÉE
# ==============================================

@admin_bp.route('/api/update_user', methods=['POST'])
@admin_required
def api_update_user():
    """
    Endpoint API pour modifier un utilisateur
    Accepte: email, active, admin
    """
    try:
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({'status': 'error', 'message': 'Username required'}), 400
        
        updates = {
            'updated_at': datetime.utcnow()
        }
        
        # Champs modifiables
        if 'email' in data:
            updates['email'] = data['email'].strip()
        if 'active' in data:
            updates['active'] = bool(data['active'])
        if 'admin' in data:
            updates['admin'] = bool(data['admin'])
        
        result = utilisateurs.update_one(
            {'username': username},
            {'$set': updates}
        )
        
        log_admin_action("Mise à jour via API", username)
        return jsonify({
            'status': 'success',
            'modified_count': result.modified_count
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==============================================
# 📤 EXPORT DE DONNÉES
# ==============================================

@admin_bp.route('/export/users.csv')
@admin_required
def export_users_csv():
    """Export CSV de tous les utilisateurs"""
    users = list(utilisateurs.find({}, {
        'username': 1,
        'email': 1,
        'admin': 1,
        'active': 1,
        'created_at': 1,
        'last_login': 1,
        '_id': 0
    }))
    
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'username', 'email', 'admin', 'active', 'created_at', 'last_login'
    ])
    writer.writeheader()
    
    for user in users:
        user['created_at'] = user['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        user['last_login'] = user.get('last_login', '').strftime('%Y-%m-%d %H:%M:%S') if user.get('last_login') else ''
        writer.writerow(user)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = 'attachment; filename=users_export.csv'
    response.headers['Content-type'] = 'text/csv'
    log_admin_action("Export CSV des utilisateurs")
    return response

# ==============================================
# 📝 JOURNAL DES ACTIONS ADMIN
# ==============================================

@admin_bp.route('/api/admin_logs')
@admin_required
def get_admin_logs():
    """Récupère les 50 dernières actions admin pour l'audit"""
    try:
        logs = list(db_manager.get_db().admin_logs.find()
                  .sort('timestamp', -1)
                  .limit(50))
        
        # Conversion pour le JSON
        for log in logs:
            log['_id'] = str(log['_id'])
            log['timestamp'] = log['timestamp'].isoformat()
        
        return jsonify({'status': 'success', 'logs': logs})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
  
