"""
Récupère les dividendes des sociétés cotées à la BRVM depuis la page
publique https://www.sikafinance.com/marches/dividendes

Cette page contient deux tableaux :
  1. Les dividendes À VENIR : date de détachement, montant, rendement.
     La date peut valoir "A préciser" quand l'assemblée générale n'a pas
     encore fixé le calendrier — on l'enregistre alors sans date.
  2. L'HISTORIQUE des dividendes versés sur les 4 dernières années, avec
     le rendement associé à chaque exercice.

On identifie chaque société par le lien présent dans sa ligne
(.../cotation_SNTS.sn), ce qui est bien plus fiable que le nom affiché
(souvent tronqué, ex. "BANK OF AFRICA BURKI").

Usage : python dividendes_sika.py
"""
import re
import sys

import lxml.html
import requests

from db import init_db, upsert_dividende_historique, upsert_dividendes_a_venir
from referentiel import VALEURS
from utils_parsing import HEADERS, parse_date_fr, parse_nombre_fr

URL = "https://www.sikafinance.com/marches/dividendes"

# Repère un lien du type .../cotation_SNTS.sn -> capture "SNTS"
MOTIF_TICKER = re.compile(r"cotation_([A-Za-z0-9]+)\.[a-z]{2}\b")


def ticker_de_la_ligne(tr):
    """Extrait le symbole (ex 'SNTS') depuis le premier lien de cotation de la ligne."""
    for href in tr.xpath(".//a/@href"):
        m = MOTIF_TICKER.search(href)
        if m:
            return m.group(1).upper()
    return None


def texte_cellules(tr):
    return [c.text_content().strip() for c in tr.xpath("./td")]


def fetch_dividendes():
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    arbre = lxml.html.fromstring(resp.text)

    a_venir = []
    historique = []

    for table in arbre.xpath("//table"):
        entetes = [th.text_content().strip().lower() for th in table.xpath(".//th")]
        entetes_txt = " | ".join(entetes)

        # --- Tableau 1 : dividendes à venir ---
        if "détachement" in entetes_txt or "detachement" in entetes_txt:
            for tr in table.xpath(".//tr"):
                cells = texte_cellules(tr)
                if len(cells) < 4:
                    continue
                sym = ticker_de_la_ligne(tr)
                if not sym:
                    continue
                date_iso = parse_date_fr(cells[0])  # None si "A préciser"
                a_venir.append({
                    "symbole": sym,
                    "date_detachement": date_iso,
                    "date_brute": cells[0],
                    "montant": parse_nombre_fr(cells[2]),
                    "rendement": parse_nombre_fr(cells[3]),
                })
            continue

        # --- Tableau 2 : historique (colonnes "Div. 2022", "Rend. 2022", ...) ---
        annees_par_colonne = {}
        for idx, e in enumerate(entetes):
            m = re.search(r"div\.?\s*(\d{4})", e)
            if m:
                annees_par_colonne[idx] = m.group(1)

        if annees_par_colonne:
            for tr in table.xpath(".//tr"):
                cells = texte_cellules(tr)
                if not cells:
                    continue
                sym = ticker_de_la_ligne(tr)
                if not sym:
                    continue
                for idx, annee in annees_par_colonne.items():
                    # idx compte les <th>; les <td> incluent la 1re colonne (nom)
                    montant = parse_nombre_fr(cells[idx]) if idx < len(cells) else None
                    rendement = parse_nombre_fr(cells[idx + 1]) if idx + 1 < len(cells) else None
                    if montant is None and rendement is None:
                        continue
                    historique.append({
                        "symbole": sym,
                        "annee": annee,
                        "montant": montant,
                        "rendement": rendement,
                    })

    return a_venir, historique


def main():
    init_db()
    a_venir, historique = fetch_dividendes()

    if not a_venir and not historique:
        print(
            "Aucune donnée de dividende récupérée. La structure de la page a "
            "peut-être changé — reviens voir Claude avec ce message."
        )
        sys.exit(1)

    upsert_dividendes_a_venir(a_venir)
    upsert_dividende_historique(historique)

    connus = set(VALEURS.keys())
    inconnus = sorted({r["symbole"] for r in a_venir + historique} - connus)

    avec_date = sum(1 for r in a_venir if r["date_detachement"])
    print(f"Dividendes à venir  : {len(a_venir)} ({avec_date} avec date connue, "
          f"{len(a_venir) - avec_date} encore 'à préciser')")
    print(f"Historique          : {len(historique)} lignes "
          f"({len({r['symbole'] for r in historique})} sociétés)")
    if inconnus:
        print(f"Symboles absents du référentiel (à ajouter dans referentiel.py) : {inconnus}")


if __name__ == "__main__":
    main()
