"""
BRVM Pro — suivi de portefeuille et analyse des valeurs cotées à la BRVM.

Lancement : streamlit run app.py
"""
from datetime import date, datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import scraper_brvm
from db import (
    basculer_favori,
    derniere_seance,
    get_dividendes_a_venir,
    get_dividendes_historique,
    get_favoris,
    get_fondamentaux,
    get_historique,
    get_portefeuille,
    get_tous_derniers_cours,
    get_liquidites,
    init_db,
    init_parametres,
    init_portefeuille,
    set_liquidites,
    set_position,
    supprimer_position,
    upsert_prix,
)
from indicateurs import ajouter_tous_les_indicateurs
from portefeuille import (
    courbe_portefeuille,
    dernier_dividende_connu,
    dividendes_attendus,
    lignes_portefeuille,
    repartition,
    resume_portefeuille,
    revenu_dividendes,
)
from referentiel import SECTEURS, VALEURS, get_nom, get_pays, get_secteur
from scoring import badge, couleur_score, drapeaux_rouges, noter_valeur

st.set_page_config(page_title="BRVM Pro", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

VERT, ROUGE, ORANGE, GRIS = "#22c55e", "#ef4444", "#f59e0b", "#9ca3af"
COULEURS = {"vert": VERT, "orange": ORANGE, "rouge": ROUGE, "gris": GRIS}

st.markdown("""
<style>
  /* Les couleurs de fond et de bordure sont volontairement semi-transparentes :
     elles s'adaptent ainsi au thème clair comme au thème sombre de Streamlit. */
  .block-container {padding-top: 2rem; max-width: 1100px;}
  .carte {background:rgba(128,128,128,.07); border:1px solid rgba(128,128,128,.25);
          border-radius:14px; padding:14px 16px; margin-bottom:10px;}
  .badge-ticker {display:inline-block; background:rgba(22,163,74,.15); color:#22c55e;
          font-weight:700; font-size:12px; padding:6px 9px; border-radius:9px;
          letter-spacing:.4px; min-width:52px; text-align:center;}
  .titre-valeur {font-weight:700; font-size:15px; margin:0;}
  .sous-titre {opacity:.65; font-size:12.5px; margin:2px 0 0 0;}
  .prix {font-weight:700; font-size:16px; text-align:right;}
  .vert {color:#22c55e;} .rouge {color:#ef4444;}
  .orange {color:#f59e0b;} .gris {opacity:.55;}
  .mini {opacity:.65; font-size:12px;}
  .section {font-size:11.5px; font-weight:700; letter-spacing:1.3px;
          opacity:.65; margin:18px 0 8px 0;}
  .pilule {display:inline-block; padding:3px 10px; border-radius:999px;
          font-size:11px; font-weight:700; border:1.5px solid;}
  .barre-fond {background:rgba(128,128,128,.22); border-radius:999px; height:9px; width:100%;}
  .barre {height:9px; border-radius:999px;}
  div[data-testid="stMetricValue"] {font-size:23px;}
</style>
""", unsafe_allow_html=True)

def _mot_de_passe_attendu():
    """Renvoie le mot de passe configuré, ou None s'il n'y en a pas.
    En local, aucun secret n'est défini : l'application s'ouvre directement."""
    try:
        return st.secrets.get("mot_de_passe")
    except Exception:
        return None


def verifier_acces():
    """Porte d'entrée de l'application hébergée.

    Sans mot de passe configuré (cas de ton ordinateur), on passe directement.
    En ligne, tant que le mot de passe n'est pas saisi, RIEN d'autre n'est
    affiché ni chargé : ni ton portefeuille, ni tes positions.
    """
    attendu = _mot_de_passe_attendu()
    if not attendu:
        return True
    if st.session_state.get("acces_autorise"):
        return True

    st.markdown("### 📈 BRVM <span class='vert'>Pro</span>", unsafe_allow_html=True)
    st.caption("Accès protégé — saisis ton mot de passe pour continuer.")
    saisie = st.text_input("Mot de passe", type="password",
                           label_visibility="collapsed", key="saisie_mdp")
    if st.button("Entrer", type="primary"):
        if saisie == attendu:
            st.session_state.acces_autorise = True
            st.rerun()
        else:
            st.error("Mot de passe incorrect.")
    return False


if not verifier_acces():
    st.stop()


init_db()
init_portefeuille()
init_parametres()

MOIS_FR = ["janv.", "févr.", "mars", "avril", "mai", "juin",
           "juil.", "août", "sept.", "oct.", "nov.", "déc."]
JOURS_FR = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def date_fr(iso):
    if not iso:
        return "—"
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()
    except ValueError:
        return str(iso)
    return f"{JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month - 1]} {d.year}"


def fmt(v, suffixe=" F", decimales=0):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return f"{v:,.{decimales}f}".replace(",", " ").replace(".", ",") + suffixe


def signe(v, suffixe=" F", decimales=0):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—", "gris"
    txt = ("+" if v >= 0 else "") + fmt(v, suffixe, decimales)
    return txt, ("vert" if v >= 0 else "rouge")


def couleur_html(txt, classe):
    return f"<span class='{classe}'>{txt}</span>"


@st.cache_data(ttl=1800, show_spinner=False)
def charger_df(symbole, seance=None):
    """Historique enrichi des indicateurs.

    Le cache est indexé sur la date de la dernière séance : il reste donc
    valide tant qu'aucune donnée nouvelle n'arrive, et se renouvelle de
    lui-même dès que c'est le cas. Le délai de 30 min est un simple filet.
    """
    hist = get_historique(symbole)
    if not hist or len(hist) < 2:
        return None
    df = pd.DataFrame(hist, columns=["date", "cours_ouverture", "cours_haut",
                                     "cours_bas", "cours_cloture", "volume"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").dropna(subset=["cours_cloture"]).reset_index(drop=True)
    if len(df) < 2:
        return None
    df = ajouter_tous_les_indicateurs(df)
    # Filet de sécurité : si un module est resté dans une version antérieure,
    # on crée les colonnes manquantes vides plutôt que de laisser planter
    # l'affichage. L'indicateur concerné ne s'affichera simplement pas.
    for colonne in ("sma20", "sma50", "sma200", "rsi14", "bb_sma", "bb_haute", "bb_basse"):
        if colonne not in df.columns:
            df[colonne] = pd.NA
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def note_de(symbole, seance=None):
    df = charger_df(symbole, seance)
    hist_div = get_dividendes_historique(symbole)
    cours = df["cours_cloture"].iloc[-1] if df is not None and len(df) else None
    fonda = get_fondamentaux(symbole)
    per = None
    for ligne in reversed(fonda):
        if ligne[6] is not None:
            per = ligne[6]
            break
    return noter_valeur(df, hist_div, cours, per, get_secteur(symbole))


@st.cache_data(ttl=1800, show_spinner=False)
def lignes_marche(seance=None):
    """Une ligne par valeur cotée pour l'onglet Marché (48 requêtes évitées
    à chaque interaction grâce au cache)."""
    cours = get_tous_derniers_cours()
    rangees = []
    for symbole in VALEURS:
        infos = cours.get(symbole)
        if not infos:
            continue
        _, cloture, veille, volume = infos
        var_pct = ((cloture - veille) / veille * 100) if (cloture and veille) else None
        div = dernier_dividende_connu(symbole)
        rendement = (div / cloture * 100) if (div and cloture) else None
        rangees.append({"symbole": symbole, "nom": get_nom(symbole),
                        "secteur": get_secteur(symbole), "cours": cloture,
                        "var": var_pct, "rendement": rendement, "volume": volume})
    return rangees


PERIODES = {"1S": 7, "1M": 30, "3M": 91, "6M": 182, "CA": None,
            "1A": 365, "5A": 1826, "MAX": None}


def filtrer_periode(df, cle):
    if df is None or df.empty:
        return df
    fin = df["date"].max()
    if cle == "MAX":
        return df
    if cle == "CA":
        debut = pd.Timestamp(year=fin.year, month=1, day=1)
    else:
        debut = fin - pd.Timedelta(days=PERIODES[cle])
    filtre = df[df["date"] >= debut]
    return filtre if len(filtre) >= 2 else df


def variation_periode(df):
    """Pourcentage de variation entre le premier et le dernier point affichés."""
    if df is None or len(df) < 2:
        return None
    debut, fin = df["cours_cloture"].iloc[0], df["cours_cloture"].iloc[-1]
    return (fin / debut - 1) * 100 if debut else None


# ============================================================== EN-TÊTE

seance = derniere_seance()
h1, h2 = st.columns([3, 1])
with h1:
    st.markdown(
        f"### 📈 BRVM <span class='vert'>Pro</span>"
        f"<div class='mini'>Séance du {date_fr(seance)}</div>",
        unsafe_allow_html=True,
    )
with h2:
    if st.button("🔄 Actualiser", width='stretch', type="primary"):
        with st.spinner("Récupération des cours…"):
            try:
                rows = scraper_brvm.fetch_cours_du_jour()
                upsert_prix(rows)
                st.cache_data.clear()
                st.success(f"{len(rows)} valeurs mises à jour.")
            except Exception as e:
                st.error(f"Échec : {e}")
        st.rerun()

cours_marche = get_tous_derniers_cours()
if not cours_marche:
    st.warning(
        "Aucune donnée en base. Lance `2_premiere_recuperation.bat`, "
        "puis `4_historique_15ans.bat` et `5_dividendes.bat`."
    )
    st.stop()

favoris = get_favoris()
onglets = st.tabs(["🏠 Accueil", "📊 Marché", "💰 Dividendes",
                   "💼 Portefeuille", "🧭 Analyse"])


# ============================================================== FICHE VALEUR

def fiche_valeur(symbole, cle):
    """Panneau détaillé d'une valeur : cours, graphique, analyse, fondamentaux."""
    df = charger_df(symbole, seance)
    infos = cours_marche.get(symbole)
    cours = infos[1] if infos else None
    veille = infos[2] if infos else None
    volume = infos[3] if infos else None
    var_pct = ((cours - veille) / veille * 100) if (cours and veille) else None

    st.markdown(f"### {get_nom(symbole)}")
    st.markdown(
        f"<div class='mini'>{symbole} · {get_secteur(symbole)} · {get_pays(symbole)}</div>",
        unsafe_allow_html=True,
    )
    txt, cls = signe(var_pct, " %", 2)
    ligne_var = couleur_html(f"{txt} aujourd'hui", cls)
    st.markdown(
        f"<div style='font-size:30px;font-weight:700;margin-top:6px'>{fmt(cours)}</div>"
        f"<div>{ligne_var}</div>"
        f"<div class='mini'>Volume de la séance : {fmt(volume, ' titres')}</div>",
        unsafe_allow_html=True,
    )

    if st.button(("★ Suivi" if symbole in favoris else "☆ Suivre"), key=f"fav_{cle}_{symbole}"):
        basculer_favori(symbole)
        st.rerun()

    vue = st.radio("Vue", ["Graphique", "Analyse", "Fondamentaux"],
                   horizontal=True, key=f"vue_{cle}_{symbole}", label_visibility="collapsed")

    if vue == "Graphique":
        _vue_graphique(df, symbole, cle)
    elif vue == "Analyse":
        _vue_analyse(symbole)
    else:
        _vue_fondamentaux(symbole, cle)

    st.markdown("<div class='section'>HISTORIQUE DES DIVIDENDES</div>", unsafe_allow_html=True)
    hist_div = get_dividendes_historique(symbole)
    if hist_div:
        tab = pd.DataFrame(hist_div, columns=["Année", "Dividende / action", "Rendement"])
        tab["Dividende / action"] = tab["Dividende / action"].apply(lambda v: fmt(v))
        tab["Rendement"] = tab["Rendement"].apply(
            lambda v: fmt(v, " %", 2) if v is not None else "—")
        st.dataframe(tab.iloc[::-1], hide_index=True, width='stretch',
                     key=f"td_{cle}_{symbole}")
    else:
        st.caption("Aucun dividende connu pour cette valeur.")


def _vue_graphique(df, symbole, cle):
    if df is None:
        st.info("Pas d'historique pour cette valeur. Lance `4_historique_15ans.bat`.")
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    periode = c1.radio("Période", list(PERIODES.keys()), index=5,
                       horizontal=True, key=f"per_{cle}_{symbole}",
                       label_visibility="collapsed")
    type_g = c2.selectbox("Type", ["Courbe", "Bougies"], key=f"typ_{cle}_{symbole}",
                          label_visibility="collapsed")
    mm = c3.multiselect("Moyennes", ["MM50", "MM200"], default=["MM50", "MM200"],
                        key=f"mm_{cle}_{symbole}", label_visibility="collapsed")

    vue = filtrer_periode(df, periode)
    fig = go.Figure()

    if type_g == "Bougies":
        haut = vue["cours_haut"].fillna(vue[["cours_ouverture", "cours_cloture"]].max(axis=1))
        bas = vue["cours_bas"].fillna(vue[["cours_ouverture", "cours_cloture"]].min(axis=1))
        ouv = vue["cours_ouverture"].fillna(vue["cours_cloture"])
        fig.add_trace(go.Candlestick(x=vue["date"], open=ouv, high=haut, low=bas,
                                     close=vue["cours_cloture"], name="Cours",
                                     increasing_line_color=VERT, decreasing_line_color=ROUGE))
    else:
        fig.add_trace(go.Scatter(x=vue["date"], y=vue["cours_cloture"], name="Cours",
                                 line=dict(color=VERT, width=2), fill="tozeroy",
                                 fillcolor="rgba(34,197,94,0.12)"))

    if "MM50" in mm and vue["sma50"].notna().any():
        fig.add_trace(go.Scatter(x=vue["date"], y=vue["sma50"], name="MM50",
                                 line=dict(color="#f59e0b", width=1.4, dash="dot")))
    if "MM200" in mm and vue["sma200"].notna().any():
        fig.add_trace(go.Scatter(x=vue["date"], y=vue["sma200"], name="MM200",
                                 line=dict(color="#6366f1", width=1.4, dash="dot")))

    fig.update_layout(height=380, margin=dict(t=10, b=10, l=0, r=0),
                      hovermode="x unified", xaxis_rangeslider_visible=False,
                      yaxis_title="FCFA", showlegend=True,
                      legend=dict(orientation="h", y=1.06, x=1, xanchor="right"))
    if type_g == "Courbe":
        bas_y = vue["cours_cloture"].min() * 0.95
        fig.update_yaxes(range=[bas_y, vue["cours_cloture"].max() * 1.03])
    st.plotly_chart(fig, width='stretch', key=f"g_{cle}_{symbole}")

    var = variation_periode(vue)
    txt, cls = signe(var, " %", 2)
    st.markdown(
        f"<div class='mini' style='text-align:center'>{len(vue)} séances · "
        f"{couleur_html(txt, cls)} sur la période</div>",
        unsafe_allow_html=True,
    )


def _barre_bloc(titre, poids, score):
    cls = couleur_score(score)
    largeur = score if score is not None else 0
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;align-items:baseline'>"
        f"<div><b>{titre}</b> <span class='mini'>{poids}</span></div>"
        f"<div class='{cls}' style='font-size:19px;font-weight:700'>"
        f"{score if score is not None else '—'}</div></div>"
        f"<div class='barre-fond'><div class='barre' style='width:{largeur}%;"
        f"background:{COULEURS[cls]}'></div></div>",
        unsafe_allow_html=True,
    )


def _ligne_critere(libelle, valeur, score_indicatif=None):
    cls = couleur_score(score_indicatif) if score_indicatif is not None else "gris"
    st.markdown(
        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
        f"border-bottom:1px solid #f3f4f6'>"
        f"<span><span class='{cls}'>●</span> {libelle}</span>"
        f"<span style='text-align:right'>{valeur}</span></div>",
        unsafe_allow_html=True,
    )


def _vue_analyse(symbole):
    note = note_de(symbole, seance)
    g = note["globale"]
    lib, coul, phrase = badge(g)

    c1, c2 = st.columns([1, 3])
    c1.markdown(
        f"<div style='text-align:center'>"
        f"<div style='font-size:38px;font-weight:800;color:{COULEURS[coul]}'>"
        f"{g if g is not None else '—'}</div><div class='mini'>/100</div></div>",
        unsafe_allow_html=True,
    )
    c2.markdown(
        f"<span class='pilule' style='color:{COULEURS[coul]};border-color:{COULEURS[coul]}'>"
        f"{lib}</span><div class='mini' style='margin-top:6px'>{phrase}</div>",
        unsafe_allow_html=True,
    )

    if g is None:
        st.info("Historique insuffisant pour noter cette valeur. "
                "Lance `4_historique_15ans.bat` pour récupérer les cours passés.")
        return

    st.write("")
    d = note["details_dividende"]
    _barre_bloc("Dividende & rendement", "30 %", note["dividende"])
    _ligne_critere("Rendement du dividende", fmt(d.get("rendement"), " %", 2),
                   min(100, (d.get("rendement") or 0) / 12 * 100))
    _ligne_critere("Croissance du dividende (CAGR)",
                   signe(d.get("cagr"), " %", 1)[0] if d.get("cagr") is not None else "—",
                   min(100, max(0, ((d.get("cagr") or 0) + 20) / 45 * 100)))
    _ligne_critere("Régularité (années versées)",
                   f"{d.get('annees_versees', 0)} / {d.get('annees_possibles', 0)} an(s)",
                   (d.get("annees_versees", 0) / d["annees_possibles"] * 100)
                   if d.get("annees_possibles") else None)

    st.write("")
    t = note["details_tendance"]
    _barre_bloc("Tendance & momentum", "25 %", note["tendance"])
    _ligne_critere("Tendance (moyennes mobiles)", t.get("tendance_libelle", "—"),
                   note["tendance"])
    _ligne_critere("Position dans le range 52 sem.", fmt(t.get("position_52s"), " %", 0),
                   t.get("position_52s"))
    _ligne_critere("Performance 1 an",
                   signe(t.get("perf_1an"), " %", 1)[0] if t.get("perf_1an") is not None else "—",
                   min(100, max(0, ((t.get("perf_1an") or 0) + 30) / 90 * 100)))

    st.write("")
    r = note["details_risque"]
    _barre_bloc("Risque & liquidité", "25 %", note["risque"])
    _ligne_critere("Volatilité annualisée", fmt(r.get("volatilite"), " %", 1),
                   max(0, min(100, (60 - (r.get("volatilite") or 60)) / 50 * 100)))
    _ligne_critere("Perte max. sur 1 an", fmt(r.get("drawdown"), " %", 1),
                   max(0, min(100, ((r.get("drawdown") or -50) + 50) / 50 * 100)))
    liq = r.get("liquidite")
    _ligne_critere("Liquidité (val. éch./jour)",
                   f"{liq / 1e6:.1f} M FCFA" if liq else "—",
                   min(100, (liq or 0) / 5e7 * 100))

    st.write("")
    v = note["details_valorisation"]
    _barre_bloc("Valorisation", "20 %", note["valorisation"])
    _ligne_critere("Rendement vs prix (approx. de valeur)", fmt(v.get("rendement"), " %", 2),
                   min(100, (v.get("rendement") or 0) / 12 * 100))
    _ligne_critere("PER (dernier exercice connu)",
                   f"{v['per']:.2f} ×" if v.get("per") else "non publié", None)
    _ligne_critere("Secteur (solidité BRVM)", v.get("secteur", "—"), None)

    st.write("")
    alertes = drapeaux_rouges(note)
    if alertes:
        for a in alertes:
            st.markdown(f"<div class='rouge'>⚠ {a}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='vert'>✓ Aucun drapeau rouge majeur détecté.</div>",
                    unsafe_allow_html=True)

    st.caption(
        "Analyse quantitative calculée à partir de l'historique BRVM (cours, dividendes, "
        "secteur). Outil de comparaison et d'aide à la décision — ce n'est pas un conseil "
        "financier, et un score élevé ne garantit aucune performance future."
    )


def _vue_fondamentaux(symbole, cle):
    fonda = get_fondamentaux(symbole)
    if not fonda:
        st.info("Aucune donnée fondamentale. Lance `2_premiere_recuperation.bat`.")
        return
    df = pd.DataFrame(fonda, columns=["Exercice", "Chiffre d'affaires", "Croissance CA",
                                      "Résultat net", "Croissance RN", "BNPA", "PER",
                                      "Dividende / action"])
    fig = make_subplots(rows=1, cols=2, subplot_titles=("Chiffre d'affaires", "Résultat net"))
    fig.add_trace(go.Bar(x=df["Exercice"], y=df["Chiffre d'affaires"],
                         marker_color=VERT, showlegend=False), row=1, col=1)
    fig.add_trace(go.Bar(x=df["Exercice"], y=df["Résultat net"],
                         marker_color=VERT, showlegend=False), row=1, col=2)
    fig.update_layout(height=250, margin=dict(t=32, b=10, l=0, r=0))
    st.plotly_chart(fig, width='stretch', key=f"f_{cle}_{symbole}")
    st.dataframe(df.set_index("Exercice").T, width='stretch',
                 key=f"tf_{cle}_{symbole}")
    st.caption("Chiffre d'affaires et résultat net en FCFA. Source : Sikafinance.")


# ============================================================== ACCUEIL

with onglets[0]:
    lignes = lignes_portefeuille()
    r = resume_portefeuille(lignes)
    if r is None:
        st.info("Ton portefeuille est vide. Ajoute une position ou saisis tes "
                "liquidités dans l'onglet **Portefeuille**.")
    else:
        txt_pv, cls_pv = signe(r["pv"])
        txt_pct, _ = signe(r["pv_pct"], " %", 2)
        detail = (f"Actions {fmt(r['valeur'])} · Liquidités {fmt(r['liquidites'])}"
                  if r["liquidites"] else "")
        pv_ligne = (couleur_html(f"{txt_pv} ({txt_pct}) sur les actions", cls_pv)
                    if r["nb_positions"] else "")
        st.markdown(
            f"<div class='carte' style='text-align:center'>"
            f"<div class='mini'>Valeur totale</div>"
            f"<div style='font-size:34px;font-weight:800'>{fmt(r['total'])}</div>"
            f"<div>{pv_ligne}</div>"
            f"<div class='mini'>{detail}</div></div>",
            unsafe_allow_html=True,
        )

        if not lignes:
            st.caption("Aucune action en portefeuille : seules tes liquidités sont comptées.")
        c1, c2 = st.columns([3, 1])
        c1.markdown("**Évolution**")
        per = c2.selectbox("Période", ["1M", "3M", "6M", "1A", "MAX"], index=3,
                           key="per_acc", label_visibility="collapsed")
        jours = {"1M": 30, "3M": 91, "6M": 182, "1A": 365, "MAX": None}[per]
        courbe = courbe_portefeuille(lignes, jours)

        if len(courbe) >= 2:
            var = (courbe["valeur"].iloc[-1] / courbe["valeur"].iloc[0] - 1) * 100
            t, c = signe(var, " %", 2)
            st.markdown(
                f"<div style='text-align:right' class='mini'>"
                f"{couleur_html(t, c)} sur la période</div>",
                unsafe_allow_html=True,
            )
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=courbe["date"], y=courbe["valeur"], name="Valeur",
                                     line=dict(color=VERT, width=2), fill="tozeroy",
                                     fillcolor="rgba(34,197,94,0.12)"))
            fig.add_hline(y=r["investi"], line_dash="dash", line_color="#9ca3af",
                          annotation_text="Investi", annotation_position="right")
            fig.update_layout(height=280, margin=dict(t=10, b=10, l=0, r=0),
                              hovermode="x unified", showlegend=False)
            fig.update_yaxes(range=[min(courbe["valeur"].min(), r["investi"]) * 0.9,
                                    courbe["valeur"].max() * 1.05])
            st.plotly_chart(fig, width='stretch')
            st.caption("Courbe reconstituée en appliquant tes quantités actuelles aux cours "
                       "passés : c'est ce que ton portefeuille d'aujourd'hui aurait valu, "
                       "pas sa valeur réelle à chaque date.")
        else:
            st.caption("Pas assez d'historique pour tracer la courbe.")

        revenus = revenu_dividendes(lignes)
        total_div = sum(x["revenu_annuel"] for x in revenus)
        t_jour, _ = signe(r["var_jour"])
        t_jour_pct, _ = signe(r["var_jour_pct"], " %", 2)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Variation du jour", t_jour, t_jour_pct)
        m2.metric("Revenu annuel estimé", fmt(total_div))
        m3.metric("Investi en actions", fmt(r["investi"]))
        m4.metric("Liquidités", fmt(r["liquidites"]))
        m5.metric("Positions", str(r["nb_positions"]))

        if r["meilleure"] and r["pire"]:
            b1, b2 = st.columns(2)
            tb, _ = signe(r["meilleure"]["pv_pct"], " %", 2)
            tp, cp = signe(r["pire"]["pv_pct"], " %", 2)
            b1.markdown(
                f"<div class='carte'><div class='mini'>▲ Meilleure ligne</div>"
                f"<div class='titre-valeur'>{r['meilleure']['nom']}</div>"
                f"{couleur_html(tb, 'vert')}</div>", unsafe_allow_html=True)
            b2.markdown(
                f"<div class='carte'><div class='mini'>▼ Moins bonne</div>"
                f"<div class='titre-valeur'>{r['pire']['nom']}</div>"
                f"{couleur_html(tp, cp)}</div>", unsafe_allow_html=True)

        st.markdown("<div class='section'>RÉPARTITION</div>", unsafe_allow_html=True)
        par = st.radio("Répartition par", ["Secteur", "Valeur"], horizontal=True,
                       key="rep", label_visibility="collapsed")
        parts = repartition(lignes, "secteur" if par == "Secteur" else "valeur")
        if parts:
            g1, g2 = st.columns([1, 1])
            fig = go.Figure(go.Pie(
                labels=[p["libelle"] for p in parts], values=[p["valeur"] for p in parts],
                hole=.62, textinfo="none",
                marker=dict(colors=["#16a34a", "#f59e0b", "#3b82f6", "#8b5cf6", "#14b8a6",
                                    "#ef4444", "#a855f7", "#eab308", "#6b7280"])))
            fig.update_layout(height=260, margin=dict(t=6, b=6, l=0, r=0), showlegend=False,
                              annotations=[dict(text=f"<b>{len(parts)}</b><br>"
                                                f"{'secteurs' if par == 'Secteur' else 'valeurs'}",
                                                showarrow=False, font_size=15)])
            g1.plotly_chart(fig, width='stretch')
            with g2:
                for p in parts:
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:3px 0'>"
                        f"<span>{p['libelle']}</span><b>{p['pct']:.1f} %</b></div>",
                        unsafe_allow_html=True)

        attendus = dividendes_attendus(lignes)
        if attendus:
            st.markdown("<div class='section'>PROCHAINS DIVIDENDES (MON PORTEFEUILLE)</div>",
                        unsafe_allow_html=True)
            for a in attendus[:5]:
                c1, c2 = st.columns([3, 1])
                c1.markdown(
                    f"<span class='badge-ticker'>{a['symbole']}</span> "
                    f"<b>{a['nom']}</b><div class='mini'>Détachement : "
                    f"{date_fr(a['date']) if a['date'] else a['date_brute']}</div>",
                    unsafe_allow_html=True)
                c2.markdown(
                    f"<div class='prix vert'>{fmt(a['montant_total'])}</div>",
                    unsafe_allow_html=True)


