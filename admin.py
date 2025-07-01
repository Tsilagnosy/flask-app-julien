from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import datetime
from database import utilisateurs  # Utilisation de la connexion centralisée
from db import db_manager  # Pour utiliser les nouvelles méthodes

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 🔐 Décorateur admin amélioré
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('is_admin'):
            flash("🔒 Accès administrateur requis", "danger")
            return redirect(url_for('login'))
        
        # Vérification supplémentaire en base si nécessaire
        username = session.get('username')
        if not db_manager.est_admin(username):
            flash("⛔ Permission administrateur révoquée", "warning")
            session.clear()
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return wrapper

# 📊 Tableau de bord admin optimisé
@admin_bp.route('/')
@admin_required
def admin_dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    filtre = {}
    if request.args.get('inactifs'):
        filtre['active'] = False
    if request.args.get('admins'):
        filtre['admin'] = True
    
    # Solution 1: Utilisation correcte de sort() avec PyMongo
    users = list(utilisateurs.find(filtre)
              .sort('created_at', -1)  # Notez la syntaxe correcte
              .skip((page-1)*per_page)
              .limit(per_page))
    
    # Solution alternative si la première ne fonctionne pas:
    # users = list(utilisateurs.find(filtre)
    #           .sort([('created_at', pymongo.DESCENDING)])
    #           .skip((page-1)*per_page)
    #           .limit(per_page))
    
    stats = {
        'total': utilisateurs.count_documents({}),
        'admins': utilisateurs.count_documents({'admin': True}),
        'today': utilisateurs.count_documents({
            'created_at': {
                '$gte': datetime.utcnow().replace(hour=0, minute=0, second=0)
            }
        })
    }
    stats['standards'] = stats['total'] - stats['admins']
    
    return render_template(
        'admin_dashboard.html',
        utilisateurs=users,
        stats=stats,
        current_page=page
    )

# 🔄 Gestion du statut admin
@admin_bp.route('/toggle-admin/<username>')
@admin_required
def toggle_admin(username):
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
    return redirect(url_for('.admin_dashboard'))

# 🔒 Gestion des comptes inactifs
@admin_bp.route('/toggle-active/<username>')
@admin_required
def toggle_active(username):
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
    return redirect(url_for('.admin_dashboard'))

# 🧹 Reset amélioré avec confirmation
@admin_bp.route('/reset-users', methods=['POST'])
@admin_required
def reset_utilisateurs():
    confirm = request.form.get('confirmation')
    if confirm == "CONFIRMER":
        result = utilisateurs.delete_many({"admin": {"$ne": True}})
        flash(f"🧹 {result.deleted_count} utilisateurs non-admins supprimés", "info")
    else:
        flash("❌ Confirmation invalide - aucune action effectuée", "danger")
    return redirect(url_for('.admin_dashboard'))