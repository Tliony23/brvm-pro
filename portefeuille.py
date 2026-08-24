"""
Calculs liés au portefeuille : valorisation, plus-values, répartition,
revenu de dividendes attendu et reconstitution de la courbe d'évolution.
"""
from collections import defaultdict

import pandas as pd

from db import (
    get_dividendes_a_venir,
    get_liquidites,
    get_dividendes_historique,
    get_historique,
    get_portefeuille,
    get_tous_derniers_cours,
)
from referentiel import get_nom, get_secteur


def lignes_portefeuille():
    """Une ligne enrichie par position détenue."""
    positions = get_portefeuille()
    if not positions:
        return []

    cours = get_tous_derniers_cours()
    lignes = []

    for symbole, quantite, pru in positions:
        infos = cours.get(symbole)
        cloture = infos[1] if infos else None
        veille = infos[2] if infos else None

        valeur = cloture * quantite if cloture else None
        investi = pru * quantite
        pv = (valeur - investi) if valeur is not None else None
        pv_pct = (pv / investi * 100) if (pv is not None and investi) else None

        var_jour_unite = (cloture - veille) if (cloture and veille) else None
        var_jour = var_jour_unite * quantite if var_jour_unite is not None else None
        var_jour_pct = (var_jour_unite / veille * 100) if (var_jour_unite is not None and veille) else None

        lignes.append({
            "symbole": symbole,
            "nom": get_nom(symbole),
            "secteur": get_secteur(symbole),
            "quantite": quantite,
            "pru": pru,
            "cours": cloture,
            "valeur": valeur,
            "investi": investi,
            "pv": pv,
            "pv_pct": pv_pct,
            "var_jour": var_jour,
            "var_jour_pct": var_jour_pct,
        })
    return lignes


def resume_portefeuille(lignes):
    """Totaux et extrêmes affichés sur l'accueil.

    La plus-value et la variation du jour ne portent QUE sur les actions :
    les liquidités ne montent ni ne descendent, les mélanger fausserait les
    pourcentages de performance.
    """
    liquidites = get_liquidites()
    if not lignes:
        if liquidites <= 0:
            return None
        return {
            "valeur": 0, "investi": 0, "pv": 0, "pv_pct": None,
            "var_jour": 0, "var_jour_pct": None, "nb_positions": 0,
            "meilleure": None, "pire": None,
            "liquidites": liquidites, "total": liquidites,
        }

    valeur = sum(l["valeur"] for l in lignes if l["valeur"] is not None)
    investi = sum(l["investi"] for l in lignes)
    var_jour = sum(l["var_jour"] for l in lignes if l["var_jour"] is not None)

    valeur_veille = valeur - var_jour
    avec_pv = [l for l in lignes if l["pv_pct"] is not None]

    return {
        "valeur": valeur,
        "investi": investi,
        "pv": valeur - investi,
        "pv_pct": (valeur - investi) / investi * 100 if investi else None,
        "var_jour": var_jour,
        "var_jour_pct": var_jour / valeur_veille * 100 if valeur_veille else None,
        "nb_positions": len(lignes),
        "meilleure": max(avec_pv, key=lambda l: l["pv_pct"]) if avec_pv else None,
        "pire": min(avec_pv, key=lambda l: l["pv_pct"]) if avec_pv else None,
        "liquidites": liquidites,
        "total": valeur + liquidites,
    }


def repartition(lignes, par="secteur", inclure_liquidites=True):
    """Répartition en pourcentage, par secteur ou par valeur.

    Les liquidités forment leur propre part : c'est ce qui permet de voir
    d'un coup d'œil quelle proportion du patrimoine n'est pas investie.
    """
    liquidites = get_liquidites() if inclure_liquidites else 0
    total = sum(l["valeur"] for l in lignes if l["valeur"] is not None) + liquidites
    if not total:
        return []

    if par == "secteur":
        cumul = defaultdict(float)
        for l in lignes:
            if l["valeur"] is not None:
                cumul[l["secteur"]] += l["valeur"]
        elements = cumul.items()
    else:
        elements = [(l["nom"], l["valeur"]) for l in lignes if l["valeur"] is not None]

    parts = [{"libelle": k, "valeur": v, "pct": v / total * 100} for k, v in elements]
    if liquidites > 0:
        parts.append({"libelle": "Liquidités", "valeur": liquidites,
                      "pct": liquidites / total * 100})
    return sorted(parts, key=lambda d: d["valeur"], reverse=True)


def dernier_dividende_connu(symbole):
    """Montant du dernier dividende versé (exercice le plus récent renseigné)."""
    historique = get_dividendes_historique(symbole)
    montants = [(a, m) for a, m, _ in historique if m is not None and m > 0]
    return montants[-1][1] if montants else None


def revenu_dividendes(lignes):
    """Revenu annuel brut projeté, ligne par ligne.

    Projection basée sur le dernier dividende connu de chaque société : elle
    suppose un versement au moins équivalent l'an prochain, ce qui n'est jamais
    garanti. Montants BRUTS, avant retenue à la source (l'IRVM est prélevé par
    la société et varie selon le pays).
    """
    resultat = []
    for l in lignes:
        div_unitaire = dernier_dividende_connu(l["symbole"])
        if not div_unitaire:
            continue
        annuel = div_unitaire * l["quantite"]
        resultat.append({
            **l,
            "div_unitaire": div_unitaire,
            "revenu_annuel": annuel,
            "rendement_sur_cout": div_unitaire / l["pru"] * 100 if l["pru"] else None,
            "rendement_actuel": div_unitaire / l["cours"] * 100 if l["cours"] else None,
        })
    return sorted(resultat, key=lambda d: d["revenu_annuel"], reverse=True)


def dividendes_attendus(lignes):
    """Prochains détachements concernant les titres détenus, avec le montant
    que représenterait la position."""
    detenus = {l["symbole"]: l for l in lignes}
    if not detenus:
        return []

    resultat = []
    for symbole, date_iso, date_brute, montant, rendement in get_dividendes_a_venir(list(detenus)):
        ligne = detenus[symbole]
        resultat.append({
            "symbole": symbole,
            "nom": get_nom(symbole),
            "date": date_iso,
            "date_brute": date_brute,
            "montant_unitaire": montant,
            "montant_total": montant * ligne["quantite"] if montant else None,
            "quantite": ligne["quantite"],
            "rendement": rendement,
        })
    return resultat


def courbe_portefeuille(lignes, jours=None):
    """Reconstitue la valeur du portefeuille dans le temps.

    ATTENTION : on applique les quantités ACTUELLES aux cours passés. La courbe
    répond donc à « combien vaudrait mon portefeuille d'aujourd'hui à chaque
    date passée », et non « combien valait-il réellement ce jour-là ».
    """
    if not lignes:
        return pd.DataFrame()

    series = []
    for l in lignes:
        historique = get_historique(l["symbole"])
        if not historique:
            continue
        df = pd.DataFrame(
            historique,
            columns=["date", "ouverture", "haut", "bas", "cloture", "volume"],
        )[["date", "cloture"]].dropna()
        if df.empty:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")["cloture"] * l["quantite"]
        series.append(df.rename(l["symbole"]))

    if not series:
        return pd.DataFrame()

    # Un titre non coté un jour donné garde sa dernière valeur connue
    total = pd.concat(series, axis=1).sort_index().ffill().dropna(how="all")
    resultat = total.sum(axis=1).reset_index()
    resultat.columns = ["date", "valeur"]

    if jours:
        limite = resultat["date"].max() - pd.Timedelta(days=jours)
        resultat = resultat[resultat["date"] >= limite]

    return resultat
