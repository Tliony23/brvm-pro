"""
Moteur de notation quantitative des valeurs BRVM.

Note globale sur 100, composée de quatre blocs pondérés :
    Dividende & rendement  30 %
    Tendance & momentum    25 %
    Risque & liquidité     25 %
    Valorisation           20 %

Chaque bloc agrège plusieurs indicateurs, chacun ramené sur une échelle 0-100.

IMPORTANT : c'est un calcul mécanique à partir de l'historique des cours, des
dividendes et du secteur. C'est un outil de comparaison et d'aide à la
décision, pas un conseil d'investissement. Un score élevé ne garantit rien.
"""
import numpy as np
import pandas as pd

PONDERATIONS = {
    "dividende": 0.30,
    "tendance": 0.25,
    "risque": 0.25,
    "valorisation": 0.20,
}

# Appréciation qualitative de la solidité relative des secteurs de la BRVM.
# Volontairement grossier : sert seulement de petit ajustement dans le bloc
# Valorisation, jamais de critère décisif.
SOLIDITE_SECTEUR = {
    "Finance": 75,
    "Télécommunications": 80,
    "Services publics": 70,
    "Distribution": 60,
    "Industrie": 55,
    "Agriculture": 50,
    "Transport": 55,
    "Autres": 50,
}


def _echelle(valeur, bas, haut):
    """Ramène `valeur` sur 0-100 entre les bornes `bas` et `haut` (bornes incluses)."""
    if valeur is None or (isinstance(valeur, float) and np.isnan(valeur)):
        return None
    if haut == bas:
        return 50.0
    score = (valeur - bas) / (haut - bas) * 100
    return float(np.clip(score, 0, 100))


def _moyenne_ponderee(paires):
    """paires: [(score, poids), ...]. Ignore les scores manquants et
    redistribue leur poids sur les indicateurs disponibles."""
    dispo = [(s, p) for s, p in paires if s is not None]
    if not dispo:
        return None
    total_poids = sum(p for _, p in dispo)
    return sum(s * p for s, p in dispo) / total_poids


# ------------------------------------------------------------------ DIVIDENDE

def bloc_dividende(historique_div, cours_actuel):
    """historique_div: [(annee, montant, rendement), ...] trié par année."""
    details = {}

    montants = [(a, m) for a, m, _ in historique_div if m is not None and m > 0]

    # Rendement du dividende : dernier dividende versé rapporté au cours actuel
    rendement = None
    if montants and cours_actuel:
        rendement = montants[-1][1] / cours_actuel * 100
    details["rendement"] = rendement
    score_rendement = _echelle(rendement, 0, 12)

    # Croissance annualisée (CAGR) entre le premier et le dernier dividende connu
    cagr = None
    if len(montants) >= 2:
        premier, dernier = montants[0][1], montants[-1][1]
        nb_annees = int(montants[-1][0]) - int(montants[0][0])
        if nb_annees > 0 and premier > 0:
            cagr = ((dernier / premier) ** (1 / nb_annees) - 1) * 100
    details["cagr"] = cagr
    score_cagr = _echelle(cagr, -20, 25)

    # Régularité : nombre d'exercices effectivement payés sur ceux disponibles
    nb_verses = len(montants)
    nb_possibles = len(historique_div) if historique_div else 0
    details["annees_versees"] = nb_verses
    details["annees_possibles"] = nb_possibles
    score_regularite = _echelle(nb_verses, 0, nb_possibles) if nb_possibles else None

    score = _moyenne_ponderee([
        (score_rendement, 0.50),
        (score_cagr, 0.30),
        (score_regularite, 0.20),
    ])
    return score, details


# ------------------------------------------------------------------- TENDANCE

