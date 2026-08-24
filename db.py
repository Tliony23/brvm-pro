"""
Accès aux données de l'application.

Toutes les requêtes utilisent des paramètres nommés (:nom) et une syntaxe
comprise aussi bien par SQLite que par PostgreSQL, afin que le même code
fonctionne en local et sur l'application hébergée. Voir connexion.py.
"""
from connexion import (
    colonnes_de,
    est_postgres,
    executer,
    executer_plusieurs,
    lire,
    lire_une,
)


def _type_reel():
    return "DOUBLE PRECISION" if est_postgres() else "REAL"


def init_db():
    reel = _type_reel()
    executer(f"""
        CREATE TABLE IF NOT EXISTS prix_quotidiens (
            symbole         TEXT NOT NULL,
            nom             TEXT,
            date            TEXT NOT NULL,
            cours_veille    {reel},
            cours_ouverture {reel},
            cours_haut      {reel},
            cours_bas       {reel},
            cours_cloture   {reel},
            variation       {reel},
            volume          {reel},
            PRIMARY KEY (symbole, date)
        )
    """)
    # Migration : bases créées avant l'ajout des bougies
    colonnes = colonnes_de("prix_quotidiens")
    if colonnes:
        if "cours_haut" not in colonnes:
            executer(f"ALTER TABLE prix_quotidiens ADD COLUMN cours_haut {reel}")
        if "cours_bas" not in colonnes:
            executer(f"ALTER TABLE prix_quotidiens ADD COLUMN cours_bas {reel}")

    executer(f"""
        CREATE TABLE IF NOT EXISTS fondamentaux (
            symbole           TEXT NOT NULL,
            annee             TEXT NOT NULL,
            chiffre_affaires  {reel},
            croissance_ca     {reel},
            resultat_net      {reel},
            croissance_rn     {reel},
            bnpa              {reel},
            per               {reel},
            dividende         {reel},
            PRIMARY KEY (symbole, annee)
        )
    """)
    executer("""
        CREATE TABLE IF NOT EXISTS ticker_sika_cache (
            symbole_brvm  TEXT PRIMARY KEY,
            symbole_sika  TEXT
        )
    """)
    executer(f"""
        CREATE TABLE IF NOT EXISTS dividendes_a_venir (
            symbole           TEXT NOT NULL,
            date_detachement  TEXT,
            date_brute        TEXT NOT NULL,
            montant           {reel},
            rendement         {reel},
            PRIMARY KEY (symbole, date_brute)
        )
    """)
    executer(f"""
        CREATE TABLE IF NOT EXISTS dividendes_historique (
            symbole    TEXT NOT NULL,
            annee      TEXT NOT NULL,
            montant    {reel},
            rendement  {reel},
            PRIMARY KEY (symbole, annee)
        )
    """)


def upsert_prix(rows):
    """Enregistre des cours. Une valeur absente n'écrase jamais une valeur déjà
    connue (COALESCE) : plusieurs sources aux colonnes différentes peuvent ainsi
    se compléter (brvm.org ne donne pas le plus haut/plus bas, Sikafinance oui)."""
    if not rows:
        return
    defauts = {
        "nom": "", "cours_veille": None, "cours_ouverture": None,
        "cours_haut": None, "cours_bas": None, "cours_cloture": None,
        "variation": None, "volume": None,
    }
    complets = [{**defauts, **r} for r in rows]
    executer_plusieurs("""
        INSERT INTO prix_quotidiens
            (symbole, nom, date, cours_veille, cours_ouverture, cours_haut,
             cours_bas, cours_cloture, variation, volume)
        VALUES
            (:symbole, :nom, :date, :cours_veille, :cours_ouverture, :cours_haut,
             :cours_bas, :cours_cloture, :variation, :volume)
        ON CONFLICT (symbole, date) DO UPDATE SET
            nom = CASE WHEN excluded.nom <> '' THEN excluded.nom
                       ELSE prix_quotidiens.nom END,
            cours_veille    = COALESCE(excluded.cours_veille, prix_quotidiens.cours_veille),
            cours_ouverture = COALESCE(excluded.cours_ouverture, prix_quotidiens.cours_ouverture),
            cours_haut      = COALESCE(excluded.cours_haut, prix_quotidiens.cours_haut),
            cours_bas       = COALESCE(excluded.cours_bas, prix_quotidiens.cours_bas),
            cours_cloture   = COALESCE(excluded.cours_cloture, prix_quotidiens.cours_cloture),
            variation       = COALESCE(excluded.variation, prix_quotidiens.variation),
            volume          = COALESCE(excluded.volume, prix_quotidiens.volume)
    """, complets)


