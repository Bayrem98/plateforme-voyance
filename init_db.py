from app import app
from models import db, User, Theme, Formation, Question
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    # ========== UTILISATEURS ==========
    
    # 1. SuperAdmin
    admin = User(username='admin', email='admin@v.com',
                 password=generate_password_hash('admin123'), role='admin')
    db.session.add(admin)
    db.session.commit()

    # 2. Recruteur (recrute les candidats)
    recruteur = User(username='recruteur1', email='rec@v.com',
                     password=generate_password_hash('rec123'), role='recruteur')
    db.session.add(recruteur)
    db.session.commit()

    # 3. Formateur
    formateur = User(username='formateur1', email='f1@v.com',
                     password=generate_password_hash('form123'), role='formateur')
    db.session.add(formateur)
    db.session.commit()

    # 4. Candidat (rattaché à un recruteur ET un formateur)
    candidat = User(
        username='candidat1',
        email='c1@v.com',
        password=generate_password_hash('candidat123'),
        role='candidat',
        formateur_id=formateur.id,
        recruteur_id=recruteur.id,
    )
    db.session.add(candidat)
    db.session.commit()

    # ========== THÈMES ==========
    themes_data = [
        ('Astrologie', 'Les signes du zodiaque, planètes et maisons.',
         'bi-sun', '#ff9800'),
        ('Numérologie', 'Les nombres et leur signification.',
         'bi-123', '#2196f3'),
        ('Tarot de Marseille', 'Les 22 arcanes majeurs.',
         'bi-suit-spade', '#9c27b0'),
    ]
    themes = {}
    for nom, desc, ic, col in themes_data:
        t = Theme(nom=nom, description=desc, icone=ic, couleur=col)
        db.session.add(t)
        themes[nom] = t
    db.session.commit()

    # Formations de base
    Formation(titre="Introduction à l'Astrologie",
              contenu="<p>L'astrologie étudie la position des astres...</p>",
              theme_id=themes['Astrologie'].id, ordre=1)
    Formation(titre="Les bases de la Numérologie",
              contenu="<p>Chaque nombre a une vibration...</p>",
              theme_id=themes['Numérologie'].id, ordre=1)
    db.session.commit()

    print("✅ BDD initialisée")
    print("🔑 admin / admin123          (SuperAdmin)")
    print("🔑 recruteur1 / rec123       (Recruteur — crée les candidats)")
    print("🔑 formateur1 / form123      (Formateur — gère formations)")
    print("🔑 candidat1 / candidat123   (Candidat — passe les tests)")