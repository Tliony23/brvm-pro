"""
Récupère les chiffres clés / fondamentaux d'un titre depuis la page
"société" de Sikafinance (https://www.sikafinance.com/marches/societe/{TICKER}).

Cette page donne, pour les ~5 dernières années : chiffre d'affaires, résultat
net, BNPA (bénéfice net par action), PER (déjà calculé par Sikafinance) et
dividende par action.

Remarque : le P/B (price-to-book) n'est pas publié sous forme structurée sur
les portails BRVM habituels (il faudrait la valeur comptable des fonds
propres, qui ne figure pas sur cette page) — il n'est donc pas inclus ici.
Le rendement du dividende (dividende / cours actuel) est calculable dans le
tableau de bord à partir du dividende et du dernier cours de clôture connu.
"""
import io
import re
import sys

import pandas as pd
import requests

from db import get_symboles, init_db, upsert_fondamentaux
from sika_utils import resoudre_symbole_sika
from utils_parsing import HEADERS, parse_nombre_fr


def trouver_ligne(table, *motifs):
    """Trouve la ligne dont le libellé (1ère colonne) contient un des motifs."""
    premiere_col = table.iloc[:, 0].astype(str).str.lower()
    for motif in motifs:
        mask = premiere_col.str.contains(motif, na=False)
        if mask.any():
            return table[mask].iloc[0]
    return None


def fetch_fondamentaux(symbole_sika):
    url = f"https://www.sikafinance.com/marches/societe/{symbole_sika}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()

    tables = pd.read_html(io.StringIO(resp.text), thousands=" ", decimal=",")

    table = None
    for t in tables:
        if t.shape[1] < 2:
            continue
        premiere_col = t.iloc[:, 0].astype(str).str.lower()
        if premiere_col.str.contains("per").any() and premiere_col.str.contains("bnpa").any():
            table = t
            break

    if table is None:
        return []

    annees = [str(c) for c in table.columns[1:]]

    ligne_ca = trouver_ligne(table, "chiffre d'affaires", "chiffre daffaires")
    ligne_croissance_ca = trouver_ligne(table, "croissance ca")
    ligne_rn = trouver_ligne(table, "résultat net", "resultat net")
    ligne_croissance_rn = trouver_ligne(table, "croissance rn")
    ligne_bnpa = trouver_ligne(table, "bnpa")
    ligne_per = trouver_ligne(table, "per")
    ligne_div = trouver_ligne(table, "dividende")

    def valeur(ligne, annee):
        if ligne is None:
            return None
        return parse_nombre_fr(ligne.get(annee))

    rows = []
    for annee in annees:
        if not re.match(r"^\d{4}$", annee):
            continue
        rows.append({
            "symbole": symbole_sika,
            "annee": annee,
            "chiffre_affaires": valeur(ligne_ca, annee),
            "croissance_ca": valeur(ligne_croissance_ca, annee),
            "resultat_net": valeur(ligne_rn, annee),
            "croissance_rn": valeur(ligne_croissance_rn, annee),
            "bnpa": valeur(ligne_bnpa, annee),
            "per": valeur(ligne_per, annee),
            "dividende": valeur(ligne_div, annee),
        })
    return rows


def main(symboles_brvm):
    init_db()
    for symbole_brvm in symboles_brvm:
        symbole_sika = resoudre_symbole_sika(symbole_brvm)
        if not symbole_sika:
            print(f"[{symbole_brvm}] introuvable sur Sikafinance (tous les suffixes pays ont échoué).")
            continue
        rows = fetch_fondamentaux(symbole_sika)
        if not rows:
            print(f"[{symbole_brvm}] page trouvée ({symbole_sika}) mais aucun tableau de fondamentaux détecté.")
            continue
        for r in rows:
            r["symbole"] = symbole_brvm
        upsert_fondamentaux(rows)
        print(f"[{symbole_brvm}] {len(rows)} année(s) de fondamentaux enregistrée(s) (source: {symbole_sika}).")


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else [sym for sym, _ in get_symboles()]
    if not tickers:
        print("Aucun titre en base. Précise des symboles en argument, ex: python fondamentaux_sika.py SNTS BICC")
        sys.exit(1)
    main(tickers)