def bloc_tendance(df):
    """df: DataFrame trié par date avec cours_cloture, sma50, sma200."""
    details = {}
    # En dessous d'environ trois mois de séances, une "tendance" n'a pas de sens :
    # mieux vaut ne rien afficher que d'afficher un chiffre trompeur.
    if df is None or len(df) < 60:
        return None, details

    prix = df["cours_cloture"].iloc[-1]
    sma50 = df["sma50"].iloc[-1] if "sma50" in df else None
    sma200 = df["sma200"].iloc[-1] if "sma200" in df else None

    # Configuration des moyennes mobiles
    score_mm, libelle = None, "indisponible"
    if pd.notna(sma50) and pd.notna(sma200):
        if prix > sma50 > sma200:
            score_mm, libelle = 100, "haussière (prix > MM50 > MM200)"
        elif prix > sma50:
            score_mm, libelle = 70, "en reprise (prix > MM50)"
        elif prix > sma200:
            score_mm, libelle = 40, "hésitante (prix > MM200 mais < MM50)"
        else:
            score_mm, libelle = 10, "baissière (prix < MM50 et < MM200)"
    elif pd.notna(sma50):
        score_mm = 70 if prix > sma50 else 30
        libelle = "prix > MM50" if prix > sma50 else "prix < MM50"
    details["tendance_libelle"] = libelle

    # Position dans le range des 52 dernières semaines (~252 séances)
    fenetre = df.tail(252)
    plus_bas, plus_haut = fenetre["cours_cloture"].min(), fenetre["cours_cloture"].max()
    position = None
    if pd.notna(plus_bas) and pd.notna(plus_haut) and plus_haut > plus_bas:
        position = (prix - plus_bas) / (plus_haut - plus_bas) * 100
    details["position_52s"] = position
    score_position = _echelle(position, 0, 100)

    # Performance sur un an
    perf = None
    if len(df) > 252:
        ancien = df["cours_cloture"].iloc[-253]
        if ancien and ancien > 0:
            perf = (prix / ancien - 1) * 100
    elif len(df) > 20:
        ancien = df["cours_cloture"].iloc[0]
        if ancien and ancien > 0:
            perf = (prix / ancien - 1) * 100
    details["perf_1an"] = perf
    score_perf = _echelle(perf, -30, 60)

    score = _moyenne_ponderee([
        (score_mm, 0.40),
        (score_position, 0.25),
        (score_perf, 0.35),
    ])
    return score, details


# --------------------------------------------------------------------- RISQUE

def bloc_risque(df):
    """Volatilité, perte maximale et liquidité. Un score élevé = risque faible."""
    details = {}
    if df is None or len(df) < 20:
        return None, details

    fenetre = df.tail(252).copy()
    rendements = fenetre["cours_cloture"].pct_change().dropna()

    # Volatilité annualisée (252 séances de bourse par an)
    volatilite = None
    if len(rendements) > 5:
        volatilite = float(rendements.std() * np.sqrt(252) * 100)
    details["volatilite"] = volatilite
    score_vol = _echelle(volatilite, 60, 10)  # bornes inversées : moins = mieux

    # Perte maximale (plus forte baisse depuis un sommet) sur la période
    drawdown = None
    if len(fenetre) > 5:
        sommet = fenetre["cours_cloture"].cummax()
        drawdown = float((fenetre["cours_cloture"] / sommet - 1).min() * 100)
    details["drawdown"] = drawdown
    score_dd = _echelle(drawdown, -50, 0)

    # Liquidité : valeur moyenne échangée par séance, estimée en volume x cours
    liquidite = None
    if "volume" in fenetre:
        valeurs = (fenetre["volume"] * fenetre["cours_cloture"]).dropna()
        if len(valeurs) > 0:
            liquidite = float(valeurs.mean())
    details["liquidite"] = liquidite
    # Échelle logarithmique : 1 M FCFA/jour -> 0, 100 M FCFA/jour -> 100
    score_liq = None
    if liquidite and liquidite > 0:
        score_liq = _echelle(np.log10(liquidite), 6, 8)

    score = _moyenne_ponderee([
        (score_vol, 0.35),
        (score_dd, 0.30),
        (score_liq, 0.35),
    ])
    return score, details


# --------------------------------------------------------------- VALORISATION

