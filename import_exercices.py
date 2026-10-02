"""
Import du fichier 'Test de Niveau.docx' → table Exercice (Numérologie)
"""
import os
import re
from docx import Document
from app import app
from models import db, Theme, Exercice

DOSSIER_WORD = "docs_word"
THEME = "Numérologie"


def importer():
    with app.app_context():
        fichiers = [f for f in os.listdir(DOSSIER_WORD)
                    if f.lower().endswith('.docx') and 'test' in f.lower()]

        if not fichiers:
            print("❌ Aucun fichier 'Test*.docx' trouvé dans docs_word/")
            return

        fichier = os.path.join(DOSSIER_WORD, fichiers[0])
        print(f"📄 Fichier détecté : {fichier}\n")

        theme = Theme.query.filter_by(nom=THEME).first()
        if not theme:
            print(f"❌ Thème '{THEME}' introuvable. Lance d'abord init_db.py")
            return

        doc = Document(fichier)
        texte = "\n".join(p.text for p in doc.paragraphs)

        pattern = r'(?:🔹\s*\*?\*?)?Exercice\s+(\d+)'
        morceaux = re.split(pattern, texte)

        ordre = 0
        i = 1
        while i < len(morceaux) - 1:
            num = morceaux[i].strip()
            contenu = morceaux[i+1].strip()

            if not num.isdigit():
                i += 2
                continue

            client_match = re.search(r'Client\s*:\s*[«"]?(.+?)[»"]?\s*\n',
                                     contenu, re.MULTILINE)
            client_txt = client_match.group(1).strip() if client_match else ""

            donnees_lignes = []
            for ligne in contenu.split('\n'):
                ligne_clean = ligne.strip().strip('*').strip()
                if re.match(r'Date (de naissance|de consultation)', ligne_clean):
                    donnees_lignes.append(ligne_clean)

            ordre += 1
            titre = f"Exercice {num}"

            existant = Exercice.query.filter_by(
                theme_id=theme.id, titre=titre
            ).first()

            if existant:
                existant.enonce = client_txt
                existant.donnees = "\n".join(donnees_lignes)
                print(f"♻️  Mis à jour : {titre}")
            else:
                ex = Exercice(
                    titre=titre,
                    enonce=client_txt,
                    donnees="\n".join(donnees_lignes),
                    reponse_attendue="(À compléter par le formateur)",
                    theme_id=theme.id,
                    ordre=ordre
                )
                db.session.add(ex)
                print(f"➕ Ajouté : {titre} — {client_txt[:60]}…")

            i += 2

        db.session.commit()
        print(f"\n✅ {ordre} exercices importés pour '{THEME}'.")


if __name__ == "__main__":
    importer()