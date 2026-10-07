import os
from flask import Flask, render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import random, json
from datetime import datetime

from config import Config
from models import (db, User, Theme, Formation, Question, Tentative,
                    Exercice, ReponseExercice, CarteValidee, RendezVous)
from mail_service import (init_mail, email_bienvenue_candidat,
                          email_rdv_candidat, email_rdv_recruteur,
                          email_felicitations, email_rdv_annule)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)
init_mail(app)

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
    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    exercices_all = Exercice.query.filter_by(theme_id=theme_id)\
                                  .order_by(Exercice.niveau, Exercice.ordre).all()

    ex_par_niveau = {}
    for ex in exercices_all:
        niv = ex.niveau or 1
        ex_par_niveau.setdefault(niv, []).append(ex)

    mes_rep = {r.exercice_id: r for r in
               ReponseExercice.query.filter_by(user_id=user_id).all()}

    cartes_val = {cv.niveau: cv for cv in
                  CarteValidee.query.filter_by(
                      user_id=user_id, theme_id=theme_id).all()}

    resultat = []
    precedent_valide = True

    for f in formations:
        niv = f.ordre
        exs = ex_par_niveau.get(niv, [])
        reps = {ex.id: mes_rep[ex.id] for ex in exs if ex.id in mes_rep}

        nb_faits = len(reps)
        nb_total = len(exs)
        tous_faits = (nb_faits == nb_total and nb_total > 0)

        notes = [r.note for r in reps.values() if r.note is not None]
        moyenne = round(sum(notes) / len(notes), 2) if notes else None

        tous_valides = (tous_faits and moyenne is not None and moyenne >= 10)

        carte_validee = cartes_val.get(niv)
        valide = tous_valides

        if valide and not carte_validee:
            carte_validee = CarteValidee(
                user_id=user_id, theme_id=theme_id,
                niveau=niv, moyenne=moyenne, validee=True
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
        precedent_valide = valide

    return resultat


def verifier_fin_formation(user_id):
    """Vérifie si un candidat a terminé TOUTE sa formation (toutes les cartes Tarot validées)."""
    theme_tarot = Theme.query.filter_by(nom='Tarot de Marseille').first()
    if not theme_tarot:
        return False

    total_cartes = Formation.query.filter_by(theme_id=theme_tarot.id).count()
    if total_cartes == 0:
        return False

    cartes_validees = CarteValidee.query.filter_by(
        user_id=user_id, theme_id=theme_tarot.id, validee=True
    ).count()

    return cartes_validees >= total_cartes


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
    elif current_user.role == 'recruteur':
        return redirect(url_for('recruteur_dash'))
    elif current_user.role == 'candidat':
        return redirect(url_for('candidat_dashboard'))
    return redirect(url_for('login'))


# ============================================================
#   CANDIDAT
# ============================================================

@app.route('/candidat')
@login_required
@role_required('candidat')
def candidat_dashboard():
    themes = Theme.query.all()
    scores = {}
    for t in themes:
        best = Tentative.query.filter_by(user_id=current_user.id, theme_id=t.id)\
                              .order_by(Tentative.score.desc()).first()
        scores[t.id] = best
    return render_template('recruteur/dashboard.html', themes=themes, scores=scores)


# ============================================================
#   TAROT
# ============================================================

@app.route('/cartes-tarot/<int:theme_id>')
@login_required
@role_required('candidat')
def cartes_tarot(theme_id):
    theme = Theme.query.get_or_404(theme_id)
    if theme.nom != 'Tarot de Marseille':
        flash("Cette page est réservée au Tarot de Marseille.", "warning")
        return redirect(url_for('candidat_dashboard'))
    cartes = calculer_progression_tarot(current_user.id, theme_id)
    return render_template('recruteur/cartes_tarot.html',
                           theme=theme, cartes=cartes)


@app.route('/carte-tarot/<int:formation_id>')
@login_required
@role_required('candidat')
def voir_carte_tarot(formation_id):
    formation = Formation.query.get_or_404(formation_id)
    theme = formation.theme
    if theme.nom != 'Tarot de Marseille':
        return redirect(url_for('voir_formation', theme_id=theme.id))

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
@role_required('candidat')
def refaire_carte(theme_id, niveau):
    theme = Theme.query.get_or_404(theme_id)
    if theme.nom != 'Tarot de Marseille':
        return redirect(url_for('candidat_dashboard'))

    exercices = Exercice.query.filter_by(theme_id=theme_id, niveau=niveau).all()
    ids_exercices = [ex.id for ex in exercices]

    ReponseExercice.query.filter(
        ReponseExercice.user_id == current_user.id,
        ReponseExercice.exercice_id.in_(ids_exercices)
    ).delete(synchronize_session=False)

    CarteValidee.query.filter_by(
        user_id=current_user.id, theme_id=theme_id, niveau=niveau
    ).delete()

    db.session.commit()

    flash(f"♻️ Carte {niveau} réinitialisée. Tu peux refaire les tests.", "info")
    f = Formation.query.filter_by(theme_id=theme_id, ordre=niveau).first()
    return redirect(url_for('voir_carte_tarot', formation_id=f.id))


# ============================================================
#   TEST — Mode examen + IA
# ============================================================

@app.route('/test/<int:exercice_id>', methods=['GET', 'POST'])
@login_required
@role_required('candidat')
def passer_test(exercice_id):
    ex = Exercice.query.get_or_404(exercice_id)

    if ex.theme.nom == 'Tarot de Marseille':
        cartes = calculer_progression_tarot(current_user.id, ex.theme_id)
        carte = next((c for c in cartes if c['niveau'] == ex.niveau), None)
        if not carte or not carte['debloque']:
            flash("🔒 Ce test est verrouillé.", "warning")
            return redirect(url_for('cartes_tarot', theme_id=ex.theme_id))

    deja = ReponseExercice.query.filter_by(
        exercice_id=exercice_id, user_id=current_user.id
    ).first()

    if deja and deja.valide:
        flash("✅ Tu as déjà validé ce test.", "info")
        if ex.theme.nom == 'Tarot de Marseille':
            f = Formation.query.filter_by(theme_id=ex.theme_id, ordre=ex.niveau).first()
            return redirect(url_for('voir_carte_tarot', formation_id=f.id))
        return redirect(url_for('liste_exercices', theme_id=ex.theme_id))

    if request.method == 'GET':
        session[f'test_debut_{exercice_id}'] = datetime.utcnow().timestamp()
        return render_template('recruteur/test_examen.html', ex=ex)

    debut_ts = session.get(f'test_debut_{exercice_id}', 0)
    duree = int(datetime.utcnow().timestamp() - debut_ts) if debut_ts else 0

    reponse_txt = request.form.get('reponse_client', '').strip()
    explication_txt = request.form.get('explication', '').strip()

    if not reponse_txt:
        flash("⚠️ Tu dois rédiger une réponse.", "warning")
        return redirect(url_for('passer_test', exercice_id=exercice_id))

    from ia_service import corriger_reponse
    resultat_ia = corriger_reponse(
        question=ex.enonce,
        mots_cles=ex.mots_cles or '',
        reponse_attendue=ex.reponse_attendue or '',
        reponse_recruteur=reponse_txt,
        explication_recruteur=explication_txt
    )

    note = resultat_ia['note']

    cle_triche = f'triche_{current_user.id}_{exercice_id}'
    triches = session.get(cle_triche, [])
    nb_triches = len(triches)

    if nb_triches >= 3:
        note = 0
        resultat_ia['commentaire'] = (
            f"🚫 TRICHE DÉTECTÉE ({nb_triches} tentatives). Note mise à 0. "
            f"Tentatives : {', '.join(triches)}. " + resultat_ia.get('commentaire', '')
        )
    elif nb_triches >= 1:
        note = max(0, note - 5 * nb_triches)
        resultat_ia['commentaire'] = (
            f"⚠️ {nb_triches} tentative(s) de triche — pénalité de {5*nb_triches} points. "
            + resultat_ia.get('commentaire', '')
        )

    valide = (note >= 10)
    session.pop(cle_triche, None)

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
    deja.correcteur_id = None
    deja.date_soumission = datetime.utcnow()
    deja.date_correction = datetime.utcnow()
    db.session.commit()

    session.pop(f'test_debut_{exercice_id}', None)

    carte_info = None
    if ex.theme.nom == 'Tarot de Marseille':
        cartes = calculer_progression_tarot(current_user.id, ex.theme_id)
        carte_info = next((c for c in cartes if c['niveau'] == ex.niveau), None)

        # 🏆 FÉLICITATIONS si fin de formation
        if valide and verifier_fin_formation(current_user.id):
            if not current_user.email_fin_formation_envoye:
                try:
                    email_felicitations(
                        current_user,
                        formateur=current_user.formateur,
                        recruteur=current_user.recruteur
                    )
                    current_user.email_fin_formation_envoye = True
                    db.session.commit()
                    flash("🏆 Félicitations ! Un email de fin de formation t'a été envoyé.", "success")
                except Exception as e:
                    print(f"⚠️  Erreur email félicitations : {e}")

    return render_template('recruteur/resultat_test.html',
                           ex=ex, note=note, valide=valide, duree=duree,
                           resultat=resultat_ia,
                           reponse_recruteur=reponse_txt,
                           carte_info=carte_info)


@app.route('/signaler_triche', methods=['POST'])
@login_required
@role_required('candidat')
def signaler_triche():
    data = request.get_json()
    ex_id = data.get('exercice_id')
    type_triche = data.get('type')

    cle = f'triche_{current_user.id}_{ex_id}'
    liste = session.get(cle, [])
    liste.append(type_triche)
    session[cle] = liste

    return jsonify({'ok': True, 'total': len(liste)})


# ============================================================
#   FORMATIONS
# ============================================================

@app.route('/formation/<int:theme_id>')
@login_required
@role_required('candidat', 'formateur', 'admin')
def voir_formation(theme_id):
    theme = Theme.query.get_or_404(theme_id)
    if theme.nom == 'Tarot de Marseille' and current_user.role == 'candidat':
        return redirect(url_for('cartes_tarot', theme_id=theme_id))

    formations = Formation.query.filter_by(theme_id=theme_id)\
                                .order_by(Formation.ordre).all()
    return render_template('recruteur/formation.html',
                           theme=theme, formations=formations)


@app.route('/exercices/<int:theme_id>')
@login_required
@role_required('candidat')
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
    candidats = User.query.filter_by(formateur_id=current_user.id,
                                     role='candidat').all()
    data = []
    for c in candidats:
        tentatives = Tentative.query.filter_by(user_id=c.id)\
                                    .order_by(Tentative.date_passage.desc()).all()
        moy = round(sum(t.score for t in tentatives) / len(tentatives)) if tentatives else 0
        data.append({'recruteur': c, 'tentatives': tentatives, 'moyenne': moy})
    return render_template('formateur/dashboard.html', data=data)


@app.route('/formateur/corrections')
@login_required
@role_required('formateur', 'admin')
def formateur_corrections():
    if current_user.role == 'admin':
        reponses = ReponseExercice.query\
                                  .order_by(ReponseExercice.date_soumission.desc()).all()
    else:
        mes_candidats_ids = [u.id for u in User.query.filter_by(
            formateur_id=current_user.id, role='candidat').all()]
        reponses = ReponseExercice.query.filter(
            ReponseExercice.user_id.in_(mes_candidats_ids)
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
        rep.correcteur_id = current_user.id
        rep.date_correction = datetime.utcnow()
        db.session.commit()

        flash(f"✅ Note {rep.note}/20 enregistrée.", "success")
        return redirect(url_for('formateur_corrections'))

    return render_template('formateur/correction_detail.html', rep=rep)


@app.route('/formateur/candidat/<int:candidat_id>')
@login_required
@role_required('formateur', 'admin')
def formateur_voir_candidat(candidat_id):
    candidat = User.query.get_or_404(candidat_id)
    if current_user.role == 'formateur' and candidat.formateur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('formateur_dashboard'))

    reponses = ReponseExercice.query.filter_by(user_id=candidat_id)\
                                    .order_by(ReponseExercice.date_soumission.desc()).all()

    stats = {
        'total': len(reponses),
        'validees': sum(1 for r in reponses if r.valide),
        'en_attente': sum(1 for r in reponses if r.statut == 'en_attente'),
        'note_moyenne': round(sum(r.note for r in reponses if r.note is not None) /
                              len([r for r in reponses if r.note is not None]), 2)
                        if any(r.note for r in reponses) else 0,
    }

    par_theme = {}
    for r in reponses:
        theme_nom = r.exercice.theme.nom
        par_theme.setdefault(theme_nom, []).append(r)

    return render_template('formateur/candidat_detail.html',
                           candidat=candidat, reponses=reponses,
                           stats=stats, par_theme=par_theme)


@app.route('/formateur/reponse/<int:rep_id>')
@login_required
@role_required('formateur', 'admin')
def formateur_voir_reponse(rep_id):
    rep = ReponseExercice.query.get_or_404(rep_id)
    if current_user.role == 'formateur' and rep.user.formateur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('formateur_dashboard'))
    return render_template('formateur/reponse_detail.html', rep=rep)


