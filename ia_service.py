"""
Service IA pour corriger automatiquement les exercices.
Utilise Google Gemini avec rotation de modèles.
"""
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-generativeai non installé.")


# 📌 Liste des modèles à essayer dans l'ordre
# Si un échoue (quota 429, modèle 404), on essaie le suivant
MODELES_GEMINI = [
    'gemini-3.8-flash',           # ✅ Confirmé fonctionnel
    'gemini-flash-latest',        # ✅ Fallback stable
]


def _configurer_gemini():
    """Configure Gemini et retourne la liste des modèles."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("❌ GEMINI_API_KEY manquante dans .env")
    genai.configure(api_key=api_key)
    return MODELES_GEMINI


def corriger_reponse(question, mots_cles, reponse_attendue,
                     reponse_recruteur, explication_recruteur=""):
    """
    Corrige une réponse libre avec Gemini.
    Essaie plusieurs modèles en cas d'échec.
    """
    if not GEMINI_AVAILABLE:
        print("⚠️  Gemini non disponible → fallback")
        return _correction_fallback(question, mots_cles,
                                    reponse_attendue, reponse_recruteur)

    try:
        modeles_a_essayer = _configurer_gemini()
    except Exception as e:
        print(f"⚠️  Erreur config Gemini : {e} → fallback")
        return _correction_fallback(question, mots_cles,
                                    reponse_attendue, reponse_recruteur)

    prompt = f"""Tu es un formateur TRÈS STRICT en voyance et tarot.
Tu dois corriger la réponse d'un nouveau recruteur.

⚠️ RÈGLE ABSOLUE : si la réponse du recruteur ne répond PAS à la question
posée par le client, tu DOIS mettre une note de 0 à 3 maximum,
même si des mots-clés sont présents.

EXEMPLES DE HORS-SUJET À SANCTIONNER :
- Question sur l'AMOUR → réponse qui parle de TRAVAIL/ARGENT
- Question sur le TRAVAIL → réponse qui parle d'AMOUR
- Réponse qui ne répond pas à la question posée
- Réponse vague sans lien avec la question

CONTEXTE DE L'EXERCICE :
- Domaine : {mots_cles}
- Question du client : {question}
- Réponse modèle attendue : {reponse_attendue}

RÉPONSE DU RECRUTEUR :
{reponse_recruteur}

EXPLICATION DONNÉE :
{explication_recruteur or '(non fournie)'}

CONSIGNES DE CORRECTION (STRICTES) :
1. Note sur 20.
2. **Vérifie D'ABORD que la réponse répond à LA QUESTION POSÉE.**
   Si la réponse est hors-sujet → note entre 0 et 3.
3. Ensuite, vérifie l'usage des mots-clés : {mots_cles}
4. Vérifie le ton (professionnel, empathique, adapté voyance).
5. Vérifie la clarté et l'utilité pour le client.

BARÈME :
- 16-20 : Excellent, répond parfaitement à la question
- 12-15 : Bon, quelques manques
- 10-11 : Passable (juste validé)
- 6-9 : Insuffisant
- 0-5 : Hors-sujet ou très mauvais

Réponds UNIQUEMENT en JSON valide :
{{
    "note": <entier 0-20>,
    "hors_sujet": <true/false>,
    "commentaire": "<feedback constructif en 2-3 phrases>",
    "points_forts": ["<point 1>"],
    "points_faibles": ["<point 1>"],
    "mots_cles_utilises": ["<mot 1>"],
    "mots_cles_manquants": ["<mot 1>"]
}}
"""

    # Essayer chaque modèle jusqu'à succès
    reponse = None
    derniere_erreur = None
    for nom_modele in modeles_a_essayer:
        try:
            modele = genai.GenerativeModel(nom_modele)
            reponse = modele.generate_content(
               prompt,
               request_options={"timeout": 60}  # 60 secondes max
          )
            print(f"✅ Modèle utilisé : {nom_modele}")
            break
        except Exception as e:
            derniere_erreur = e
            err = str(e)
            if '429' in err or 'quota' in err.lower():
                print(f"⚠️  Quota dépassé pour {nom_modele} → essai suivant...")
                continue
            if '404' in err:
                print(f"⚠️  Modèle {nom_modele} introuvable → essai suivant...")
                continue
            print(f"⚠️  Erreur sur {nom_modele} : {err[:100]}")
            continue

    if reponse is None:
        print(f"❌ Tous les modèles ont échoué.")
        return _correction_fallback(question, mots_cles,
                                    reponse_attendue, reponse_recruteur)

    try:
        texte = reponse.text.strip()
        texte = re.sub(r'^```json\s*', '', texte)
        texte = re.sub(r'\s*```$', '', texte)

        resultat = json.loads(texte)

        resultat['note'] = max(0, min(20, int(resultat.get('note', 0))))
        resultat.setdefault('hors_sujet', False)
        resultat.setdefault('commentaire', '')
        resultat.setdefault('points_forts', [])
        resultat.setdefault('points_faibles', [])
        resultat.setdefault('mots_cles_utilises', [])
        resultat.setdefault('mots_cles_manquants', [])

        return resultat

    except Exception as e:
        print(f"⚠️  Erreur parsing JSON : {e}")
        return _correction_fallback(question, mots_cles,
                                    reponse_attendue, reponse_recruteur)


def _correction_fallback(question, mots_cles, reponse_attendue, reponse_recruteur):
    """Correction basique si tous les modèles IA échouent."""
    if not reponse_recruteur or len(reponse_recruteur.strip()) < 30:
        return {
            "note": 0,
            "hors_sujet": True,
            "commentaire": "⚠️ Réponse trop courte. Correction manuelle requise.",
            "points_forts": [],
            "points_faibles": ["Réponse trop courte"],
            "mots_cles_utilises": [],
            "mots_cles_manquants": []
        }

    if not mots_cles:
        return {
            "note": 8,
            "hors_sujet": False,
            "commentaire": "⚠️ IA indisponible. Correction manuelle requise.",
            "points_forts": [],
            "points_faibles": ["Correction manuelle requise"],
            "mots_cles_utilises": [],
            "mots_cles_manquants": []
        }

    liste_mots = [m.strip().lower() for m in mots_cles.split(',') if m.strip()]
    texte = reponse_recruteur.lower()
    trouves = [m for m in liste_mots if m in texte]
    manquants = [m for m in liste_mots if m not in texte]
    ratio = len(trouves) / len(liste_mots) if liste_mots else 0
    note = min(round(ratio * 15), 12)

    return {
        "note": note,
        "hors_sujet": False,
        "commentaire": (
            f"⚠️ Correction basique (IA indisponible) : "
            f"{len(trouves)}/{len(liste_mots)} mots-clés. "
            f"⚠️ Hors-sujet NON vérifié. Formateur requis."
        ),
        "points_forts": [f"Mot-clé utilisé : {m}" for m in trouves],
        "points_faibles": [f"Mot-clé manquant : {m}" for m in manquants],
        "mots_cles_utilises": trouves,
        "mots_cles_manquants": manquants
    }