def get_symboles():
    return lire("""
        SELECT symbole, MAX(nom) AS nom
        FROM prix_quotidiens
        GROUP BY symbole
        ORDER BY symbole
    """)


def get_historique(symbole):
    return lire("""
        SELECT date, cours_ouverture, cours_haut, cours_bas, cours_cloture, volume
        FROM prix_quotidiens
        WHERE symbole = :s
        ORDER BY date
    """, {"s": symbole})


def nb_jours_enregistres():
    ligne = lire_une("SELECT COUNT(DISTINCT date) FROM prix_quotidiens")
    return ligne[0] if ligne else 0


def get_ticker_sika(symbole_brvm):
    ligne = lire_une(
        "SELECT symbole_sika FROM ticker_sika_cache WHERE symbole_brvm = :s",
        {"s": symbole_brvm})
    return ligne[0] if ligne else None


def set_ticker_sika(symbole_brvm, symbole_sika):
    executer("""
        INSERT INTO ticker_sika_cache (symbole_brvm, symbole_sika)
        VALUES (:b, :s)
        ON CONFLICT (symbole_brvm) DO UPDATE SET symbole_sika = excluded.symbole_sika
    """, {"b": symbole_brvm, "s": symbole_sika})


def upsert_fondamentaux(rows):
    executer_plusieurs("""
        INSERT INTO fondamentaux
            (symbole, annee, chiffre_affaires, croissance_ca, resultat_net,
             croissance_rn, bnpa, per, dividende)
        VALUES
            (:symbole, :annee, :chiffre_affaires, :croissance_ca, :resultat_net,
             :croissance_rn, :bnpa, :per, :dividende)
        ON CONFLICT (symbole, annee) DO UPDATE SET
            chiffre_affaires = excluded.chiffre_affaires,
            croissance_ca    = excluded.croissance_ca,
            resultat_net     = excluded.resultat_net,
            croissance_rn    = excluded.croissance_rn,
            bnpa             = excluded.bnpa,
            per              = excluded.per,
            dividende        = excluded.dividende
    """, rows)


def get_fondamentaux(symbole):
    return lire("""
        SELECT annee, chiffre_affaires, croissance_ca, resultat_net,
               croissance_rn, bnpa, per, dividende
        FROM fondamentaux
        WHERE symbole = :s
        ORDER BY annee
    """, {"s": symbole})


def upsert_dividendes_a_venir(rows):
    """On vide la table avant d'écrire : un dividende détaché disparaît de la
    page source, et garder d'anciennes annonces fausserait les prévisions."""
    executer("DELETE FROM dividendes_a_venir")
    executer_plusieurs("""
        INSERT INTO dividendes_a_venir
            (symbole, date_detachement, date_brute, montant, rendement)
        VALUES (:symbole, :date_detachement, :date_brute, :montant, :rendement)
        ON CONFLICT (symbole, date_brute) DO UPDATE SET
            date_detachement = excluded.date_detachement,
            montant          = excluded.montant,
            rendement        = excluded.rendement
    """, rows)


def upsert_dividende_historique(rows):
    executer_plusieurs("""
        INSERT INTO dividendes_historique (symbole, annee, montant, rendement)
        VALUES (:symbole, :annee, :montant, :rendement)
        ON CONFLICT (symbole, annee) DO UPDATE SET
            montant   = COALESCE(excluded.montant, dividendes_historique.montant),
            rendement = COALESCE(excluded.rendement, dividendes_historique.rendement)
    """, rows)