@app.route('/formateur/reponse/<int:rep_id>/override', methods=['POST'])
@login_required
@role_required('formateur', 'admin')
def formateur_override_reponse(rep_id):
    rep = ReponseExercice.query.get_or_404(rep_id)
    if current_user.role == 'formateur' and rep.user.formateur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('formateur_dashboard'))

    ancienne_note = rep.note
    try:
        nouvelle_note = int(request.form.get('note', rep.note or 0))
        nouvelle_note = max(0, min(20, nouvelle_note))
    except ValueError:
        nouvelle_note = rep.note or 0

    rep.note = nouvelle_note
    rep.commentaire_formateur = request.form.get('commentaire_formateur', '')
    rep.statut = 'corrige'
    rep.valide = (nouvelle_note >= 10)
    rep.corrige_par_ia = False
    rep.correcteur_id = current_user.id
    rep.date_correction = datetime.utcnow()
    db.session.commit()

    flash(f"✅ Note modifiée : {ancienne_note}/20 → {nouvelle_note}/20", "success")
    return redirect(url_for('formateur_voir_reponse', rep_id=rep_id))


# ============================================================
#   RECRUTEUR — Gestion des candidats
# ============================================================

@app.route('/recruteur-dash')
@login_required
@role_required('recruteur')
def recruteur_dash():
    candidats = User.query.filter_by(recruteur_id=current_user.id,
                                     role='candidat').all()

    data = []
    for c in candidats:
        data.append({
            'candidat': c,
            'formateur': c.formateur,
        })

    formateurs = User.query.filter_by(role='formateur').all()

    rdvs_a_venir = RendezVous.query.filter_by(recruteur_id=current_user.id)\
                                  .filter(RendezVous.date_heure >= datetime.utcnow())\
                                  .filter(RendezVous.statut == 'planifie')\
                                  .order_by(RendezVous.date_heure.asc())\
                                  .limit(5).all()

    return render_template('recruteur/dashboard_recruteur.html',
                           data=data, formateurs=formateurs,
                           rdvs_a_venir=rdvs_a_venir)