# ============================================================== MARCHÉ

with onglets[1]:
    recherche = st.text_input("Rechercher", placeholder="Rechercher une valeur (ex : SNTS, Sonatel…)",
                              label_visibility="collapsed")
    f1, f2 = st.columns([2, 2])
    filtre = f1.selectbox("Secteur", ["Toutes", "★ Suivi"] + SECTEURS,
                          label_visibility="collapsed")
    tri = f2.radio("Trier", ["Nom", "Variation", "Rendement", "Cours"],
                   horizontal=True, key="tri_m", label_visibility="collapsed")

    rangees = lignes_marche(seance)

    if recherche:
        q = recherche.lower().strip()
        rangees = [r for r in rangees if q in r["symbole"].lower() or q in r["nom"].lower()]
    if filtre == "★ Suivi":
        rangees = [r for r in rangees if r["symbole"] in favoris]
    elif filtre != "Toutes":
        rangees = [r for r in rangees if r["secteur"] == filtre]

    cles = {"Nom": ("nom", False), "Variation": ("var", True),
            "Rendement": ("rendement", True), "Cours": ("cours", True)}
    cle, decroissant = cles[tri]
    rangees.sort(key=lambda r: (r[cle] is None, r[cle] if r[cle] is not None else 0),
                 reverse=decroissant)

    sel = st.session_state.get("sel_marche")
    if sel:
        with st.container(border=True):
            if st.button("✕ Fermer le détail", key="fermer_m"):
                st.session_state.sel_marche = None
                st.rerun()
            fiche_valeur(sel, "m")
        st.divider()

    st.caption(f"{len(rangees)} valeur(s)")
    for r in rangees:
        c1, c2, c3, c4 = st.columns([1, 4, 2, 1])
        c1.markdown(f"<span class='badge-ticker'>{r['symbole']}</span>", unsafe_allow_html=True)
        etoile = "★ " if r["symbole"] in favoris else ""
        sous = r["secteur"] + (f" · rend. {r['rendement']:.1f} %" if r["rendement"] else "")
        c2.markdown(
            f"<div class='titre-valeur'>{etoile}{r['nom']}</div>"
            f"<div class='sous-titre'>{sous}</div>", unsafe_allow_html=True)
        t, cl = signe(r["var"], " %", 2)
        c3.markdown(
            f"<div class='prix'>{fmt(r['cours'])}</div>"
            f"<div class='prix {cl}' style='font-size:13px'>{t}</div>"
            f"<div class='mini' style='text-align:right'>vol {fmt(r['volume'], '')}</div>",
            unsafe_allow_html=True)
        if c4.button("Voir", key=f"voir_m_{r['symbole']}", width='stretch'):
            st.session_state.sel_marche = r["symbole"]
            st.rerun()


