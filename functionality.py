from flask import Blueprint, render_template, request, session, redirect, url_for, send_file
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pandas as pd
import io
import uuid
from database import db

# Initialisation du Blueprint
functionality_bp = Blueprint('functionality', __name__)

class VisitTracker:
    def __init__(self):
        self.collection = db.visits

    def log_visit(self, path, ip, user_agent, user_id=None):
        visit_data = {
            'timestamp': datetime.utcnow(),
            'path': path,
            'ip': ip,
            'user_agent': user_agent,
            'user_id': user_id,
            'session_id': session.get('session_id'),
            'is_authenticated': user_id is not None
        }
        return self.collection.insert_one(visit_data)

    def get_stats(self):
        return {
            'total': self.collection.count_documents({}),
            'today': self.collection.count_documents({
                'timestamp': {'$gt': datetime.utcnow() - timedelta(days=1)}
            }),
            'unique_visitors': len(self.collection.distinct('session_id')),
            'unique_ips': len(self.collection.distinct('ip'))
        }

visit_tracker = VisitTracker()

def register_tracking(app):
    """Fonction à appeler depuis app.py pour enregistrer le tracking"""
    @app.before_request
    def track_visits():
        if request.path.startswith(('/static', '/admin')):
            return
        
        if 'session_id' not in session:
            session['session_id'] = str(uuid.uuid4())
        
        visit_tracker.log_visit(
            path=request.path,
            ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
            user_id=session.get('user_id')
        )

@functionality_bp.route('/visit-stats')
def show_visit_stats():
    stats = visit_tracker.get_stats()
    return render_template('visit_stats.html', stats=stats)
    
    
@functionality_bp.before_request
def strict_admin_check():
    if not current_user.is_authenticated or not session.get('is_admin'):
        return redirect(url_for('login'))

@functionality_bp.route('/admin/users_full')
def users_full_list():
    users = list(db.utilisateurs.find({}, {
        'username': 1,
        'phone': 1,
        'email': 1,
        'created_at': 1,
        'location': 1,
        'ip_address': 1,
        'device_id': 1,
        '_id': 0
    }))
    
    for user in users:
        user['created_at'] = user.get('created_at', datetime.utcnow()).strftime('%d/%m/%Y %H:%M')
        user['device_id'] = user.get('device_id', 'N/A')
    
    return render_template('admin/users_full.html', 
                         users=users,
                         current_page='users')

@functionality_bp.route('/admin/visit_stats')
def visit_stats():
    stats = visit_tracker.get_stats()
    return render_template('admin/visit_stats.html', 
                         stats=stats,
                         current_page='stats')

@functionality_bp.route('/admin/preview/<page>')
def route_preview(page):
    allowed_pages = {
        'choix': 'choix.html',
        'listes': 'listes.html',
        'saisie': 'saisie.html',
        'contact': 'contact.html',
        'report': 'report.html'
    }
    
    if page not in allowed_pages:
        return redirect(url_for('functionality.users_full_list'))
    
    return render_template(allowed_pages[page], 
                         admin_preview=True,
                         current_page='preview')

@functionality_bp.route('/admin/export_users')
def export_users():
    users = list(db.utilisateurs.find({}, {
        'username': 1,
        'phone': 1,
        'email': 1,
        'created_at': 1,
        'location': 1,
        'ip_address': 1,
        'device_id': 1
    }))
    
    df = pd.DataFrame(users)
    
    if 'created_at' in df.columns:
        df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Utilisateurs', index=False)
    
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"export_utilisateurs_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )

@functionality_bp.route('/admin/export_visits')
def export_visits():
    visits = list(db.visits.find({}, {
        'timestamp': 1,
        'path': 1,
        'ip': 1,
        'user_agent': 1,
        'is_authenticated': 1
    }).limit(1000))
    
    df = pd.DataFrame(visits)
    
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
    
    output = io.StringIO()
    df.to_csv(output, index=False)
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f"visits_export_{datetime.now().strftime('%Y%m%d')}.csv"
    )

def init_functionality(app):
    app.register_blueprint(functionality_bp)
    register_tracking(app)  # Enregistre le système de tracking
    
    with app.app_context():
        db.visits.create_index('timestamp')
        db.visits.create_index('session_id')
        db.visits.create_index('user_id')