@app.route('/recruteur/creer-candidat', methods=['POST'])
@login_required
@role_required('recruteur')
def recruteur_creer_candidat():
    """Créer un nouveau candidat + envoyer email de bienvenue avec mot de passe."""
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    formateur_id = request.form.get('formateur_id') or None

    if User.query.filter_by(username=username).first():
        flash("Nom d'utilisateur déjà pris.", "danger")
        return redirect(url_for('recruteur_dash'))

    candidat = User(
        username=username,
        email=email,
        password=generate_password_hash(password),
        role='candidat',
        formateur_id=int(formateur_id) if formateur_id else None,
        recruteur_id=current_user.id,
    )
    db.session.add(candidat)
    db.session.commit()

    try:
        formateur = candidat.formateur
        envoye = email_bienvenue_candidat(candidat, formateur, password)
        if envoye:
            flash(f"✅ Candidat {username} créé et email envoyé à {email}.", "success")
        else:
            flash(f"✅ Candidat {username} créé (⚠️ email non envoyé).", "warning")
    except Exception as e:
        print(f"⚠️  Erreur email : {e}")
        flash(f"✅ Candidat {username} créé (⚠️ email non envoyé).", "warning")

    return redirect(url_for('recruteur_dash'))


@app.route('/recruteur/candidat/<int:candidat_id>')
@login_required
@role_required('recruteur')
def recruteur_voir_candidat(candidat_id):
    candidat = User.query.get_or_404(candidat_id)
    if candidat.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_dash'))
    return render_template('recruteur/candidat_detail.html',
                           candidat=candidat)


