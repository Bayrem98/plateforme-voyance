from flask import Flask, render_template, redirect, url_for, flash, request, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random, json
from datetime import datetime

from config import Config
from models import (db, User, Theme, Formation, Question, Tentative,
                    Exercice, ReponseExercice, CarteValidee)

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
#   PROGRESSION — Logique de déblocage par carte
# ============================================================

def calculer_progression_tarot(user_id, theme_id):
    """
    Calcule l'état complet des cartes pour un utilisateur.
    La carte est validée si TOUS les exercices sont faits ET la moyenne >= 10.
    """
    # Récupérer toutes les formations (cartes) triées
    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    
    # Récupérer tous les exercices du thème, groupés par niveau
    exercices_all = Exercice.query.filter_by(theme_id=theme_id)\
                                  .order_by(Exercice.niveau, Exercice.ordre).all()
    
    ex_par_niveau = {}
    for ex in exercices_all:
        niv = ex.niveau or 1
        ex_par_niveau.setdefault(niv, []).append(ex)
    
    # Récupérer les réponses de ce user
    mes_rep = {r.exercice_id: r for r in
               ReponseExercice.query.filter_by(user_id=user_id).all()}
    
    # Récupérer les cartes validées
    cartes_val = {cv.niveau: cv for cv in
                  CarteValidee.query.filter_by(
                      user_id=user_id, theme_id=theme_id).all()}
    
    resultat = []
    precedent_valide = True  # Carte 1 toujours débloquée
    
    for f in formations:
        niv = f.ordre
        exs = ex_par_niveau.get(niv, [])
        reps = {ex.id: mes_rep[ex.id] for ex in exs if ex.id in mes_rep}
        
        # Combien de réponses ont été données ?
        nb_faits = len(reps)
        nb_total = len(exs)
        tous_faits = (nb_faits == nb_total and nb_total > 0)
        
        # Moyenne des notes
        notes = [r.note for r in reps.values() if r.note is not None]
        moyenne = round(sum(notes) / len(notes), 2) if notes else None
        
        # 🎯 Validation : tous les exercices faits ET moyenne >= 10
        tous_valides = (tous_faits 
                        and moyenne is not None 
                        and moyenne >= 10)
        
        # Carte validée
        carte_validee = cartes_val.get(niv)
        valide = tous_valides
        
        # Sauvegarder dans CarteValidee si validée et pas encore enregistrée
        if valide and not carte_validee:
            carte_validee = CarteValidee(
                user_id=user_id,
                theme_id=theme_id,
                niveau=niv,
                moyenne=moyenne,
                validee=True
            )
            db.session.add(carte_validee)
            db.session.commit()
        
        resultat.append({
            'niveau': niv,
            'formation': f,
            'exercices': exs,
            'reponses': reps,
            'nb_faits': nb_faits,
            'nb_total': nb_total,
            'tous_faits': tous_faits,
            'tous_valides': tous_valides,
            'moyenne': moyenne,
            'debloque': precedent_valide,
            'valide': valide,
            'carte_validee': carte_validee,
        })
        
        # La carte suivante est débloquée si celle-ci est validée
        precedent_valide = valide
    
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
#   TAROT — Cartes progressives
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

    cartes = calculer_progression_tarot(current_user.id, theme_id)
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
    cartes = calculer_progression_tarot(current_user.id, theme.id)
    carte = next((c for c in cartes if c['niveau'] == formation.ordre), None)

    if not carte or not carte['debloque']:
        flash("🔒 Termine d'abord la carte précédente.", "warning")
        return redirect(url_for('cartes_tarot', theme_id=theme.id))

    return render_template('recruteur/carte_tarot_detail.html',
                           theme=theme, formation=formation,
                           carte=carte,
                           exercices=carte['exercices'],
                           mes_reponses=carte['reponses'])


@app.route('/carte-tarot/<int:theme_id>/refaire/<int:niveau>')
@login_required
@role_required('recruteur')
def refaire_carte(theme_id, niveau):
    """
    Permet de refaire tous les exercices d'une carte.
    Supprime toutes les réponses du user pour les exercices de cette carte.
    """
    theme = Theme.query.get_or_404(theme_id)
    
    if theme.nom != 'Tarot de Marseille':
        return redirect(url_for('recruteur_dashboard'))
    
    # Récupérer les exercices de cette carte
    exercices = Exercice.query.filter_by(
        theme_id=theme_id, niveau=niveau
    ).all()
    
    ids_exercices = [ex.id for ex in exercices]
    
    # Supprimer les réponses du user pour ces exercices
    ReponseExercice.query.filter(
        ReponseExercice.user_id == current_user.id,
        ReponseExercice.exercice_id.in_(ids_exercices)
    ).delete(synchronize_session=False)
    
    # Supprimer aussi la CarteValidee si elle existe
    CarteValidee.query.filter_by(
        user_id=current_user.id, theme_id=theme_id, niveau=niveau
    ).delete()
    
    db.session.commit()
    
    flash(f"♻️ Carte {niveau} réinitialisée. Tu peux refaire les tests.", "info")
    return redirect(url_for('voir_carte_tarot', formation_id=Formation.query.filter_by(
        theme_id=theme_id, ordre=niveau).first().id))


# ============================================================
#   TEST — Mode examen avec correction IA
# ============================================================

