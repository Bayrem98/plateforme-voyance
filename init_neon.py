"""
Script one-shot pour créer les tables + thèmes + admin sur Neon.
⚠️ À exécuter UNE SEULE FOIS.
"""
import os
from dotenv import load_dotenv
load_dotenv()

# ⚠️ REMPLACE par ta vraie URL Neon
os.environ['DATABASE_URL'] = 'postgresql://neondb_owner:npg_AsdHCjz1SwZ7@ep-sparkling-thunder-b1o1sjhx-pooler.c-5.eu-central-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'

from app import app
from models import db, User, Theme, RendezVous
from werkzeug.security import generate_password_hash

with app.app_context():
    # 1. Créer les tables
    db.create_all()
    print("✅ Tables créées sur Neon !")

    # 2. Créer les 3 thèmes
    themes_data = [
        ('Astrologie', 'Les signes du zodiaque, planètes et maisons.',
         'bi-sun', '#ff9800'),
        ('Numérologie', 'Les nombres et leur signification.',
         'bi-123', '#2196f3'),
        ('Tarot de Marseille', 'Les 22 arcanes majeurs.',
         'bi-suit-spade', '#9c27b0'),
    ]
    for nom, desc, ic, col in themes_data:
        if not Theme.query.filter_by(nom=nom).first():
            db.session.add(Theme(nom=nom, description=desc, icone=ic, couleur=col))
            print(f"✅ Thème créé : {nom}")
        else:
            print(f"ℹ️  Thème existe déjà : {nom}")
    db.session.commit()

    # 3. Créer l'admin
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@voyance.com',
            password=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin créé : admin / admin123")
    else:
        print("ℹ️  Admin existe déjà")

    print("\n🎉 Neon est prêt !")
    print("Étapes suivantes :")
    print("  1. python import_word.py")
    print("  2. python import_exercices.py")
    print("  3. python import_tarot.py")