@app.route('/recruteur/candidat/<int:candidat_id>/supprimer')
@login_required
@role_required('recruteur')
def recruteur_supprimer_candidat(candidat_id):
    candidat = User.query.get_or_404(candidat_id)
    if candidat.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_dash'))

    candidat.actif = False
    db.session.commit()
    flash(f"✅ Candidat {candidat.username} désactivé.", "success")
    return redirect(url_for('recruteur_dash'))


# ============================================================
#   ADMIN
# ============================================================

@app.route('/admin')
@login_required
@role_required('admin', 'formateur')
def admin_dashboard():
    stats = {
        'Utilisateurs': User.query.count(),
        'Candidats': User.query.filter_by(role='candidat').count(),
        'Recruteurs': User.query.filter_by(role='recruteur').count(),
        'Formateurs': User.query.filter_by(role='formateur').count(),
        'Thèmes': Theme.query.count(),
        'Questions': Question.query.count(),
        'Exercices': Exercice.query.count(),
        'Tentatives': Tentative.query.count(),
    }
    return render_template('admin/dashboard.html', stats=stats)


@app.route('/admin/users')
@login_required
@role_required('admin')
def admin_users():
    users = User.query.all()
    formateurs = User.query.filter_by(role='formateur').all()
    recruteurs = User.query.filter_by(role='recruteur').all()
    return render_template('admin/users.html', users=users,
                           formateurs=formateurs, recruteurs=recruteurs)


