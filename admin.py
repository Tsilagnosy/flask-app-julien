from flask import Blueprint, render_template, session, redirect, url_for
from db import get_all_utilisateurs

admin_bp = Blueprint("admin", __name__)


"""
    # Adaptation des données pour le rendu HTML
    liste_utilisateurs = []
    for u in utilisateurs:
        liste_utilisateurs.append({
            "username": u.get("username", "—"),
            "email": u.get("email", None),
            "telegram": u.get("telegram", None),
            "date_inscription": u.get("date_inscription", "—"),
            "active": u.get("active", True)  # True par défaut si le champ n'existe pas
        })

    return render_template("admin/dashboard.html", utilisateurs=liste_utilisateurs)
    """
@admin_bp.route("/admin")
def admin_dashboard():
    if not session.get("is_admin"):
        return redirect(url_for("login"))

@admin_bp.route("/")
def index():
    return redirect(url_for("admin.admin_dashboard"))
    # 🔽 Bloc temporaire pour test local
    utilisateurs = [
        {
            "username": "julien_dev",
            "email": "julien@example.com",
            "telegram": None,
            "date_inscription": "2025-06-27",
            "active": True
        },
        {
            "username": "invite42",
            "email": None,
            "telegram": "123456789",
            "date_inscription": "2025-06-26",
            "active": False
        }
    ]

    return render_template("admin/dashboard.html", utilisateurs=utilisateurs)
    
if __name__ == "__main__":
    from flask import Flask
    import os

    app = Flask(__name__)
    app.secret_key = "test-secret"  # nécessaire pour la gestion des sessions

    # Fausse session pour simuler un admin
    @app.before_request
    def simuler_admin():
        from flask import session
        session["is_admin"] = True

    app.register_blueprint(admin_bp, url_prefix="/")  # ou autre préfixe unique si tu veux

    app.run(debug=True)