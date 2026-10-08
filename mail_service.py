"""
Service d'envoi d'emails via l'API HTTP de Brevo.
Contourne le blocage SMTP de Render (ports 587/465 bloqués sur plan gratuit).
"""
import os
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from flask import current_app

# Configuration globale de l'API Brevo
_brevo_config = None


def init_mail(app):
    """Initialise l'API Brevo (appelée au démarrage)."""
    global _brevo_config
    api_key = os.environ.get('BREVO_API_KEY')
    if not api_key:
        print("⚠️  BREVO_API_KEY manquante dans les variables d'environnement")
        return

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = api_key
    _brevo_config = configuration
    print("✅ Brevo API initialisée")


def _envoyer(destinataire, sujet, corps_html):
    """Envoie un email via l'API HTTP de Brevo (non bloquée par Render)."""
    if not _brevo_config:
        print("⚠️  Brevo API non configurée — email non envoyé")
        return False

    try:
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(_brevo_config)
        )

        sender_email = os.environ.get('MAIL_FROM_EMAIL', 'noreply@example.com')
        sender_name = os.environ.get('MAIL_FROM_NAME', 'Voyance Academy')

        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": destinataire}],
            sender={"name": sender_name, "email": sender_email},
            subject=sujet,
            html_content=corps_html
        )

        api_instance.send_transac_email(send_smtp_email)
        print(f"✅ Email envoyé à {destinataire} via API Brevo")
        return True

    except ApiException as e:
        print(f"⚠️  Erreur API Brevo : {e}")
        return False
    except Exception as e:
        print(f"⚠️  Erreur inattendue email : {e}")
        return False


def _base_url():
    """Retourne l'URL de base depuis l'env (ou fallback)."""
    return os.environ.get('BASE_URL', 'http://127.0.0.1:5000')


# ═══════════════════════════════════════════════════════════
#   EMAIL : BIENVENUE CANDIDAT
# ═══════════════════════════════════════════════════════════

def email_bienvenue_candidat(candidat, formateur=None, mot_de_passe=None):
    """Email de bienvenue (via API Brevo)."""
    sujet = "🎓 Bienvenue sur Voyance Academy"

    formateur_info = ""
    if formateur:
        formateur_info = f"""
        <p style="margin: 10px 0;">
            <strong>👨‍🏫 Ton formateur :</strong><br>
            <strong>{formateur.username}</strong>
            (<a href="mailto:{formateur.email}">{formateur.email}</a>)
        </p>
        """

    if mot_de_passe:
        identifiants_html = f"""
        <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #7b1fa2; margin: 20px 0;">
            <p style="margin: 8px 0;"><strong>🔑 Nom d'utilisateur :</strong> <code style="background: #f3e5f5; padding: 3px 8px; border-radius: 5px;">{candidat.username}</code></p>
            <p style="margin: 8px 0;"><strong>🔐 Mot de passe :</strong> <code style="background: #f3e5f5; padding: 3px 8px; border-radius: 5px;">{mot_de_passe}</code></p>
            <p style="margin: 8px 0;"><strong>📧 Email :</strong> {candidat.email}</p>
        </div>
        <div style="background: #fff3cd; padding: 15px; border-radius: 10px; border-left: 4px solid #ffc107; margin: 15px 0;">
            <p style="margin: 0; font-size: 0.9rem;">
                <strong>⚠️ Important :</strong> Garde bien ce mot de passe.
            </p>
        </div>
        """
    else:
        identifiants_html = f"""
        <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #7b1fa2; margin: 20px 0;">
            <p style="margin: 8px 0;"><strong>🔑 Nom d'utilisateur :</strong> <code>{candidat.username}</code></p>
            <p style="margin: 8px 0;"><strong>📧 Email :</strong> {candidat.email}</p>
        </div>
        """

    corps = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #4a148c, #7b1fa2); color: white; padding: 30px; text-align: center; border-radius: 15px 15px 0 0;">
            <h1 style="margin: 0;">🔮 Voyance Academy</h1>
            <p style="margin: 10px 0 0 0;">Bienvenue dans ta formation</p>
        </div>
        <div style="background: #f9f5ff; padding: 30px; border-radius: 0 0 15px 15px;">
            <p>Bonjour <strong>{candidat.username}</strong>,</p>
            <p>🎉 Ton compte candidat a été créé avec succès !</p>
            <p>Voici tes identifiants :</p>
            {identifiants_html}
            {formateur_info}
            <div style="text-align: center; margin: 30px 0;">
                <a href="{_base_url()}/login" style="background: linear-gradient(135deg, #4a148c, #7b1fa2); color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; display: inline-block;">
                    🚀 Accéder à ma formation
                </a>
            </div>
            <p style="font-size: 0.9rem; color: #666;">À bientôt !<br>L'équipe Voyance Academy</p>
        </div>
    </div>
    """

    return _envoyer(candidat.email, sujet, corps)


# ═══════════════════════════════════════════════════════════
#   EMAIL : RDV PLANIFIÉ (CANDIDAT)
# ═══════════════════════════════════════════════════════════

def email_rdv_candidat(candidat, rdv, recruteur):
    """Email envoyé au candidat pour l'informer d'un RDV (via API Brevo)."""
    sujet = f"📅 RDV planifié : {rdv.date_heure.strftime('%d/%m/%Y à %H:%M')}"

    corps = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #4a148c, #7b1fa2); color: white; padding: 30px; text-align: center; border-radius: 15px 15px 0 0;">
            <h1 style="margin: 0;">📅 Rendez-vous planifié</h1>
        </div>
        <div style="background: #f9f5ff; padding: 30px; border-radius: 0 0 15px 15px;">
            <p>Bonjour <strong>{candidat.username}</strong>,</p>
            <p>Un entretien a été planifié pour toi :</p>
            <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #7b1fa2; margin: 20px 0;">
                <p style="margin: 8px 0;"><strong>📅 Date :</strong> {rdv.date_heure.strftime('%A %d %B %Y')}</p>
                <p style="margin: 8px 0;"><strong>🕐 Heure :</strong> {rdv.date_heure.strftime('%H:%M')}</p>
                <p style="margin: 8px 0;"><strong>⏱️ Durée :</strong> {rdv.duree_minutes} minutes</p>
                <p style="margin: 8px 0;"><strong>💼 Type :</strong> {rdv.type_rdv}</p>
                <p style="margin: 8px 0;"><strong>👤 Recruteur :</strong> {recruteur.username}</p>
                <p style="margin: 8px 0;"><strong>📧 Contact :</strong> <a href="mailto:{recruteur.email}">{recruteur.email}</a></p>
            </div>
            {'<p><strong>📝 Notes :</strong><br>' + rdv.notes + '</p>' if rdv.notes else ''}
            <p>Prépare-toi bien et sois à l'heure ! 🎯</p>
            <hr style="border: none; border-top: 1px solid #e0d5ec; margin: 30px 0;">
            <p style="font-size: 0.9rem; color: #666;">À bientôt,<br>L'équipe Voyance Academy</p>
        </div>
    </div>
    """

    return _envoyer(candidat.email, sujet, corps)