@app.route('/admin/users/create', methods=['POST'])
@login_required
@role_required('admin')
def admin_create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'candidat')
    formateur_id = request.form.get('formateur_id') or None
    recruteur_id = request.form.get('recruteur_id') or None

    if User.query.filter_by(username=username).first():
        flash("Nom d'utilisateur déjà pris.", "danger")
        return redirect(url_for('admin_users'))

    user = User(
        username=username, email=email,
        password=generate_password_hash(password),
        role=role,
        formateur_id=int(formateur_id) if formateur_id else None,
        recruteur_id=int(recruteur_id) if recruteur_id else None,
    )
    db.session.add(user)
    db.session.commit()

    if role == 'candidat':
        try:
            envoye = email_bienvenue_candidat(user, user.formateur, password)
            if envoye:
                flash(f"✅ Utilisateur {username} créé et email envoyé.", "success")
            else:
                flash(f"✅ Utilisateur {username} créé (⚠️ email non envoyé).", "warning")
        except Exception as e:
            print(f"⚠️  Erreur email : {e}")
            flash(f"✅ Utilisateur {username} créé (⚠️ email non envoyé).", "warning")
    else:
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
@role_required('admin', 'formateur')
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
@role_required('admin', 'formateur')
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
#   ALIAS
# ============================================================

@app.route('/recruteur-old')
@login_required
@role_required('candidat')
def recruteur_dashboard():
    return redirect(url_for('candidat_dashboard'))


# ============================================================
#   RECRUTEUR — Calendrier & RDV
# ============================================================

@app.route('/recruteur/calendrier')
@login_required
@role_required('recruteur')
def recruteur_calendrier():
    mois = request.args.get('mois', type=int) or datetime.utcnow().month
    annee = request.args.get('annee', type=int) or datetime.utcnow().year

    from calendar import monthrange, monthcalendar
    from datetime import date
    premier_jour = datetime(annee, mois, 1)
    dernier_jour_num = monthrange(annee, mois)[1]
    dernier_jour = datetime(annee, mois, dernier_jour_num, 23, 59, 59)

    rdvs = RendezVous.query.filter_by(recruteur_id=current_user.id)\
                           .filter(RendezVous.date_heure >= premier_jour)\
                           .filter(RendezVous.date_heure <= dernier_jour)\
                           .order_by(RendezVous.date_heure).all()

    rdvs_par_jour = {}
    for r in rdvs:
        jour = r.date_heure.day
        rdvs_par_jour.setdefault(jour, []).append(r)

    semaines = monthcalendar(annee, mois)

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    mois_prec = mois - 1 if mois > 1 else 12
    annee_prec = annee if mois > 1 else annee - 1
    mois_suiv = mois + 1 if mois < 12 else 1
    annee_suiv = annee if mois < 12 else annee + 1

    return render_template('recruteur/calendrier.html',
                           rdvs_par_jour=rdvs_par_jour,
                           semaines=semaines,
                           mois=mois, annee=annee,
                           mois_nom=mois_noms[mois],
                           mois_prec=mois_prec, annee_prec=annee_prec,
                           mois_suiv=mois_suiv, annee_suiv=annee_suiv,
                           aujourd_hui=date.today())


