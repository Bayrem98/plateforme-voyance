"""
Import du Tarot de Marseille : formations + exercices par carte.
Lit docs_word/tarot/tarot_mapping.json
"""
import os
import re
import json
import shutil
from docx import Document
from app import app
from models import db, Theme, Formation, Exercice

DOSSIER = "docs_word/tarot"
DOSSIER_IMAGES = "static/cartes"
MAPPING_FILE = "tarot_mapping.json"
THEME = "Tarot de Marseille"


def docx_to_html(path):
    """Accepte .docx ET .txt."""
    if path.lower().endswith('.txt'):
        with open(path, encoding='utf-8') as f:
            texte = f.read()
        paragraphes = [p.strip() for p in texte.split('\n\n') if p.strip()]
        html = []
        for p in paragraphes:
            # Détecter les lignes courtes en majuscules → titres
            if len(p) < 80 and p.isupper():
                html.append(f"<h3>{p}</h3>")
            else:
                # Remplacer les sauts simples par <br>
                html.append(f"<p>{p.replace(chr(10), '<br>')}</p>")
        return "\n".join(html)
    
    # Sinon .docx normal
    from import_word import docx_to_html as d
    return d(path)


def lire_texte(path):
    """Lit un fichier .txt en UTF-8."""
    with open(path, encoding='utf-8') as f:
        return f.read()


def parser_exercice(path):
    doc = Document(path)
    texte = "\n".join(p.text for p in doc.paragraphs)

    resultats = []
    domaine_courant = None
    lignes = texte.split('\n')

    for i, ligne in enumerate(lignes):
        l = ligne.strip()

        for d in ['AMOUR', 'TRAVAIL', 'SANTÉ', 'SANTE', 'FINANCE', 'FAMILLE']:
            if d in l.upper() and len(l) < 30:
                domaine_courant = d.capitalize()

        m = re.search(r'Question\s*\d*\s*[:\-]?\s*[«"]?([^»"?]+)[»"]?',
                      l, re.IGNORECASE)
        if m and ('?' in l or 'question' in l.lower()):
            q = m.group(1).strip()
            if len(q) < 5:
                continue

            mots = None
            for j in range(1, 8):
                if i + j >= len(lignes):
                    break
                lsuiv = lignes[i + j].strip()
                if 'mots' in lsuiv.lower() and ('clé' in lsuiv.lower() or 'cle' in lsuiv.lower()):
                    apres = re.sub(r'.*[:\-→]\s*', '', lsuiv).strip()
                    if apres and len(apres) > 3:
                        mots = apres
                        break
                if lsuiv.startswith(('→', '-', '•')) and '–' in lsuiv and len(lsuiv) < 100:
                    mots = re.sub(r'^[→\-\s]+', '', lsuiv).strip()
                    break

            resultats.append({
                'domaine': domaine_courant,
                'question': q,
                'mots_cles': mots
            })

    return resultats


def importer():
    with app.app_context():
        theme = Theme.query.filter_by(nom=THEME).first()
        if not theme:
            print(f"❌ Thème '{THEME}' introuvable. Lance init_db.py d'abord.")
            return

        if not os.path.exists(DOSSIER):
            print(f"❌ Dossier '{DOSSIER}/' introuvable.")
            return

        mapping_path = os.path.join(DOSSIER, MAPPING_FILE)
        if not os.path.exists(mapping_path):
            print(f"❌ Fichier '{MAPPING_FILE}' introuvable dans {DOSSIER}/")
            return

        os.makedirs(DOSSIER_IMAGES, exist_ok=True)

        with open(mapping_path, encoding='utf-8') as f:
            mapping = json.load(f)

        for niveau_str, info in sorted(mapping.items(), key=lambda x: int(x[0])):
            niveau = int(niveau_str)
            nom_carte = info['nom']
            titre_carte = f"Arcane {niveau} — {nom_carte}"

            print(f"\n🃏 Carte {niveau} : {nom_carte}")

            # 📸 IMAGE
            image_nom = None
            if info.get('image'):
                src = os.path.join(DOSSIER, info['image'])
                if os.path.exists(src):
                    dest = os.path.join(DOSSIER_IMAGES, info['image'])
                    shutil.copy2(src, dest)
                    image_nom = info['image']
                    print(f"   📸 Image copiée : {image_nom}")
                else:
                    print(f"   ⚠️  Image introuvable : {info['image']}")

            # 📝 DÉFINITION (txt)
            definition_txt = None
            if info.get('definition'):
                chemin_def = os.path.join(DOSSIER, info['definition'])
                if os.path.exists(chemin_def):
                    definition_txt = lire_texte(chemin_def)
                    print(f"   📖 Définition lue : {info['definition']}")
                else:
                    print(f"   ⚠️  Définition introuvable : {info['definition']}")

            # 📚 FORMATION (docx)
            contenu_html = None
            if info.get('formation'):
                chemin = os.path.join(DOSSIER, info['formation'])
                if os.path.exists(chemin):
                    contenu_html = docx_to_html(chemin)
                    print(f"   📚 Formation lue : {info['formation']}")
                else:
                    print(f"   ⚠️  Formation introuvable : {info['formation']}")

            # Créer ou mettre à jour la Formation
            if contenu_html:
                existante = Formation.query.filter_by(
                    theme_id=theme.id, ordre=niveau
                ).first()

                if existante:
                    existante.titre = titre_carte
                    existante.contenu = contenu_html
                    existante.image = image_nom
                    existante.definition = definition_txt
                    print(f"   ♻️  Formation mise à jour")
                else:
                    f = Formation(
                        titre=titre_carte,
                        contenu=contenu_html,
                        image=image_nom,
                        definition=definition_txt,
                        theme_id=theme.id,
                        ordre=niveau
                    )
                    db.session.add(f)
                    print(f"   ➕ Formation créée")

            # 📝 EXERCICES
            if info.get('exercice'):
                chemin = os.path.join(DOSSIER, info['exercice'])
                if os.path.exists(chemin):
                    questions = parser_exercice(chemin)
                    print(f"   📝 {len(questions)} question(s) détectée(s)")

                    for idx, q in enumerate(questions, 1):
                        titre = f"{nom_carte} — Q{idx}"
                        if q['domaine']:
                            titre = f"{nom_carte} — {q['domaine']} Q{idx}"

                        existant = Exercice.query.filter_by(
                            theme_id=theme.id, titre=titre
                        ).first()

                        if existant:
                            existant.enonce = q['question']
                            existant.mots_cles = q['mots_cles']
                            existant.niveau = niveau
                            existant.domaine = q['domaine']
                        else:
                            ex = Exercice(
                                titre=titre,
                                domaine=q['domaine'],
                                niveau=niveau,
                                enonce=q['question'],
                                mots_cles=q['mots_cles'],
                                reponse_attendue="(à compléter)",
                                theme_id=theme.id,
                                ordre=idx
                            )
                            db.session.add(ex)
                else:
                    print(f"   ⚠️  Exercice introuvable : {info['exercice']}")

            db.session.commit()

        print("\n✅ Import Tarot terminé !")


if __name__ == "__main__":
    importer()