# ═══════════════════════════════════════════════════════════
#   EMAIL : RDV CONFIRMÉ (RECRUTEUR)
# ═══════════════════════════════════════════════════════════

def email_rdv_recruteur(candidat, rdv, recruteur):
    """Email envoyé au recruteur pour confirmer le RDV (via API Brevo)."""
    sujet = f"📅 RDV confirmé avec {candidat.username}"

    corps = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #4a148c, #7b1fa2); color: white; padding: 30px; text-align: center; border-radius: 15px 15px 0 0;">
            <h1 style="margin: 0;">✅ RDV confirmé</h1>
        </div>
        <div style="background: #f9f5ff; padding: 30px; border-radius: 0 0 15px 15px;">
            <p>Bonjour <strong>{recruteur.username}</strong>,</p>
            <p>Ton rendez-vous avec <strong>{candidat.username}</strong> est confirmé :</p>
            <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #7b1fa2; margin: 20px 0;">
                <p style="margin: 8px 0;"><strong>📅 Date :</strong> {rdv.date_heure.strftime('%A %d %B %Y')}</p>
                <p style="margin: 8px 0;"><strong>🕐 Heure :</strong> {rdv.date_heure.strftime('%H:%M')}</p>
                <p style="margin: 8px 0;"><strong>⏱️ Durée :</strong> {rdv.duree_minutes} minutes</p>
                <p style="margin: 8px 0;"><strong>👤 Candidat :</strong> {candidat.username}</p>
                <p style="margin: 8px 0;"><strong>📧 Email candidat :</strong> <a href="mailto:{candidat.email}">{candidat.email}</a></p>
            </div>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{_base_url()}/recruteur/calendrier" style="background: linear-gradient(135deg, #4a148c, #7b1fa2); color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; display: inline-block;">
                    📅 Voir mon calendrier
                </a>
            </div>
            <hr style="border: none; border-top: 1px solid #e0d5ec; margin: 30px 0;">
            <p style="font-size: 0.9rem; color: #666;">Bon entretien !<br>L'équipe Voyance Academy</p>
        </div>
    </div>
    """

    return _envoyer(recruteur.email, sujet, corps)


# ═══════════════════════════════════════════════════════════
#   EMAIL : FÉLICITATIONS
# ═══════════════════════════════════════════════════════════

def email_felicitations(candidat, formateur=None, recruteur=None):
    """Email de félicitations quand le candidat termine sa formation (via API Brevo)."""
    sujet = "🏆 Félicitations ! Tu as terminé ta formation"

    formateur_info = ""
    if formateur:
        formateur_info = f"""
        <p style="margin: 10px 0;">
            <strong>👨‍🏫 Ton formateur :</strong> {formateur.username}
            (<a href="mailto:{formateur.email}">{formateur.email}</a>)
        </p>
        """

    recruteur_info = ""
    if recruteur:
        recruteur_info = f"""
        <p style="margin: 10px 0;">
            <strong>👤 Ton recruteur :</strong> {recruteur.username}
            (<a href="mailto:{recruteur.email}">{recruteur.email}</a>)
        </p>
        """

    corps = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #f57c00, #ff9800); color: white; padding: 40px 30px; text-align: center; border-radius: 15px 15px 0 0;">
            <div style="font-size: 4rem;">🏆</div>
            <h1 style="margin: 10px 0;">Félicitations {candidat.username} !</h1>
            <p style="margin: 10px 0 0 0; font-size: 1.1rem;">Tu as terminé ta formation avec succès 🎉</p>
        </div>
        <div style="background: #fff9e6; padding: 30px; border-radius: 0 0 15px 15px;">
            <p>Bonjour <strong>{candidat.username}</strong>,</p>
            <p style="font-size: 1.05rem;">
                🎊 <strong>Bravo !</strong> Tu as validé l'ensemble de ta formation sur la plateforme Voyance Academy.
            </p>
            <div style="background: white; padding: 25px; border-radius: 10px; border-left: 5px solid #ff9800; margin: 25px 0;">
                <h3 style="margin-top: 0; color: #e65100;">🎯 Prochaine étape : Rejoins l'équipe !</h3>
                <p>Tu es maintenant <strong>officiellement prêt(e)</strong> à rejoindre notre équipe de conseillers.</p>
                <p style="margin-bottom: 0;"><strong>👨‍🏫 Formateur :</strong></p>
                {formateur_info}
                <p style="margin-bottom: 0; margin-top: 15px;"><strong>👤 Recruteur :</strong></p>
                {recruteur_info}
            </div>
            <div style="background: #e8f5e9; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <p style="margin: 0;"><strong>💼 Ce qui t'attend :</strong></p>
                <ul style="margin: 10px 0 0 20px;">
                    <li>Consultations clients (tchat, téléphone)</li>
                    <li>Utilisation quotidienne des cartes et de la numérologie</li>
                    <li>Accompagnement continu de ton formateur</li>
                </ul>
            </div>
            <p style="font-size: 1.05rem;">Nous sommes <strong>très fiers</strong> de ton parcours. Bienvenue dans l'équipe ! 🌟</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{_base_url()}/login" style="background: linear-gradient(135deg, #f57c00, #ff9800); color: white; padding: 15px 30px; text-decoration: none; border-radius: 10px; font-weight: bold; display: inline-block; font-size: 1.05rem;">
                    🚀 Accéder à mon espace
                </a>
            </div>
            <hr style="border: none; border-top: 2px dashed #ffcc80; margin: 30px 0;">
            <p style="text-align: center; color: #666;"><strong>🔮 Voyance Academy</strong><br><small>L'équipe qui croit en toi</small></p>
        </div>
    </div>
    """

    return _envoyer(candidat.email, sujet, corps)


# ═══════════════════════════════════════════════════════════
#   EMAIL : RDV ANNULÉ
# ═══════════════════════════════════════════════════════════

def email_rdv_annule(candidat, rdv, recruteur, raison=None):
    """Email envoyé au candidat quand un RDV est annulé (via API Brevo)."""
    sujet = f"❌ RDV annulé : {rdv.date_heure.strftime('%d/%m/%Y à %H:%M')}"

    raison_html = ""
    if raison:
        raison_html = f"""
        <div style="background: #ffebee; padding: 15px; border-radius: 10px; border-left: 4px solid #f44336; margin: 20px 0;">
            <p style="margin: 0;"><strong>❓ Raison :</strong> {raison}</p>
        </div>
        """

    corps = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #b71c1c, #f44336); color: white; padding: 30px; text-align: center; border-radius: 15px 15px 0 0;">
            <h1 style="margin: 0;">❌ RDV annulé</h1>
        </div>
        <div style="background: #fef2f2; padding: 30px; border-radius: 0 0 15px 15px;">
            <p>Bonjour <strong>{candidat.username}</strong>,</p>
            <p>Nous sommes désolés de t'informer que ton rendez-vous avec <strong>{recruteur.username}</strong> a été <strong>annulé</strong>.</p>
            <div style="background: white; padding: 20px; border-radius: 10px; border-left: 4px solid #f44336; margin: 20px 0;">
                <p style="margin: 8px 0;"><strong>📅 Date initiale :</strong> {rdv.date_heure.strftime('%A %d %B %Y')}</p>
                <p style="margin: 8px 0;"><strong>🕐 Heure :</strong> {rdv.date_heure.strftime('%H:%M')}</p>
                <p style="margin: 8px 0;"><strong>💼 Type :</strong> {rdv.type_rdv}</p>
                <p style="margin: 8px 0;"><strong>👤 Recruteur :</strong> {recruteur.username}</p>
                <p style="margin: 8px 0;"><strong>📧 Contact :</strong> <a href="mailto:{recruteur.email}">{recruteur.email}</a></p>
            </div>
            {raison_html}
            <p><strong>{recruteur.username}</strong> te contactera très prochainement pour fixer un nouveau rendez-vous.</p>
            <hr style="border: none; border-top: 1px solid #e0d5ec; margin: 30px 0;">
            <p style="font-size: 0.9rem; color: #666;">Cordialement,<br>L'équipe Voyance Academy</p>
        </div>
    </div>
    """

    return _envoyer(candidat.email, sujet, corps)