@app.route('/recruteur/nouveau-rdv/<int:candidat_id>', methods=['GET', 'POST'])
@login_required
@role_required('recruteur')
def recruteur_nouveau_rdv(candidat_id):
    candidat = User.query.get_or_404(candidat_id)

    if candidat.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_dash'))

    if request.method == 'POST':
        try:
            date_str = request.form.get('date')
            heure_str = request.form.get('heure')

            date_heure = datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")

            rdv = RendezVous(
                recruteur_id=current_user.id,
                candidat_id=candidat_id,
                date_heure=date_heure,
                duree_minutes=int(request.form.get('duree', 30)),
                type_rdv=request.form.get('type_rdv', 'Entretien'),
                notes=request.form.get('notes', ''),
                statut='planifie'
            )
            db.session.add(rdv)
            db.session.commit()

            try:
                email_rdv_candidat(candidat, rdv, current_user)
                email_rdv_recruteur(candidat, rdv, current_user)
                flash(f"✅ RDV planifié et emails envoyés.", "success")
            except Exception as e:
                print(f"⚠️  Erreur email : {e}")
                flash(f"✅ RDV planifié (⚠️ emails non envoyés).", "warning")

            return redirect(url_for('recruteur_calendrier'))
        except ValueError as e:
            flash(f"❌ Date/heure invalide : {e}", "danger")

    return render_template('recruteur/nouveau_rdv.html', candidat=candidat)


@app.route('/recruteur/rdv/<int:rdv_id>')
@login_required
@role_required('recruteur', 'admin')
def recruteur_voir_rdv(rdv_id):
    rdv = RendezVous.query.get_or_404(rdv_id)
    if current_user.role == 'recruteur' and rdv.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_calendrier'))
    return render_template('recruteur/rdv_detail.html', rdv=rdv)


@app.route('/recruteur/rdv/<int:rdv_id>/statut', methods=['POST'])
@login_required
@role_required('recruteur', 'admin')
def recruteur_changer_statut_rdv(rdv_id):
    rdv = RendezVous.query.get_or_404(rdv_id)
    if current_user.role == 'recruteur' and rdv.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_calendrier'))

    ancien_statut = rdv.statut
    nouveau_statut = request.form.get('statut')

    if nouveau_statut in ['planifie', 'termine', 'annule']:
        rdv.statut = nouveau_statut
        db.session.commit()

        # 🆕 Email d'annulation si le statut passe à "annule"
        if nouveau_statut == 'annule' and ancien_statut != 'annule':
            try:
                email_rdv_annule(rdv.candidat, rdv, rdv.recruteur)
                flash("✅ Statut mis à jour. Email d'annulation envoyé au candidat.", "success")
            except Exception as e:
                print(f"⚠️  Erreur email : {e}")
                flash("✅ Statut mis à jour (⚠️ email non envoyé).", "warning")
        else:
            flash(f"✅ Statut du RDV mis à jour : {nouveau_statut}.", "success")

    return redirect(url_for('recruteur_voir_rdv', rdv_id=rdv_id))


@app.route('/recruteur/rdv/<int:rdv_id>/supprimer')
@login_required
@role_required('recruteur')
def recruteur_supprimer_rdv(rdv_id):
    rdv = RendezVous.query.get_or_404(rdv_id)
    if rdv.recruteur_id != current_user.id:
        flash("Accès refusé.", "danger")
        return redirect(url_for('recruteur_calendrier'))

    db.session.delete(rdv)
    db.session.commit()
    flash("🗑️ RDV supprimé.", "success")
    return redirect(url_for('recruteur_calendrier'))


# ============================================================
#   FORMATEUR — Voir les RDV
# ============================================================

@app.route('/formateur/rdv')
@login_required
@role_required('formateur')
def formateur_rdv():
    candidats_ids = [u.id for u in User.query.filter_by(
        formateur_id=current_user.id, role='candidat').all()]

    rdvs = RendezVous.query.filter(RendezVous.candidat_id.in_(candidats_ids))\
                           .order_by(RendezVous.date_heure.desc()).all()

    return render_template('formateur/rdv.html', rdvs=rdvs)


# ============================================================
#   ADMIN — RDV
# ============================================================

