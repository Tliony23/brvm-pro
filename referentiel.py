"""
Référentiel des valeurs cotées à la BRVM.

Pour chaque symbole : nom d'affichage, code Sikafinance (avec suffixe pays),
secteur d'activité et pays de cotation.

--- POURQUOI CE FICHIER EXISTE ---
Les tickers et les noms viennent de la page "Cotations de A à Z" de Sikafinance.
Les SECTEURS, eux, ne sont pas publiés sous une forme exploitable en une seule
page : ils sont donc renseignés ici à la main. C'est stable (une société ne
change pas de secteur), mais si tu repères une erreur, corrige simplement la
ligne concernée et relance l'application — rien d'autre à faire.

Secteurs utilisés : Finance, Agriculture, Distribution, Industrie,
Services publics, Transport, Télécommunications, Autres.
"""

# symbole : (nom d'affichage, code Sikafinance, secteur, pays)
VALEURS = {
    "SDSC":  ("Africa Global Logistics CI",        "SDSC.ci",  "Transport",           "Côte d'Ivoire"),
    "BOAB":  ("Bank Of Africa Bénin",              "BOAB.bj",  "Finance",             "Bénin"),
    "BOABF": ("Bank Of Africa Burkina Faso",       "BOABF.bf", "Finance",             "Burkina Faso"),
    "BOAC":  ("Bank Of Africa Côte d'Ivoire",      "BOAC.ci",  "Finance",             "Côte d'Ivoire"),
    "BOAM":  ("Bank Of Africa Mali",               "BOAM.ml",  "Finance",             "Mali"),
    "BOAN":  ("Bank Of Africa Niger",              "BOAN.ne",  "Finance",             "Niger"),
    "BOAS":  ("Bank Of Africa Sénégal",            "BOAS.sn",  "Finance",             "Sénégal"),
    "BICB":  ("Banque Int. pour le Commerce Bénin", "BICB.bj", "Finance",             "Bénin"),
    "BNBC":  ("Bernabé Côte d'Ivoire",             "BNBC.ci",  "Distribution",        "Côte d'Ivoire"),
    "BICC":  ("BICICI",                            "BICC.ci",  "Finance",             "Côte d'Ivoire"),
    "CFAC":  ("CFAO Motors Côte d'Ivoire",         "CFAC.ci",  "Distribution",        "Côte d'Ivoire"),
    "CIEC":  ("CIE Côte d'Ivoire",                 "CIEC.ci",  "Services publics",    "Côte d'Ivoire"),
    "CBIBF": ("Coris Bank International BF",       "CBIBF.bf", "Finance",             "Burkina Faso"),
    "SEMC":  ("Crown SIEM Côte d'Ivoire",          "SEMC.ci",  "Industrie",           "Côte d'Ivoire"),
    "ECOC":  ("Ecobank Côte d'Ivoire",             "ECOC.ci",  "Finance",             "Côte d'Ivoire"),
    "SIVC":  ("Erium (ex-Air Liquide CI)",         "SIVC.ci",  "Industrie",           "Côte d'Ivoire"),
    "ETIT":  ("Ecobank Transnational Inc. Togo",   "ETIT.tg",  "Finance",             "Togo"),
    "FTSC":  ("Filtisac Côte d'Ivoire",            "FTSC.ci",  "Industrie",           "Côte d'Ivoire"),
    "LNBB":  ("Loterie Nationale du Bénin",        "LNBB.bj",  "Autres",              "Bénin"),
    "SVOC":  ("Movis Côte d'Ivoire",               "SVOC.ci",  "Transport",           "Côte d'Ivoire"),
    "NEIC":  ("NEI-CEDA Côte d'Ivoire",            "NEIC.ci",  "Industrie",           "Côte d'Ivoire"),
    "NTLC":  ("Nestlé Côte d'Ivoire",              "NTLC.ci",  "Industrie",           "Côte d'Ivoire"),
    "NSBC":  ("NSIA Banque Côte d'Ivoire",         "NSBC.ci",  "Finance",             "Côte d'Ivoire"),
    "ONTBF": ("ONATEL Burkina Faso",               "ONTBF.bf", "Télécommunications",  "Burkina Faso"),
    "ORGT":  ("Oragroup Togo",                     "ORGT.tg",  "Finance",             "Togo"),
    "ORAC":  ("Orange Côte d'Ivoire",              "ORAC.ci",  "Télécommunications",  "Côte d'Ivoire"),
    "PALC":  ("Palm Côte d'Ivoire",                "PALC.ci",  "Agriculture",         "Côte d'Ivoire"),
    "SAFC":  ("SAFCA Côte d'Ivoire",               "SAFC.ci",  "Finance",             "Côte d'Ivoire"),
    "SPHC":  ("SAPH Côte d'Ivoire",                "SPHC.ci",  "Agriculture",         "Côte d'Ivoire"),
    "ABJC":  ("Servair Abidjan Côte d'Ivoire",     "ABJC.ci",  "Distribution",        "Côte d'Ivoire"),
    "STAC":  ("SETAO Côte d'Ivoire",               "STAC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SGBC":  ("Société Générale Côte d'Ivoire",    "SGBC.ci",  "Finance",             "Côte d'Ivoire"),
    "CABC":  ("Sicable Côte d'Ivoire",             "CABC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SICC":  ("SICOR Côte d'Ivoire",               "SICC.ci",  "Agriculture",         "Côte d'Ivoire"),
    "STBC":  ("SITAB Côte d'Ivoire",               "STBC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SMBC":  ("SMB Côte d'Ivoire",                 "SMBC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SIBC":  ("Société Ivoirienne de Banque",      "SIBC.ci",  "Finance",             "Côte d'Ivoire"),
    "SDCC":  ("SODECI",                            "SDCC.ci",  "Services publics",    "Côte d'Ivoire"),
    "SOGC":  ("SOGB Côte d'Ivoire",                "SOGC.ci",  "Agriculture",         "Côte d'Ivoire"),
    "SLBC":  ("Solibra Côte d'Ivoire",             "SLBC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SNTS":  ("Sonatel Sénégal",                   "SNTS.sn",  "Télécommunications",  "Sénégal"),
    "SCRC":  ("Sucrivoire Côte d'Ivoire",          "SCRC.ci",  "Agriculture",         "Côte d'Ivoire"),
    "TTLC":  ("Total Côte d'Ivoire",               "TTLC.ci",  "Distribution",        "Côte d'Ivoire"),
    "TTLS":  ("Total Sénégal",                     "TTLS.sn",  "Distribution",        "Sénégal"),
    "PRSC":  ("Tractafric Motors Côte d'Ivoire",   "PRSC.ci",  "Distribution",        "Côte d'Ivoire"),
    "UNLC":  ("Unilever Côte d'Ivoire",            "UNLC.ci",  "Industrie",           "Côte d'Ivoire"),
    "UNXC":  ("Uniwax Côte d'Ivoire",              "UNXC.ci",  "Industrie",           "Côte d'Ivoire"),
    "SHEC":  ("Vivo Energy Côte d'Ivoire",         "SHEC.ci",  "Distribution",        "Côte d'Ivoire"),
}

# Ordre d'affichage des filtres par secteur dans l'onglet Marché
SECTEURS = [
    "Finance",
    "Agriculture",
    "Distribution",
    "Industrie",
    "Services publics",
    "Transport",
    "Télécommunications",
    "Autres",
]


def get_nom(symbole):
    v = VALEURS.get(symbole)
    return v[0] if v else symbole


def get_sika(symbole):
    v = VALEURS.get(symbole)
    return v[1] if v else None


def get_secteur(symbole):
    v = VALEURS.get(symbole)
    return v[2] if v else "Autres"


def get_pays(symbole):
    v = VALEURS.get(symbole)
    return v[3] if v else ""


def symbole_depuis_sika(code_sika):
    """'SNTS.sn' -> 'SNTS'. Utile pour relier les pages Sikafinance à nos symboles."""
    if not code_sika:
        return None
    return str(code_sika).split(".")[0].strip().upper()


def tous_les_symboles():
    return sorted(VALEURS.keys())
