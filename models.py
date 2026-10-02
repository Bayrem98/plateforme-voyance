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
    role = db.Column(db.String(20), default='recruteur')
    formateur_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    actif = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    formateur = db.relationship('User', remote_side=[id], backref='recruteurs')
    tentatives = db.relationship('Tentative', backref='user', lazy=True)
    reponses_exercices = db.relationship('ReponseExercice', backref='user', lazy=True)


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
    definition = db.Column(db.Text)        # 🆕 petite définition pour les cartes
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
    statut = db.Column(db.String(20), default='en_attente')
    valide = db.Column(db.Boolean, default=False)
    date_soumission = db.Column(db.DateTime, default=datetime.utcnow)
    date_correction = db.Column(db.DateTime)