@app.route('/admin/rdv')
@login_required
@role_required('admin')
def admin_rdv():
    rdvs = RendezVous.query.order_by(RendezVous.date_heure.desc()).all()

    maintenant = datetime.utcnow()
    futurs = [r for r in rdvs if r.date_heure >= maintenant and r.statut == 'planifie']
    passes = [r for r in rdvs if r.date_heure < maintenant or r.statut != 'planifie']

    return render_template('admin/rdv.html',
                           rdvs=rdvs, futurs=futurs, passes=passes,
                           total=len(rdvs))


@app.route('/admin/rdv/nouveau', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_nouveau_rdv():
    candidats = User.query.filter_by(role='candidat').order_by(User.username).all()
    recruteurs = User.query.filter_by(role='recruteur').all()

    if request.method == 'POST':
        try:
            candidat_id = int(request.form.get('candidat_id'))
            recruteur_id = request.form.get('recruteur_id') or None

            date_str = request.form.get('date')
            heure_str = request.form.get('heure')
            date_heure = datetime.strptime(f"{date_str} {heure_str}", "%Y-%m-%d %H:%M")

            rdv = RendezVous(
                candidat_id=candidat_id,
                recruteur_id=int(recruteur_id) if recruteur_id else current_user.id,
                date_heure=date_heure,
                duree_minutes=int(request.form.get('duree', 30)),
                type_rdv=request.form.get('type_rdv', 'Entretien'),
                notes=request.form.get('notes', ''),
                statut='planifie'
            )
            db.session.add(rdv)
            db.session.commit()

            try:
                candidat = User.query.get(candidat_id)
                recruteur = rdv.recruteur
                email_rdv_candidat(candidat, rdv, recruteur)
                email_rdv_recruteur(candidat, rdv, recruteur)
                flash(f"✅ RDV créé et emails envoyés.", "success")
            except Exception as e:
                print(f"⚠️  Erreur email : {e}")
                flash(f"✅ RDV créé (⚠️ emails non envoyés).", "warning")

            return redirect(url_for('admin_rdv'))
        except (ValueError, TypeError) as e:
            flash(f"❌ Erreur : {e}", "danger")

    return render_template('admin/nouveau_rdv.html',
                           candidats=candidats, recruteurs=recruteurs)


@app.route('/admin/rdv/<int:rdv_id>/supprimer')
@login_required
@role_required('admin')
def admin_supprimer_rdv(rdv_id):
    rdv = RendezVous.query.get_or_404(rdv_id)
    db.session.delete(rdv)
    db.session.commit()
    flash("🗑️ RDV supprimé.", "success")
    return redirect(url_for('admin_rdv'))


# ============================================================
#   ADMIN — Modifier / Supprimer utilisateur
# ============================================================

@app.route('/admin/users/<int:uid>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def admin_edit_user(uid):
    user = User.query.get_or_404(uid)

    if request.method == 'POST':
        user.username = request.form.get('username', user.username)
        user.email = request.form.get('email', user.email)

        nouveau_mdp = request.form.get('password', '').strip()
        if nouveau_mdp:
            user.password = generate_password_hash(nouveau_mdp)

        nouveau_role = request.form.get('role', user.role)
        if user.id != current_user.id:
            user.role = nouveau_role

        if user.role == 'candidat':
            formateur_id = request.form.get('formateur_id') or None
            recruteur_id = request.form.get('recruteur_id') or None
            user.formateur_id = int(formateur_id) if formateur_id else None
            user.recruteur_id = int(recruteur_id) if recruteur_id else None

        user.actif = 'actif' in request.form

        db.session.commit()
        flash(f"✅ Utilisateur {user.username} modifié.", "success")
        return redirect(url_for('admin_users'))

    formateurs = User.query.filter_by(role='formateur').all()
    recruteurs = User.query.filter_by(role='recruteur').all()

    return render_template('admin/user_edit.html',
                           user=user, formateurs=formateurs,
                           recruteurs=recruteurs)


@app.route('/admin/users/<int:uid>/delete')
@login_required
@role_required('admin')
def admin_delete_user(uid):
    user = User.query.get_or_404(uid)

    if user.id == current_user.id:
        flash("❌ Tu ne peux pas te supprimer toi-même.", "danger")
        return redirect(url_for('admin_users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f"🗑️ Utilisateur {username} supprimé.", "success")
    return redirect(url_for('admin_users'))


# ============================================================
#   INIT
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # En production, Render utilise la variable PORT
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)