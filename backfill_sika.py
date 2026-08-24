"""
Récupère l'historique des cours (par défaut les 15 dernières années, au jour
le jour) via le point d'accès JSON interne utilisé par le site Sikafinance
pour ses propres graphiques.

IMPORTANT — à savoir avant d'utiliser ce script :
Ce point d'accès (URL ci-dessous) n'est pas documenté officiellement par
Sikafinance. Sa structure exacte (URL, champs envoyés, format de la réponse)
a été identifiée en étudiant le code source ouvert du package R "BRVM" par
Koffi Frédéric Sessie (https://github.com/Koffi-Fredysessie/BRVM), qui
l'utilise pour le même usage. Il n'a pas pu être testé en conditions réelles
au moment d'écrire ce script (environnement sans accès direct à internet pour
ce test précis) : il est donc possible qu'un ajustement soit nécessaire au
premier lancement. Si ça ne fonctionne pas du premier coup, le message
d'erreur affiché donnera une piste claire, et on pourra ajuster ensemble.

Usage :
    python backfill_sika.py                  (tous les titres connus, 15 ans)
    python backfill_sika.py SNTS BICC         (titres précis, 15 ans)
    python backfill_sika.py --annees 5        (change la profondeur d'historique)
"""
import argparse
import sys
import time
from datetime import date, timedelta

import requests

from db import get_symboles, init_db, upsert_prix
from sika_utils import resoudre_symbole_sika
from utils_parsing import parse_date_souple

API_URL = "https://www.sikafinance.com/api/general/GetHistos"
TAILLE_FENETRE_JOURS = 89   # taille des tranches de requêtes successives
PAUSE_ENTRE_REQUETES = 0.15  # secondes, pour rester correct vis-à-vis du serveur

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
    "Origin": "https://www.sikafinance.com",
    "Content-Type": "application/json",
}


def fetch_tranche(ticker_sika, date_debut, date_fin):
    headers = dict(HEADERS_BASE)
    headers["Referer"] = f"https://www.sikafinance.com/marches/historiques/{ticker_sika}"
    corps = {
        "ticker": ticker_sika,
        "datedeb": date_debut.isoformat(),
        "datefin": date_fin.isoformat(),
        "xperiod": "0",  # 0 = quotidien
    }
    resp = requests.post(API_URL, json=corps, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # La réponse a la forme {"lst": [{"Date": "01/01/2025", "Open": 23790, "High": ...}, ...]}
    # c'est-à-dire une LISTE d'objets (un objet par jour), pas un dictionnaire de listes.
    lst = data.get("lst") if isinstance(data, dict) else None
    if not lst or not isinstance(lst, list):
        return []

    rows = []
    for item in lst:
        if not isinstance(item, dict):
            continue
        d = parse_date_souple(item.get("Date"))
        if not d:
            continue
        rows.append({
            "date": d,
            "cours_ouverture": item.get("Open"),
            "cours_haut": item.get("High"),
            "cours_bas": item.get("Low"),
            "cours_cloture": item.get("Close"),
            "volume": item.get("Volume"),
        })
    return rows


def fetch_historique_profond(ticker_sika, annees):
    aujourdhui = date.today()
    depart = aujourdhui - timedelta(days=int(annees * 365.25))
    toutes_les_lignes = []
    curseur = depart
    nb_tranches_ok = 0
    nb_tranches_echec = 0

    while curseur < aujourdhui:
        fin_tranche = min(curseur + timedelta(days=TAILLE_FENETRE_JOURS), aujourdhui)
        try:
            lignes = fetch_tranche(ticker_sika, curseur, fin_tranche)
            toutes_les_lignes.extend(lignes)
            nb_tranches_ok += 1
        except requests.RequestException as e:
            nb_tranches_echec += 1
            if nb_tranches_echec <= 3:
                print(f"    (tranche {curseur} -> {fin_tranche} échouée : {e})")
        time.sleep(PAUSE_ENTRE_REQUETES)
        curseur = fin_tranche + timedelta(days=1)

    return toutes_les_lignes, nb_tranches_ok, nb_tranches_echec


def main(symboles_brvm, annees):
    init_db()
    for symbole_brvm in symboles_brvm:
        symbole_sika = resoudre_symbole_sika(symbole_brvm)
        if not symbole_sika:
            print(f"[{symbole_brvm}] introuvable sur Sikafinance (tous les suffixes pays ont échoué).")
            continue

        print(f"[{symbole_brvm}] récupération de {annees} an(s) d'historique (source : {symbole_sika})...")
        lignes, ok, echec = fetch_historique_profond(symbole_sika, annees)

        if not lignes:
            print(
                f"[{symbole_brvm}] aucune donnée reçue ({ok} tranche(s) ok, {echec} échouée(s)). "
                "Le point d'accès a peut-être changé de format — reviens voir Claude avec ce message."
            )
            continue

        for r in lignes:
            r["symbole"] = symbole_brvm
        upsert_prix(lignes)

        dates_valides = sorted(r["date"] for r in lignes)
        print(
            f"[{symbole_brvm}] {len(lignes)} jour(s) enregistré(s), "
            f"du {dates_valides[0]} au {dates_valides[-1]}."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill de l'historique des cours BRVM depuis Sikafinance.")
    parser.add_argument("tickers", nargs="*", help="Symboles à traiter (vide = tous les titres connus)")
    parser.add_argument("--annees", type=float, default=15, help="Profondeur d'historique en années (défaut : 15)")
    args = parser.parse_args()

    tickers = args.tickers if args.tickers else [sym for sym, _ in get_symboles()]
    if not tickers:
        print("Aucun titre en base. Lance d'abord scraper_brvm.py, ou précise des symboles en argument.")
        sys.exit(1)

    main(tickers, args.annees)
