from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random, json
from datetime import datetime

from config import Config
from models import (db, User, Theme, Formation, Question, Tentative,
                    Exercice, ReponseExercice)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Veuillez vous connecter."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ============================================================
#   DÉCORATEUR DE RÔLES
# ============================================================

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash("Accès refusé.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
#   PROGRESSION (Tarot de Marseille)
# ============================================================

def progression_tarot(user_id, theme_id):
    """
    Retourne la liste des cartes avec état (débloqué / validé).
    Chaque carte = {niveau, formation, exercices, reponses, debloque, valide}
    """
    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    exercices = Exercice.query.filter_by(theme_id=theme_id)\
                              .order_by(Exercice.niveau, Exercice.ordre).all()
    mes_rep = {r.exercice_id: r for r in
               ReponseExercice.query.filter_by(user_id=user_id).all()}

    niveaux = {}
    for f in formations:
        niveaux.setdefault(f.ordre, {})['formation'] = f
    for ex in exercices:
        niv = ex.niveau or 1
        niveaux.setdefault(niv, {}).setdefault('exercices', []).append(ex)

    resultat = []
    precedent_valide = True
    for niv in sorted(niveaux.keys()):
        info = niveaux[niv]
        exs = info.get('exercices', [])
        reps = {ex.id: mes_rep[ex.id] for ex in exs if ex.id in mes_rep}

        tous_valides = bool(exs) and all(
            reps.get(ex.id) and reps[ex.id].valide for ex in exs
        )

        resultat.append({
            'niveau': niv,
            'formation': info.get('formation'),
            'exercices': exs,
            'reponses': reps,
            'debloque': precedent_valide,
            'valide': tous_valides,
        })
        precedent_valide = tous_valides

    return resultat


# ============================================================
#   AUTH
# ============================================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            if not user.actif:
                flash("Compte désactivé.", "danger")
                return redirect(url_for('login'))
            login_user(user)
            return redirect(url_for('dashboard'))
        flash("Identifiants incorrects.", "danger")
    return render_template('auth/login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'formateur':
        return redirect(url_for('formateur_dashboard'))
    return redirect(url_for('recruteur_dashboard'))


# ============================================================
#   RECRUTEUR
# ============================================================

@app.route('/recruteur')
@login_required
@role_required('recruteur')
def recruteur_dashboard():
    themes = Theme.query.all()
    scores = {}
    for t in themes:
        best = Tentative.query.filter_by(user_id=current_user.id, theme_id=t.id)\
                              .order_by(Tentative.score.desc()).first()
        scores[t.id] = best
    return render_template('recruteur/dashboard.html', themes=themes, scores=scores)


# ============================================================
#   TAROT DE MARSEILLE — Système de cartes progressives
# ============================================================

@app.route('/cartes-tarot/<int:theme_id>')
@login_required
@role_required('recruteur')
def cartes_tarot(theme_id):
    """Affiche la grille des 22 cartes avec verrouillage progressif."""
    theme = Theme.query.get_or_404(theme_id)

    if theme.nom != 'Tarot de Marseille':
        flash("Cette page est réservée au Tarot de Marseille.", "warning")
        return redirect(url_for('recruteur_dashboard'))

    cartes = progression_tarot(current_user.id, theme_id)
    return render_template('recruteur/cartes_tarot.html',
                           theme=theme, cartes=cartes)


@app.route('/carte-tarot/<int:formation_id>')
@login_required
@role_required('recruteur')
def voir_carte_tarot(formation_id):
    """Affiche la formation d'une carte + ses exercices."""
    formation = Formation.query.get_or_404(formation_id)
    theme = formation.theme

    if theme.nom != 'Tarot de Marseille':
        return redirect(url_for('voir_formation', theme_id=theme.id))

    # Vérifier le déblocage
    cartes = progression_tarot(current_user.id, theme.id)
    carte = next((c for c in cartes if c['niveau'] == formation.ordre), None)

    if not carte or not carte['debloque']:
        flash(f"🔒 Termine d'abord la carte précédente.", "warning")
        return redirect(url_for('cartes_tarot', theme_id=theme.id))

    return render_template('recruteur/carte_tarot_detail.html',
                           theme=theme, formation=formation,
                           exercices=carte['exercices'],
                           mes_reponses=carte['reponses'])


# ============================================================
#   FORMATIONS (Astro / Numérologie)
# ============================================================

@app.route('/formation/<int:theme_id>')
@login_required
@role_required('recruteur', 'formateur', 'admin')
def voir_formation(theme_id):
    theme = Theme.query.get_or_404(theme_id)

    # Si c'est le Tarot, rediriger vers la vue cartes
    if theme.nom == 'Tarot de Marseille':
        if current_user.role == 'recruteur':
            return redirect(url_for('cartes_tarot', theme_id=theme_id))

    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    return render_template('recruteur/formation.html',
                           theme=theme, formations=formations)


@app.route('/formation-carte/<int:formation_id>')
@login_required
@role_required('recruteur', 'formateur', 'admin')
def lire_formation_carte(formation_id):
    f = Formation.query.get_or_404(formation_id)

    if current_user.role == 'recruteur' and f.theme.nom == 'Tarot de Marseille':
        cartes = progression_tarot(current_user.id, f.theme_id)
        carte = next((c for c in cartes if c['niveau'] == f.ordre), None)
        if not carte or not carte['debloque']:
            flash("🔒 Cette carte est verrouillée.", "warning")
            return redirect(url_for('cartes_tarot', theme_id=f.theme_id))

    return render_template('recruteur/formation_detail.html', formation=f)


# ============================================================
#   EXERCICES (Astro / Numérologie)
# ============================================================

@app.route('/exercices/<int:theme_id>')
@login_required
@role_required('recruteur')
def liste_exercices(theme_id):
    theme = Theme.query.get_or_404(theme_id)

    # Rediriger vers les cartes si c'est le Tarot
    if theme.nom == 'Tarot de Marseille':
        return redirect(url_for('cartes_tarot', theme_id=theme_id))

    exercices = Exercice.query.filter_by(theme_id=theme_id)\
                              .order_by(Exercice.ordre).all()
    mes_reponses = {r.exercice_id: r for r in
                    ReponseExercice.query.filter_by(user_id=current_user.id).all()}

    return render_template('recruteur/exercices.html',
                           theme=theme, exercices=exercices,
                           mes_reponses=mes_reponses)


@app.route('/exercice/<int:exercice_id>', methods=['GET', 'POST'])
@login_required
@role_required('recruteur')
def passer_exercice(exercice_id):
    ex = Exercice.query.get_or_404(exercice_id)

    # Vérifier déblocage si c'est le Tarot
    if ex.theme.nom == 'Tarot de Marseille':
        cartes = progression_tarot(current_user.id, ex.theme_id)
        carte = next((c for c in cartes if c['niveau'] == ex.niveau), None)
        if not carte or not carte['debloque']:
            flash("🔒 Ce niveau est verrouillé.", "warning")
            return redirect(url_for('cartes_tarot', theme_id=ex.theme_id))

    reponse = ReponseExercice.query.filter_by(
        exercice_id=exercice_id, user_id=current_user.id
    ).first()

    if request.method == 'POST':
        if not reponse:
            reponse = ReponseExercice(
                exercice_id=exercice_id,
                user_id=current_user.id
            )
            db.session.add(reponse)

        reponse.reponse_client = request.form.get('reponse_client')
        reponse.explication = request.form.get('explication')
        reponse.statut = 'en_attente'
        reponse.date_soumission = datetime.utcnow()
        db.session.commit()

        flash("✅ Réponse envoyée ! Ton formateur va la corriger.", "success")

        if ex.theme.nom == 'Tarot de Marseille':
            return redirect(url_for('voir_carte_tarot',
                                    formation_id=ex.theme.formations[0].id
                                    if ex.theme.formations else 0))
        return redirect(url_for('liste_exercices', theme_id=ex.theme_id))

    return render_template('recruteur/exercice_detail.html',
                           ex=ex, reponse=reponse)


# ============================================================
#   FORMATEUR
# ============================================================

@app.route('/formateur')
@login_required
@role_required('formateur')
def formateur_dashboard():
    recruteurs = User.query.filter_by(formateur_id=current_user.id,
                                      role='recruteur').all()
    data = []
    for r in recruteurs:
        tentatives = Tentative.query.filter_by(user_id=r.id)\
                                    .order_by(Tentative.date_passage.desc()).all()
        moy = round(sum(t.score for t in tentatives) / len(tentatives)) if tentatives else 0
        data.append({'recruteur': r, 'tentatives': tentatives, 'moyenne': moy})
    return render_template('formateur/dashboard.html', data=data)


@app.route('/formateur/corrections')
@login_required
@role_required('formateur')
def formateur_corrections():
    mes_recruteurs_ids = [u.id for u in User.query.filter_by(
        formateur_id=current_user.id, role='recruteur').all()]

    reponses = ReponseExercice.query.filter(
        ReponseExercice.user_id.in_(mes_recruteurs_ids)
    ).order_by(ReponseExercice.date_soumission.desc()).all()

    return render_template('formateur/corrections.html', reponses=reponses)


@app.route('/formateur/correction/<int:rep_id>', methods=['GET', 'POST'])
@login_required
@role_required('formateur')
def corriger_reponse(rep_id):
    rep = ReponseExercice.query.get_or_404(rep_id)

    if rep.user.formateur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('formateur_corrections'))

    if request.method == 'POST':
        rep.note = int(request.form.get('note', 0))
        rep.commentaire_formateur = request.form.get('commentaire')
        rep.statut = 'corrige'
        rep.valide = (rep.note >= 10)
        rep.date_correction = datetime.utcnow()
        db.session.commit()

        if rep.valide:
            flash(f"✅ Note {rep.note}/20 — Niveau suivant débloqué !", "success")
        else:
            flash(f"⚠️ Note {rep.note}/20 — L'élève doit refaire ce niveau.", "warning")

        return redirect(url_for('formateur_corrections'))

    return render_template('formateur/correction_detail.html', rep=rep)


# ============================================================
#   ADMIN
# ============================================================

@app.route('/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    stats = {
        'users': User.query.count(),
        'recruteurs': User.query.filter_by(role='recruteur').count(),
        'formateurs': User.query.filter_by(role='formateur').count(),
        'themes': Theme.query.count(),
        'questions': Question.query.count(),
        'exercices': Exercice.query.count(),
        'tentatives': Tentative.query.count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    users = User.query.all()
    formateurs = User.query.filter_by(role='formateur').all()
    return render_template('admin/users.html', users=users, formateurs=formateurs)


@app.route('/admin/users/create', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'recruteur')
    formateur_id = request.form.get('formateur_id') or None

    if User.query.filter_by(username=username).first():
        flash("Nom d'utilisateur déjà pris.", "danger")
        return redirect(url_for('admin_users'))

    user = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role=role,
        formateur_id=int(formateur_id) if formateur_id else None
    )
    db.session.add(user)
    db.session.commit()
    flash(f"Utilisateur {username} créé.", "success")
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:uid>/toggle')
@login_required
@role_required('admin')
def admin_toggle_user(uid):
    u = User.query.get_or_404(uid)
    u.actif = not u.actif
    db.session.commit()
    return redirect(url_for('admin_users'))


@app.route('/admin/themes', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_themes():
    if request.method == 'POST':
        nom = request.form.get('nom')
        description = request.form.get('description')
        icone = request.form.get('icone', 'bi-book')
        couleur = request.form.get('couleur', '#6f42c1')
        db.session.add(Theme(nom=nom, description=description,
                             icone=icone, couleur=couleur))
        db.session.commit()
        flash("Thème créé.", "success")
        return redirect(url_for('admin_themes'))
    themes = Theme.query.all()
    return render_template('admin/themes.html', themes=themes)


@app.route('/admin/formations', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_formations():
    if request.method == 'POST':
        f = Formation(
            titre=request.form.get('titre'),
            contenu=request.form.get('contenu'),
            theme_id=int(request.form.get('theme_id')),
            ordre=int(request.form.get('ordre', 1))
        )
        db.session.add(f)
        db.session.commit()
        flash("Formation ajoutée.", "success")
        return redirect(url_for('admin_formations'))
    themes = Theme.query.all()
    formations = Formation.query.order_by(Formation.theme_id, Formation.ordre).all()
    return render_template('admin/formations.html',
                           themes=themes, formations=formations)


@app.route('/admin/exercices', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'formateur')
def admin_exercices():
    if request.method == 'POST':
        ex = Exercice(
            titre=request.form.get('titre'),
            domaine=request.form.get('domaine'),
            niveau=int(request.form.get('niveau', 1)),
            enonce=request.form.get('enonce'),
            donnees=request.form.get('donnees'),
            mots_cles=request.form.get('mots_cles'),
            reponse_attendue=request.form.get('reponse_attendue'),
            theme_id=int(request.form.get('theme_id')),
            ordre=int(request.form.get('ordre', 1))
        )
        db.session.add(ex)
        db.session.commit()
        flash("✅ Exercice ajouté.", "success")
        return redirect(url_for('admin_exercices'))

    themes = Theme.query.all()
    exercices = Exercice.query.order_by(Exercice.theme_id, Exercice.niveau).all()
    return render_template('admin/exercices.html',
                           themes=themes, exercices=exercices)


@app.route('/admin/exercices/<int:ex_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'formateur')
def admin_edit_exercice(ex_id):
    ex = Exercice.query.get_or_404(ex_id)

    if request.method == 'POST':
        ex.titre = request.form.get('titre')
        ex.domaine = request.form.get('domaine')
        ex.niveau = int(request.form.get('niveau', 1))
        ex.enonce = request.form.get('enonce')
        ex.donnees = request.form.get('donnees')
        ex.mots_cles = request.form.get('mots_cles')
        ex.reponse_attendue = request.form.get('reponse_attendue')
        ex.theme_id = int(request.form.get('theme_id'))
        ex.ordre = int(request.form.get('ordre', 1))
        db.session.commit()
        flash("✅ Exercice modifié.", "success")
        return redirect(url_for('admin_exercices'))

    themes = Theme.query.all()
    return render_template('admin/exercice_edit.html', ex=ex, themes=themes)


@app.route('/admin/exercices/<int:ex_id>/delete')
@login_required
@role_required('admin')
def admin_delete_exercice(ex_id):
    ex = Exercice.query.get_or_404(ex_id)
    db.session.delete(ex)
    db.session.commit()
    flash("🗑️ Exercice supprimé.", "success")
    return redirect(url_for('admin_exercices'))


# ============================================================
#   INIT
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)