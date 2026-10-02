"""
Import des exercices de formulation (format Tarot).
Lit tous les fichiers commençant par '🧠 EXERCICE' dans docs_word/.
"""
import os
import re
from docx import Document
from app import app
from models import db, Theme, Formation, Exercice

DOSSIER = "docs_word"
THEME_NOM = "Tarot de Marseille"


def extraire_domaine(txt):
    """Détecte le domaine (AMOUR, TRAVAIL, etc.)"""
    txt_up = txt.upper()
    for d in ['AMOUR', 'TRAVAIL', 'SANTÉ', 'SANTE', 'FINANCE', 'FAMILLE']:
        if d in txt_up:
            return d.capitalize()
    return None


def extraire_mots_cles(txt):
    """Cherche une ligne 'Mots-clés à utiliser : a, b, c'"""
    match = re.search(r'Mots[- ]?cl[ée]s?\s*(?:à\s*(?:utiliser|intégrer))?\s*[:\-→]\s*(.+)',
                      txt, re.IGNORECASE)
    if match:
        # Nettoyer
        mots = match.group(1).strip()
        mots = re.sub(r'^[→\-\s]+', '', mots)
        return mots
    return None


def importer_fichier(chemin, theme):
    doc = Document(chemin)
    texte = "\n".join(p.text for p in doc.paragraphs)
    
    # Trouver la carte concernée (ex: "Le Bateleur")
    carte_match = re.search(r'(?:Arcane\s+I+\s*[:\-]?\s*)?(Le\s+\w+|La\s+\w+|L\'?\w+)',
                            texte)
    nom_carte = carte_match.group(0).strip() if carte_match else "Carte inconnue"
    
    # Découper par domaine
    domaine_actuel = None
    
    # Pattern : "Domaine : X" ou "AMOUR" / "TRAVAIL" en majuscules
    lignes = texte.split('\n')
    
    # Recherche par bloc
    # Pattern question : "Question N : « ... »" ou "N. Question : ..."
    pattern_q = re.compile(
        r'(?:(\d+)\.\s*)?Question\s*(?:(\d+)\s*[:\-])?\s*[«"]([^»"]+)[»"]',
        re.IGNORECASE
    )
    
    # Récupérer les domaines
    domaines = re.findall(r'Domaine\s*[:\-]\s*(\w+)', texte, re.IGNORECASE)
    if not domaines:
        domaines = re.findall(r'^\s*(AMOUR|TRAVAIL|SANTÉ|SANTE|FINANCE|FAMILLE)\s*$',
                              texte, re.MULTILINE | re.IGNORECASE)
    
    # Compter les questions
    questions = list(pattern_q.finditer(texte))
    
    # Si le fichier "FICHE CANDIDAT", on a des questions avec mots-clés
    # Pattern bloc question + mots-clés
    blocs = re.split(r'(?:(\d+)\.\s*)?Question\s*(?:\d+\s*[:\-])?\s*', texte)
    
    ordre = 0
    for i, match in enumerate(questions):
        question_txt = match.group(3).strip()
        
        # Chercher mots-clés après la question
        pos_fin = match.end()
        extrait = texte[pos_fin:pos_fin+400]
        mots_cles = extraire_mots_cles(extrait)
        
        # Domaine : on regarde avant la question
        avant = texte[:match.start()]
        domaine = None
        for d in reversed(domaines):
            # Le dernier domaine vu avant la question
            if d.upper() in avant.upper():
                domaine = d.capitalize()
                break
        
        ordre += 1
        titre = f"{nom_carte} — Q{ordre}"
        if domaine:
            titre = f"{nom_carte} — {domaine} Q{ordre}"
        
        # Vérifier existence
        existant = Exercice.query.filter_by(
            theme_id=theme.id, titre=titre
        ).first()
        
        if existant:
            existant.enonce = question_txt
            existant.mots_cles = mots_cles or existant.mots_cles
            existant.domaine = domaine
            print(f"♻️  {titre}")
        else:
            ex = Exercice(
                titre=titre,
                domaine=domaine,
                enonce=question_txt,
                mots_cles=mots_cles,
                reponse_attendue="(à compléter par le formateur)",
                theme_id=theme.id,
                ordre=ordre
            )
            db.session.add(ex)
            print(f"➕ {titre}")
            if mots_cles:
                print(f"    Mots-clés : {mots_cles}")
    
    db.session.commit()


def importer():
    with app.app_context():
        theme = Theme.query.filter_by(nom=THEME_NOM).first()
        if not theme:
            print(f"❌ Thème '{THEME_NOM}' introuvable.")
            return
        
        fichiers = [f for f in os.listdir(DOSSIER)
                    if f.lower().endswith('.docx') and 'exercice' in f.lower()]
        
        if not fichiers:
            print(f"⚠️  Aucun fichier 'EXERCICE*.docx' dans {DOSSIER}/")
            return
        
        print(f"📂 {len(fichiers)} fichier(s) détecté(s)\n")
        for f in fichiers:
            print(f"📄 {f}")
            importer_fichier(os.path.join(DOSSIER, f), theme)
            print()
        
        print("✅ Import terminé !")


if __name__ == "__main__":
    importer()