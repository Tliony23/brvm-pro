"""
Sikafinance identifie chaque titre par un code du type "SNTS.sn" (symbole BRVM +
suffixe du pays de cotation).

Ces codes sont désormais connus d'avance pour les 48 valeurs cotées : ils sont
listés dans referentiel.py. On les utilise en priorité, ce qui évite de tester
les suffixes un par un (c'était lent et bruyant pour le serveur).

Le repli par essais successifs reste disponible pour un éventuel nouveau titre
qui ne serait pas encore dans le référentiel.
"""
import requests

from db import get_ticker_sika, set_ticker_sika
from referentiel import get_sika
from utils_parsing import HEADERS

SUFFIXES_PAYS = [".ci", ".sn", ".bf", ".ml", ".tg", ".bj", ".ne", ".gw"]


def resoudre_symbole_sika(symbole_brvm, timeout=20):
    """Retourne le code Sikafinance (ex 'SNTS.sn') pour un symbole BRVM."""
    # 1) Le référentiel : instantané, aucune requête réseau
    depuis_ref = get_sika(symbole_brvm)
    if depuis_ref:
        return depuis_ref

    # 2) Le cache local d'une précédente résolution
    cache = get_ticker_sika(symbole_brvm)
    if cache:
        return cache

    # 3) Dernier recours : on essaie les suffixes un par un
    for suf in SUFFIXES_PAYS:
        candidat = f"{symbole_brvm}{suf}"
        url = f"https://www.sikafinance.com/marches/societe/{candidat}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
        except requests.RequestException:
            continue
        if resp.status_code == 200 and "fiche société" in resp.text.lower():
            set_ticker_sika(symbole_brvm, candidat)
            return candidat

    return None
