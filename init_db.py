from app import app
from models import db, User, Theme, Formation, Question
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    # ========== UTILISATEURS ==========
    admin = User(username='admin', email='admin@v.com',
                 password=generate_password_hash('admin123'), role='admin')
    formateur = User(username='formateur1', email='f1@v.com',
                     password=generate_password_hash('form123'), role='formateur')
    db.session.add_all([admin, formateur])
    db.session.commit()

    recrue = User(username='recrue1', email='r1@v.com',
                  password=generate_password_hash('recrue123'),
                  role='recruteur', formateur_id=formateur.id)
    db.session.add(recrue)
    db.session.commit()

    # ========== THÈMES (3 seulement) ==========
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

    # ========== FORMATIONS DE BASE ==========
    Formation(
        titre="Introduction à l'Astrologie",
        contenu="<p>L'astrologie étudie la position des astres...</p>",
        theme_id=themes['Astrologie'].id, ordre=1
    )
    Formation(
        titre="Les bases de la Numérologie",
        contenu="<p>Chaque nombre a une vibration...</p>",
        theme_id=themes['Numérologie'].id, ordre=1
    )

    # ========== QUESTIONS TEST ==========
    questions_data = [
        ("Quel est le premier signe du zodiaque ?",
         "Taureau", "Bélier", "Gémeaux", "Poisson", "b",
         "Le Bélier ouvre le cycle zodiacal.", "Astrologie"),
        ("Combien de signes compte le zodiaque ?",
         "10", "11", "12", "13", "c",
         "12 signes, un par mois.", "Astrologie"),
    ]
    for texte, a, b, c, d, bonne, expl, theme_nom in questions_data:
        Question(texte=texte, option_a=a, option_b=b, option_c=c, option_d=d,
                 bonne_reponse=bonne, explication=expl,
                 theme_id=themes[theme_nom].id)

    db.session.commit()
    print("✅ BDD initialisée")
    print("🔑 admin / admin123")
    print("🔑 formateur1 / form123")
    print("🔑 recrue1 / recrue123")
    print()
    print("📌 Étapes suivantes :")
    print("   1. python import_word.py       (Formations Astro + Numérologie)")
    print("   2. python import_exercices.py  (Exercices Numérologie)")
    print("   3. python import_tarot.py      (Cartes Tarot)")