@app.route('/test/<int:exercice_id>', methods=['GET', 'POST'])
@login_required
@role_required('recruteur')
def passer_test(exercice_id):
    """Mode EXAMEN : formation masquée, chrono, correction IA."""
    ex = Exercice.query.get_or_404(exercice_id)

    # Vérifier déblocage pour le Tarot
    if ex.theme.nom == 'Tarot de Marseille':
        cartes = calculer_progression_tarot(current_user.id, ex.theme_id)
        carte = next((c for c in cartes if c['niveau'] == ex.niveau), None)
        if not carte or not carte['debloque']:
            flash("🔒 Ce test est verrouillé.", "warning")
            return redirect(url_for('cartes_tarot', theme_id=ex.theme_id))

    # Vérifier si déjà validé
    deja = ReponseExercice.query.filter_by(
        exercice_id=exercice_id, user_id=current_user.id
    ).first()

    if deja and deja.valide:
        flash("✅ Tu as déjà validé ce test.", "info")
        if ex.theme.nom == 'Tarot de Marseille':
            return redirect(url_for('voir_carte_tarot',
                                    formation_id=Formation.query.filter_by(
                                        theme_id=ex.theme_id,
                                        ordre=ex.niveau).first().id))
        return redirect(url_for('liste_exercices', theme_id=ex.theme_id))

    if request.method == 'GET':
        session[f'test_debut_{exercice_id}'] = datetime.utcnow().timestamp()
        return render_template('recruteur/test_examen.html', ex=ex)

    # POST : correction IA
    debut_ts = session.get(f'test_debut_{exercice_id}', 0)
    duree = int(datetime.utcnow().timestamp() - debut_ts) if debut_ts else 0

    reponse_txt = request.form.get('reponse_client', '').strip()
    explication_txt = request.form.get('explication', '').strip()

    if not reponse_txt:
        flash("⚠️ Tu dois rédiger une réponse.", "warning")
        return redirect(url_for('passer_test', exercice_id=exercice_id))

    # Correction IA
    from ia_service import corriger_reponse
    resultat_ia = corriger_reponse(
        question=ex.enonce,
        mots_cles=ex.mots_cles or '',
        reponse_attendue=ex.reponse_attendue or '',
        reponse_recruteur=reponse_txt,
        explication_recruteur=explication_txt
    )

    note = resultat_ia['note']
    hors_sujet = resultat_ia.get('hors_sujet', False)
    
    # 🔒 Si hors-sujet → note plafonnée à 3 (sécurité)
    if hors_sujet and note > 3:
        note = 3
    
    valide = (note >= 10)

    if not deja:
        deja = ReponseExercice(exercice_id=exercice_id, user_id=current_user.id)
        db.session.add(deja)

    deja.reponse_client = reponse_txt
    deja.explication = explication_txt
    deja.note = note
    deja.commentaire_ia = resultat_ia.get('commentaire', '')
    deja.statut = 'corrige'
    deja.valide = valide
    deja.duree_secondes = duree
    deja.corrige_par_ia = True
    deja.date_soumission = datetime.utcnow()
    deja.date_correction = datetime.utcnow()
    db.session.commit()

    session.pop(f'test_debut_{exercice_id}', None)

    # Recalculer la progression de la carte
    carte_info = None
    if ex.theme.nom == 'Tarot de Marseille':
        cartes = calculer_progression_tarot(current_user.id, ex.theme_id)
        carte_info = next((c for c in cartes if c['niveau'] == ex.niveau), None)

    return render_template('recruteur/resultat_test.html',
                           ex=ex, note=note, valide=valide, duree=duree,
                           resultat=resultat_ia,
                           reponse_recruteur=reponse_txt,
                           carte_info=carte_info)


# ============================================================
#   FORMATIONS (Astro / Numérologie)
# ============================================================

@app.route('/formation/<int:theme_id>')
@login_required
@role_required('recruteur', 'formateur', 'admin')
def voir_formation(theme_id):
    theme = Theme.query.get_or_404(theme_id)

    if theme.nom == 'Tarot de Marseille' and current_user.role == 'recruteur':
        return redirect(url_for('cartes_tarot', theme_id=theme_id))

    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    return render_template('recruteur/formation.html',
                           theme=theme, formations=formations)


# ============================================================
#   EXERCICES (Astro / Numérologie)
# ============================================================

@app.route('/exercices/<int:theme_id>')
@login_required
@role_required('recruteur')
def liste_exercices(theme_id):
    theme = Theme.query.get_or_404(theme_id)

    if theme.nom == 'Tarot de Marseille':
        return redirect(url_for('cartes_tarot', theme_id=theme_id))

    exercices = Exercice.query.filter_by(theme_id=theme_id)\
                              .order_by(Exercice.ordre).all()
    mes_reponses = {r.exercice_id: r for r in
                    ReponseExercice.query.filter_by(user_id=current_user.id).all()}

    return render_template('recruteur/exercices.html',
                           theme=theme, exercices=exercices,
                           mes_reponses=mes_reponses)


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
        rep.corrige_par_ia = False
        rep.date_correction = datetime.utcnow()
        db.session.commit()

        flash(f"✅ Note {rep.note}/20 enregistrée.", "success")
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
        username=username, email=email,
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
        db.session.add(Theme(
            nom=request.form.get('nom'),
            description=request.form.get('description'),
            icone=request.form.get('icone', 'bi-book'),
            couleur=request.form.get('couleur', '#6f42c1')
        ))
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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)