def get_dividendes_a_venir(symboles=None):
    """Dates connues d'abord (ordre chronologique), puis les 'à préciser'."""
    if symboles:
        params = {f"s{i}": s for i, s in enumerate(symboles)}
        marques = ",".join(f":s{i}" for i in range(len(symboles)))
        return lire(f"""
            SELECT symbole, date_detachement, date_brute, montant, rendement
            FROM dividendes_a_venir
            WHERE symbole IN ({marques})
            ORDER BY CASE WHEN date_detachement IS NULL THEN 1 ELSE 0 END,
                     date_detachement
        """, params)
    return lire("""
        SELECT symbole, date_detachement, date_brute, montant, rendement
        FROM dividendes_a_venir
        ORDER BY CASE WHEN date_detachement IS NULL THEN 1 ELSE 0 END,
                 date_detachement
    """)


def get_dividendes_historique(symbole):
    return lire("""
        SELECT annee, montant, rendement
        FROM dividendes_historique
        WHERE symbole = :s
        ORDER BY annee
    """, {"s": symbole})


# ---------------------------------------------------------------- PORTEFEUILLE

def init_portefeuille():
    reel = _type_reel()
    executer(f"""
        CREATE TABLE IF NOT EXISTS portefeuille (
            symbole   TEXT PRIMARY KEY,
            quantite  {reel} NOT NULL,
            pru       {reel} NOT NULL
        )
    """)
    executer("""
        CREATE TABLE IF NOT EXISTS favoris (
            symbole TEXT PRIMARY KEY
        )
    """)


def get_portefeuille():
    return lire("SELECT symbole, quantite, pru FROM portefeuille ORDER BY symbole")


def set_position(symbole, quantite, pru):
    executer("""
        INSERT INTO portefeuille (symbole, quantite, pru)
        VALUES (:s, :q, :p)
        ON CONFLICT (symbole) DO UPDATE SET
            quantite = excluded.quantite, pru = excluded.pru
    """, {"s": symbole, "q": float(quantite), "p": float(pru)})


def supprimer_position(symbole):
    executer("DELETE FROM portefeuille WHERE symbole = :s", {"s": symbole})


def get_favoris():
    return {r[0] for r in lire("SELECT symbole FROM favoris")}


def basculer_favori(symbole):
    if lire_une("SELECT 1 FROM favoris WHERE symbole = :s", {"s": symbole}):
        executer("DELETE FROM favoris WHERE symbole = :s", {"s": symbole})
    else:
        executer("INSERT INTO favoris (symbole) VALUES (:s)", {"s": symbole})


# ------------------------------------------------------------------ COTATIONS

def get_dernier_cours(symbole):
    return lire_une("""
        SELECT date, cours_cloture, cours_veille, volume
        FROM prix_quotidiens
        WHERE symbole = :s AND cours_cloture IS NOT NULL
        ORDER BY date DESC
        LIMIT 1
    """, {"s": symbole})


def get_tous_derniers_cours():
    """{symbole: (date, cloture, veille, volume)} pour la dernière séance connue."""
    lignes = lire("""
        SELECT p.symbole, p.date, p.cours_cloture, p.cours_veille, p.volume
        FROM prix_quotidiens p
        JOIN (
            SELECT symbole, MAX(date) AS dmax
            FROM prix_quotidiens
            WHERE cours_cloture IS NOT NULL
            GROUP BY symbole
        ) m ON m.symbole = p.symbole AND m.dmax = p.date
    """)
    return {r[0]: (r[1], r[2], r[3], r[4]) for r in lignes}


def derniere_seance():
    ligne = lire_une("SELECT MAX(date) FROM prix_quotidiens")
    return ligne[0] if ligne else None


# ------------------------------------------------------------------ PARAMÈTRES

def init_parametres():
    executer("""
        CREATE TABLE IF NOT EXISTS parametres (
            cle    TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)


def get_parametre(cle, defaut=None):
    ligne = lire_une("SELECT valeur FROM parametres WHERE cle = :c", {"c": cle})
    return ligne[0] if ligne else defaut


def set_parametre(cle, valeur):
    executer("""
        INSERT INTO parametres (cle, valeur) VALUES (:c, :v)
        ON CONFLICT (cle) DO UPDATE SET valeur = excluded.valeur
    """, {"c": cle, "v": str(valeur)})


def get_liquidites():
    """Montant en espèces non investi, en FCFA."""
    try:
        return float(get_parametre("liquidites", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def set_liquidites(montant):
    set_parametre("liquidites", float(montant))