# ============================================================== DIVIDENDES

with onglets[2]:
    vue_div = st.radio("Vue", ["Mon portefeuille", "Tout le marché"],
                       horizontal=True, key="vd", label_visibility="collapsed")
    lignes = lignes_portefeuille()

    if vue_div == "Mon portefeuille":
        if not lignes:
            st.info("Ajoute d'abord des positions dans l'onglet **Portefeuille**.")
        else:
            revenus = revenu_dividendes(lignes)
            total = sum(x["revenu_annuel"] for x in revenus)
            c1, c2 = st.columns(2)
            c1.metric("Revenu annuel projeté (brut)", fmt(total),
                      f"{len(revenus)} valeur(s) distributrice(s)")
            attendus = dividendes_attendus(lignes)
            a_venir_total = sum(a["montant_total"] for a in attendus
                                if a["montant_total"] and a["date"])
            c2.metric("Détachements annoncés à venir", fmt(a_venir_total))
            st.caption(
                "Montants **bruts**, avant retenue à la source (l'IRVM est prélevé par la "
                "société et varie selon le pays). Projection fondée sur le dernier dividende "
                "connu de chaque société : un versement identique n'est jamais garanti."
            )

            st.markdown("<div class='section'>REVENU ANNUEL PAR VALEUR</div>",
                        unsafe_allow_html=True)
            for x in revenus:
                c1, c2, c3 = st.columns([1, 4, 2])
                c1.markdown(f"<span class='badge-ticker'>{x['symbole']}</span>",
                            unsafe_allow_html=True)
                c2.markdown(
                    f"<div class='titre-valeur'>{x['nom']}</div><div class='sous-titre'>"
                    f"{x['quantite']:.0f} × {fmt(x['div_unitaire'], ' F/action')} · "
                    f"rendement/coût {x['rendement_sur_cout']:.1f} %</div>",
                    unsafe_allow_html=True)
                c3.markdown(
                    f"<div class='prix vert'>{fmt(x['revenu_annuel'])}</div>"
                    f"<div class='mini' style='text-align:right'>/ an</div>",
                    unsafe_allow_html=True)

            if attendus:
                st.markdown("<div class='section'>À ENCAISSER</div>", unsafe_allow_html=True)
                for a in attendus:
                    c1, c2, c3 = st.columns([1, 4, 2])
                    c1.markdown(f"<span class='badge-ticker'>{a['symbole']}</span>",
                                unsafe_allow_html=True)
                    quand = date_fr(a["date"]) if a["date"] else "date à préciser"
                    c2.markdown(
                        f"<div class='titre-valeur'>{a['nom']}</div>"
                        f"<div class='sous-titre'>Détachement : {quand}</div>",
                        unsafe_allow_html=True)
                    c3.markdown(f"<div class='prix vert'>+ {fmt(a['montant_total'])}</div>",
                                unsafe_allow_html=True)
    else:
        tous = get_dividendes_a_venir()
        if not tous:
            st.info("Aucun dividende annoncé en base. Lance `5_dividendes.bat`.")
        else:
            aujourdhui = date.today()
            groupes = {}
            for symbole, d_iso, d_brute, montant, rendement in tous:
                groupes.setdefault(d_iso or "__inconnu__", []).append(
                    (symbole, montant, rendement, d_brute))
            for cle_date in sorted(groupes, key=lambda k: (k == "__inconnu__", k)):
                if cle_date == "__inconnu__":
                    st.markdown("**Date à préciser**")
                else:
                    reste = (datetime.strptime(cle_date, "%Y-%m-%d").date() - aujourdhui).days
                    suffixe = (f"<span class='orange'>dans {reste} j</span>" if reste >= 0
                               else "<span class='mini'>passé</span>")
                    st.markdown(f"**{date_fr(cle_date)}** &nbsp; {suffixe}",
                                unsafe_allow_html=True)
                for symbole, montant, rendement, _ in groupes[cle_date]:
                    c1, c2, c3 = st.columns([1, 4, 2])
                    c1.markdown(f"<span class='badge-ticker'>{symbole}</span>",
                                unsafe_allow_html=True)
                    c2.markdown(
                        f"<div class='titre-valeur'>{get_nom(symbole)}</div>"
                        f"<div class='sous-titre'>Dividende "
                        f"{fmt(montant, ' FCFA/action', 2)}</div>", unsafe_allow_html=True)
                    c3.markdown(
                        f"<div class='prix vert'>{fmt(rendement, ' %', 2)}</div>"
                        f"<div class='mini' style='text-align:right'>rendement</div>",
                        unsafe_allow_html=True)