def bloc_valorisation(rendement_dividende, per, secteur):
    details = {"rendement": rendement_dividende, "per": per, "secteur": secteur}

    # À défaut d'une vraie valeur comptable (non publiée à la BRVM), le rendement
    # du dividende sert d'approximation de la cherté du titre.
    score_rendement = _echelle(rendement_dividende, 0, 12)

    # PER : plus il est bas, moins le titre est cher (au-delà de 25, peu discriminant)
    score_per = _echelle(per, 25, 4) if per and per > 0 else None

    score_secteur = SOLIDITE_SECTEUR.get(secteur, 50)

    score = _moyenne_ponderee([
        (score_rendement, 0.50),
        (score_per, 0.30),
        (score_secteur, 0.20),
    ])
    return score, details


# ---------------------------------------------------------------------- TOTAL

def badge(score):
    """Libellé et couleur associés à une note globale."""
    if score is None:
        return "NON NOTÉ", "gris", "Pas assez de données pour noter cette valeur."
    if score >= 80:
        return "SOLIDE", "vert", "Profil robuste sur l'ensemble des critères."
    if score >= 65:
        return "INTÉRESSANT", "vert", "Bon profil, quelques points à surveiller."
    if score >= 50:
        return "CORRECT", "orange", "Profil moyen, à examiner de près."
    if score >= 35:
        return "FRAGILE", "orange", "Plusieurs critères faibles."
    return "RISQUÉ", "rouge", "Profil faible sur la majorité des critères."


def couleur_score(score):
    if score is None:
        return "gris"
    if score >= 70:
        return "vert"
    if score >= 45:
        return "orange"
    return "rouge"


def noter_valeur(df, historique_div, cours_actuel, per, secteur):
    """Calcule la note complète d'une valeur.
    Retourne un dict avec la note globale, les 4 sous-scores et leurs détails."""
    s_div, d_div = bloc_dividende(historique_div, cours_actuel)
    s_tend, d_tend = bloc_tendance(df)
    s_risq, d_risq = bloc_risque(df)
    s_valo, d_valo = bloc_valorisation(d_div.get("rendement"), per, secteur)

    # Le bloc Valorisation seul suffirait à produire un chiffre (le secteur est
    # toujours connu), ce qui donnerait une fausse impression de note fondée.
    # On exige donc qu'au moins deux blocs soient réellement calculables.
    blocs_disponibles = sum(1 for s in (s_div, s_tend, s_risq) if s is not None)
    if blocs_disponibles < 2:
        globale = None
    else:
        globale = _moyenne_ponderee([
            (s_div, PONDERATIONS["dividende"]),
            (s_tend, PONDERATIONS["tendance"]),
            (s_risq, PONDERATIONS["risque"]),
            (s_valo, PONDERATIONS["valorisation"]),
        ])

    return {
        "globale": round(globale) if globale is not None else None,
        "dividende": round(s_div) if s_div is not None else None,
        "tendance": round(s_tend) if s_tend is not None else None,
        "risque": round(s_risq) if s_risq is not None else None,
        "valorisation": round(s_valo) if s_valo is not None else None,
        "details_dividende": d_div,
        "details_tendance": d_tend,
        "details_risque": d_risq,
        "details_valorisation": d_valo,
    }


def drapeaux_rouges(note):
    """Signale les points d'alerte les plus nets. Liste vide = rien de majeur."""
    alertes = []
    d_div = note.get("details_dividende", {})
    d_risq = note.get("details_risque", {})
    d_tend = note.get("details_tendance", {})

    if d_div.get("annees_possibles") and d_div.get("annees_versees") is not None:
        if d_div["annees_versees"] <= d_div["annees_possibles"] / 2:
            alertes.append("Dividende versé de façon irrégulière sur la période connue.")
    if d_risq.get("volatilite") and d_risq["volatilite"] > 50:
        alertes.append(f"Volatilité très élevée ({d_risq['volatilite']:.0f} % par an).")
    if d_risq.get("drawdown") and d_risq["drawdown"] < -40:
        alertes.append(f"Forte baisse subie sur l'année ({d_risq['drawdown']:.0f} %).")
    if d_risq.get("liquidite") and d_risq["liquidite"] < 2_000_000:
        alertes.append("Liquidité faible : revendre peut prendre du temps.")
    if d_tend.get("tendance_libelle", "").startswith("baissière"):
        alertes.append("Tendance de fond baissière.")
    return alertes
