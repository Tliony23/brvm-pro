"""
Indicateurs d'analyse technique, calculés à partir de l'historique des cours
de clôture déjà stocké en base (aucune donnée externe nécessaire).
"""
import pandas as pd


def moyenne_mobile(df, colonne="cours_cloture", fenetre=20):
    """Moyenne mobile simple (SMA) sur `fenetre` jours."""
    return df[colonne].rolling(window=fenetre, min_periods=fenetre).mean()


def rsi(df, colonne="cours_cloture", fenetre=14):
    """RSI (Relative Strength Index) classique sur `fenetre` jours."""
    delta = df[colonne].diff()
    gains = delta.clip(lower=0)
    pertes = -delta.clip(upper=0)

    moyenne_gains = gains.rolling(window=fenetre, min_periods=fenetre).mean()
    moyenne_pertes = pertes.rolling(window=fenetre, min_periods=fenetre).mean()

    assez_de_donnees = moyenne_gains.notna() & moyenne_pertes.notna()

    rs = moyenne_gains / moyenne_pertes.replace(0, pd.NA)
    valeur_rsi = 100 - (100 / (1 + rs))
    # Cas particulier : aucune perte sur la fenêtre (mais assez de données) -> RSI = 100
    # (à ne pas confondre avec le NaN légitime de la période de préchauffage)
    valeur_rsi = valeur_rsi.where(~(assez_de_donnees & (moyenne_pertes == 0)), 100)
    return valeur_rsi


def bandes_bollinger(df, colonne="cours_cloture", fenetre=20, k=2):
    """Bandes de Bollinger : SMA ± k * écart-type glissant."""
    sma = moyenne_mobile(df, colonne, fenetre)
    ecart_type = df[colonne].rolling(window=fenetre, min_periods=fenetre).std()
    bande_haute = sma + k * ecart_type
    bande_basse = sma - k * ecart_type
    return sma, bande_haute, bande_basse


def ajouter_tous_les_indicateurs(df, colonne="cours_cloture"):
    """Ajoute toutes les colonnes d'indicateurs à un DataFrame trié par date."""
    df = df.copy()
    df["sma20"] = moyenne_mobile(df, colonne, 20)
    df["sma50"] = moyenne_mobile(df, colonne, 50)
    df["sma200"] = moyenne_mobile(df, colonne, 200)
    df["rsi14"] = rsi(df, colonne, 14)
    df["bb_sma"], df["bb_haute"], df["bb_basse"] = bandes_bollinger(df, colonne, 20, 2)
    return df