# ============================================================== PORTEFEUILLE

with onglets[3]:
    liq_actuelles = get_liquidites()
    with st.expander(f"💵 Liquidités : {fmt(liq_actuelles)}", expanded=False):
        st.caption("Montant en espèces disponible sur ton compte-titres, non investi "
                   "en actions. Il compte dans ta valeur totale et dans la répartition, "
                   "mais pas dans le calcul de tes plus-values.")
        lc1, lc2 = st.columns([3, 1])
        nouveau = lc1.number_input("Montant en FCFA", min_value=0.0, step=1000.0,
                                   value=float(liq_actuelles), key="liq_input",
                                   label_visibility="collapsed")
        if lc2.button("Enregistrer", key="liq_save", width='stretch'):
            set_liquidites(nouveau)
            st.success(f"Liquidités enregistrées : {fmt(nouveau)}")
            st.rerun()

    with st.expander("➕ Ajouter ou modifier une position", expanded=False):
        with st.form("ajout", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            options = [f"{s} — {get_nom(s)}" for s in sorted(VALEURS)]
            choix = c1.selectbox("Valeur", options)
            qte = c2.number_input("Nombre d'actions", min_value=0.0, step=1.0, value=1.0)
            pru = c3.number_input("Coût moyen d'achat (F)", min_value=0.0, step=100.0, value=0.0)
            if st.form_submit_button("Enregistrer", type="primary", width='stretch'):
                symbole = choix.split(" — ")[0]
                if qte <= 0 or pru <= 0:
                    st.error("La quantité et le coût moyen doivent être supérieurs à zéro.")
                else:
                    set_position(symbole, qte, pru)
                    st.success(f"Position {symbole} enregistrée.")
                    st.rerun()

    lignes = lignes_portefeuille()
    if not lignes:
        st.info("Aucune position en actions. Utilise le bouton ci-dessus pour en ajouter une.")
    else:
        st.markdown("<div class='section'>MES POSITIONS</div>", unsafe_allow_html=True)
        for l in lignes:
            c1, c2, c3 = st.columns([1, 3, 3])
            c1.markdown(f"<span class='badge-ticker'>{l['symbole']}</span>",
                        unsafe_allow_html=True)
            c2.markdown(
                f"<div class='titre-valeur'>{l['nom']}</div><div class='sous-titre'>"
                f"{l['quantite']:.0f} × PRU {fmt(l['pru'])}</div>", unsafe_allow_html=True)
            t_pv, c_pv = signe(l["pv"])
            t_pct, _ = signe(l["pv_pct"], " %", 2)
            t_j, c_j = signe(l["var_jour"])
            t_jp, _ = signe(l["var_jour_pct"], " %", 2)
            c3.markdown(
                f"<div class='prix'>{fmt(l['valeur'])}</div>"
                f"<div class='prix {c_pv}' style='font-size:13px'>{t_pv} ({t_pct})</div>"
                f"<div class='prix {c_j}' style='font-size:12px'>jour {t_j} ({t_jp})</div>",
                unsafe_allow_html=True)

            with st.expander(f"Modifier {l['symbole']}", expanded=False):
                m1, m2, m3 = st.columns([2, 2, 1])
                nq = m1.number_input("Quantité", value=float(l["quantite"]), min_value=0.0,
                                     step=1.0, key=f"q_{l['symbole']}")
                np_ = m2.number_input("Coût moyen (F)", value=float(l["pru"]), min_value=0.0,
                                      step=100.0, key=f"p_{l['symbole']}")
                if m3.button("💾", key=f"s_{l['symbole']}", help="Enregistrer"):
                    if nq > 0 and np_ > 0:
                        set_position(l["symbole"], nq, np_)
                        st.rerun()
                    else:
                        st.error("Valeurs invalides.")
                if m3.button("🗑", key=f"d_{l['symbole']}", help="Supprimer la position"):
                    supprimer_position(l["symbole"])
                    st.rerun()


# ============================================================== ANALYSE

with onglets[4]:
    portee = st.radio("Portée", ["Tout le marché", "Mon portefeuille"],
                      horizontal=True, key="pa", label_visibility="collapsed")
    if portee == "Mon portefeuille":
        symboles = [s for s, _, _ in get_portefeuille()]
        if not symboles:
            st.info("Ton portefeuille est vide.")
            symboles = []
    else:
        symboles = [s for s in VALEURS if s in cours_marche]

    if symboles:
        with st.spinner("Calcul des notes…"):
            notes = [(s, note_de(s, seance)) for s in symboles]
        notees = [(s, n) for s, n in notes if n["globale"] is not None]
        notees.sort(key=lambda x: x[1]["globale"], reverse=True)

        if not notees:
            st.warning(
                "Aucune valeur ne peut être notée : il manque l'historique des cours. "
                "Lance `4_historique_15ans.bat`."
            )
        else:
            moyenne = round(sum(n["globale"] for _, n in notees) / len(notees))
            coul = COULEURS[couleur_score(moyenne)]
            st.markdown(
                f"<div class='carte' style='display:flex;gap:18px;align-items:center'>"
                f"<div style='text-align:center'><div style='font-size:32px;font-weight:800;"
                f"color:{coul}'>{moyenne}</div><div class='mini'>/100</div></div>"
                f"<div><b>Qualité moyenne</b><div class='mini'>{len(notees)} valeurs notées · "
                f"classées de la meilleure à la moins bonne</div></div></div>",
                unsafe_allow_html=True)

            non_notees = len(notes) - len(notees)
            if non_notees:
                st.caption(f"{non_notees} valeur(s) sans historique suffisant, non classée(s).")

            sel_a = st.session_state.get("sel_analyse")
            if sel_a:
                with st.container(border=True):
                    if st.button("✕ Fermer le détail", key="fermer_a"):
                        st.session_state.sel_analyse = None
                        st.rerun()
                    fiche_valeur(sel_a, "a")
                st.divider()

            for rang, (symbole, n) in enumerate(notees, 1):
                lib, coul_b, _ = badge(n["globale"])
                d, t = n["details_dividende"], n["details_tendance"]
                c1, c2, c3, c4 = st.columns([1, 5, 1, 1])
                c1.markdown(f"<div style='font-size:20px;opacity:.55;text-align:center'>"
                            f"{rang}</div>", unsafe_allow_html=True)
                perf = signe(t.get("perf_1an"), " %", 2)[0] if t.get("perf_1an") is not None else "—"
                c2.markdown(
                    f"<div class='titre-valeur'>{get_nom(symbole)}</div>"
                    f"<span class='pilule' style='color:{COULEURS[coul_b]};"
                    f"border-color:{COULEURS[coul_b]}'>{lib}</span> "
                    f"<span class='mini'>rend. {fmt(d.get('rendement'), ' %', 1)} · "
                    f"1 an {perf}</span>", unsafe_allow_html=True)
                c3.markdown(
                    f"<div class='prix {couleur_score(n['globale'])}' "
                    f"style='font-size:21px'>{n['globale']}</div>", unsafe_allow_html=True)

                b = st.columns(4)
                for col, (lbl, val) in zip(b, [("Div.", n["dividende"]),
                                               ("Tend.", n["tendance"]),
                                               ("Risque", n["risque"]),
                                               ("Valo.", n["valorisation"])]):
                    cl = couleur_score(val)
                    col.markdown(
                        f"<div class='barre-fond'><div class='barre' "
                        f"style='width:{val or 0}%;background:{COULEURS[cl]}'></div></div>"
                        f"<div class='mini' style='text-align:center'>{lbl}</div>",
                        unsafe_allow_html=True)

                if c4.button("Voir", key=f"voir_a_{symbole}", width='stretch'):
                    st.session_state.sel_analyse = symbole
                    st.rerun()
