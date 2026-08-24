"""
Récupère les cours de clôture du jour depuis la page publique de la BRVM
(https://www.brvm.org/fr/cours-actions/0) et les enregistre dans la base locale.

À lancer une fois par jour, après la clôture (le site affiche généralement
la mise à jour du jour vers 22h-23h GMT). Peut être relancé sans risque :
les données du jour sont mises à jour, pas dupliquées.
"""
import io
import sys
from datetime import date

import pandas as pd
import requests

from db import init_db, upsert_prix
from utils_parsing import HEADERS, parse_nombre_fr, trouver_colonne

URL = "https://www.brvm.org/fr/cours-actions/0"


def fetch_cours_du_jour():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    # thousands=' ' et decimal=',' : sans ça, pandas interprète mal les nombres
    # au format français (ex: "1,61" serait lu comme 161 au lieu de 1.61)
    tables = pd.read_html(io.StringIO(resp.text), thousands=" ", decimal=",")

    table = None
    for t in tables:
        cols = [str(c).lower() for c in t.columns]
        if any("symbole" in c for c in cols):
            table = t
            break

    if table is None:
        raise RuntimeError(
            "Impossible de trouver le tableau des cours sur la page brvm.org. "
            "La structure du site a probablement changé — il faut ré-inspecter la page."
        )

    cols = table.columns
    col_symbole = trouver_colonne(cols, "symbole")
    col_nom = trouver_colonne(cols, "nom", "valeur", "libell")
    col_veille = trouver_colonne(cols, "veille")
    col_ouverture = trouver_colonne(cols, "ouverture")
    col_cloture = trouver_colonne(cols, "clôture", "cloture")
    col_variation = trouver_colonne(cols, "variation")
    col_volume = trouver_colonne(cols, "volume")

    today = date.today().isoformat()
    rows = []
    for _, r in table.iterrows():
        symbole = str(r.get(col_symbole, "")).strip()
        if not symbole or symbole.lower() == "nan":
            continue
        rows.append({
            "symbole": symbole,
            "nom": str(r.get(col_nom, "")).strip() if col_nom else "",
            "date": today,
            "cours_veille": parse_nombre_fr(r.get(col_veille)) if col_veille else None,
            "cours_ouverture": parse_nombre_fr(r.get(col_ouverture)) if col_ouverture else None,
            "cours_cloture": parse_nombre_fr(r.get(col_cloture)) if col_cloture else None,
            "variation": parse_nombre_fr(r.get(col_variation)) if col_variation else None,
            "volume": parse_nombre_fr(r.get(col_volume)) if col_volume else None,
        })
    return rows


def main():
    init_db()
    rows = fetch_cours_du_jour()
    if not rows:
        print("Aucune donnée récupérée — vérifie ta connexion ou la structure du site.")
        sys.exit(1)
    upsert_prix(rows)
    print(f"OK : {len(rows)} valeurs enregistrées pour le {date.today().isoformat()}.")


if __name__ == "__main__":
    main()
