from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    # Rôles : 'candidat', 'recruteur', 'formateur', 'admin'
    role = db.Column(db.String(20), default='candidat')
    formateur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    recruteur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relations d'auto-référence
    formateur = db.relationship('User', foreign_keys=[formateur_id],
                                remote_side=[id], backref='candidats')
    recruteur = db.relationship('User', foreign_keys=[recruteur_id],
                                remote_side=[id], backref='candidats_recrutes')
    
    # Relations vers d'autres tables
    tentatives = db.relationship('Tentative', backref='user', lazy=True)
    cartes_validees = db.relationship('CarteValidee', backref='user', lazy=True,
                                     cascade='all, delete-orphan')
    
    # ⚠️ PAS de relationship 'reponses_exercices' ici
    # Il est défini côté ReponseExercice pour éviter l'ambiguïté


class Theme(db.Model):
    __tablename__ = 'themes'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    icone = db.Column(db.String(50), default='bi-book')
    couleur = db.Column(db.String(20), default='#6f42c1')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    formations = db.relationship('Formation', backref='theme', lazy=True,
                                 cascade='all, delete-orphan')
    questions = db.relationship('Question', backref='theme', lazy=True,
                                cascade='all, delete-orphan')
    exercices = db.relationship('Exercice', backref='theme', lazy=True,
                                cascade='all, delete-orphan')


class Formation(db.Model):
    __tablename__ = 'formations'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(200))
    definition = db.Column(db.Text)
    ordre = db.Column(db.Integer, default=1)
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    texte = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    bonne_reponse = db.Column(db.String(1), nullable=False)
    explication = db.Column(db.Text)
    difficulte = db.Column(db.String(20), default='facile')
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)


class Tentative(db.Model):
    __tablename__ = 'tentatives'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    nb_bonnes = db.Column(db.Integer, nullable=False)
    nb_total = db.Column(db.Integer, nullable=False)
    date_passage = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)

    theme = db.relationship('Theme', backref='tentatives')


class Exercice(db.Model):
    __tablename__ = 'exercices'
    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    domaine = db.Column(db.String(50))
    niveau = db.Column(db.Integer, default=1)
    enonce = db.Column(db.Text, nullable=False)
    donnees = db.Column(db.Text)
    mots_cles = db.Column(db.Text)
    reponse_attendue = db.Column(db.Text)
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)
    ordre = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    reponses = db.relationship('ReponseExercice', backref='exercice',
                               cascade='all, delete-orphan')


class ReponseExercice(db.Model):
    __tablename__ = 'reponses_exercice'
    id = db.Column(db.Integer, primary_key=True)
    exercice_id = db.Column(db.Integer, db.ForeignKey('exercices.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reponse_client = db.Column(db.Text)
    explication = db.Column(db.Text)
    note = db.Column(db.Integer)
    commentaire_formateur = db.Column(db.Text)
    commentaire_ia = db.Column(db.Text)
    statut = db.Column(db.String(20), default='en_attente')
    valide = db.Column(db.Boolean, default=False)
    duree_secondes = db.Column(db.Integer)
    corrige_par_ia = db.Column(db.Boolean, default=False)
    # 🆕 Qui a fait la correction manuelle (override) ?
    correcteur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    date_soumission = db.Column(db.DateTime, default=datetime.utcnow)
    date_correction = db.Column(db.DateTime)

    # Relations avec foreign_keys explicites (OBLIGATOIRE car 2 FK vers users)
    user = db.relationship('User', foreign_keys=[user_id],
                           backref='reponses_soumises')
    correcteur = db.relationship('User', foreign_keys=[correcteur_id],
                                 backref='corrections_effectuees')


class CarteValidee(db.Model):
    __tablename__ = 'cartes_validees'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    theme_id = db.Column(db.Integer, db.ForeignKey('themes.id'), nullable=False)
    niveau = db.Column(db.Integer, nullable=False)
    moyenne = db.Column(db.Float)
    validee = db.Column(db.Boolean, default=False)
    date_validation = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'theme_id', 'niveau',
                            name='unique_carte_par_user'),
    )


class RendezVous(db.Model):
    __tablename__ = 'rendez_vous'
    id = db.Column(db.Integer, primary_key=True)
    recruteur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    candidat_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_heure = db.Column(db.DateTime, nullable=False)
    duree_minutes = db.Column(db.Integer, default=30)
    type_rdv = db.Column(db.String(50), default='Entretien')
    notes = db.Column(db.Text)
    statut = db.Column(db.String(20), default='planifie')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # foreign_keys explicites car 2 FK vers users
    recruteur = db.relationship('User', foreign_keys=[recruteur_id],
                                backref='rdvs_planifies')
    candidat = db.relationship('User', foreign_keys=[candidat_id],
                               backref='rdvs_recus')