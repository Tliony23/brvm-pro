"""Fonctions de parsing partagées par tous les scrapers du projet."""
import re
from datetime import datetime

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def parse_nombre_fr(val):
    """Convertit un nombre au format FR ('12 345,67' ou '1,23%') en float.
    Renvoie None pour les cases vides ou les tirets ('-', '—')."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() == "nan" or s in ("-", "—", "None"):
        return None
    s = s.replace("\xa0", "").replace(" ", "").replace("%", "").replace(",", ".")
    s = re.sub(r"[^\d\.\-]", "", s)
    if s in ("", "-", "."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date_fr(val):
    """Convertit une date 'DD/MM/YYYY' en chaîne ISO 'YYYY-MM-DD'. None si invalide."""
    try:
        return datetime.strptime(str(val).strip(), "%d/%m/%Y").date().isoformat()
    except (ValueError, TypeError):
        return None


def parse_date_souple(val):
    """Essaie plusieurs formats de date courants ('DD/MM/YYYY', 'YYYY-MM-DD',
    ou une date/heure ISO complète) et renvoie une chaîne ISO 'YYYY-MM-DD'.
    Utile pour les points d'accès dont le format exact n'est pas garanti."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    # Dernier recours : garder juste les 10 premiers caractères si ça ressemble à une ISO
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return None


def trouver_colonne(colonnes, *candidats):
    """Cherche la première colonne dont le nom (en minuscule) contient un des candidats."""
    for c in colonnes:
        cl = str(c).strip().lower()
        for cand in candidats:
            if cand in cl:
                return c
    return None
