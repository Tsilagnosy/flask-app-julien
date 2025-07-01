from database import utilisateurs
from werkzeug.security import check_password_hash

# 1. Vérifiez que l'utilisateur existe bien
admin = utilisateurs.find_one({"username": "@Julien_Huller"})
print("Document admin:", admin)

# 2. Simulez la vérification de connexion
if admin and admin.get("admin") is True:
    print("✅ Utilisateur trouvé et est admin")
else:
    print("❌ Problème: utilisateur non trouvé ou pas admin")

# 3. Vérifiez la session Flask
from flask import session
print("Session actuelle:", dict(session))
