"""
Couche de connexion à la base de données.

Le même code fonctionne avec deux systèmes :
  - SQLite  : un simple fichier sur ton ordinateur (usage local, par défaut)
  - Postgres: une base en ligne (Neon), utilisée par l'application hébergée

Le choix se fait tout seul, dans cet ordre :
  1. la variable d'environnement DATABASE_URL, si elle existe
  2. le secret "database_url" configuré dans Streamlit
  3. sinon, le fichier brvm_data.db à côté des scripts

Tu n'as donc rien à changer pour continuer à utiliser l'application chez toi.
"""
import os
import threading
from pathlib import Path

from sqlalchemy import create_engine, text

CHEMIN_SQLITE = Path(__file__).parent / "brvm_data.db"

_moteur = None
_verrou = threading.Lock()


def _url_base():
    """Détermine l'adresse de la base à utiliser."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return _normaliser(url)

    # st.secrets n'existe que dans un contexte Streamlit : on l'interroge
    # prudemment pour que les scripts en ligne de commande fonctionnent aussi.
    try:
        import streamlit as st
        url = st.secrets.get("database_url")
        if url:
            return _normaliser(url)
    except Exception:
        pass

    return f"sqlite:///{CHEMIN_SQLITE}"


def _normaliser(url):
    """Neon fournit une adresse commençant par postgresql:// ; on précise le
    pilote psycopg (version 3) attendu par SQLAlchemy."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def get_engine():
    global _moteur
    if _moteur is None:
        with _verrou:
            if _moteur is None:
                url = _url_base()
                if url.startswith("sqlite"):
                    _moteur = create_engine(url, future=True)
                    with _moteur.begin() as cx:
                        # Meilleure tenue en cas d'accès simultanés
                        cx.execute(text("PRAGMA journal_mode=WAL"))
                else:
                    # pool_pre_ping : Neon suspend le calcul après quelques
                    # minutes d'inactivité ; sans cette option la première
                    # requête après réveil échouerait.
                    _moteur = create_engine(
                        url, future=True, pool_pre_ping=True,
                        pool_recycle=280, pool_size=3, max_overflow=2,
                    )
    return _moteur


def est_postgres():
    return get_engine().dialect.name == "postgresql"


def executer(sql, params=None):
    """Exécute une instruction qui modifie la base (INSERT, UPDATE, DELETE...)."""
    with get_engine().begin() as cx:
        cx.execute(text(sql), params or {})


def executer_plusieurs(sql, liste_params):
    """Exécute la même instruction sur une liste de jeux de paramètres."""
    if not liste_params:
        return
    with get_engine().begin() as cx:
        cx.execute(text(sql), liste_params)


def lire(sql, params=None):
    """Renvoie toutes les lignes d'une requête, sous forme de tuples."""
    with get_engine().connect() as cx:
        return [tuple(r) for r in cx.execute(text(sql), params or {}).fetchall()]


def lire_une(sql, params=None):
    """Renvoie la première ligne d'une requête, ou None."""
    with get_engine().connect() as cx:
        ligne = cx.execute(text(sql), params or {}).fetchone()
        return tuple(ligne) if ligne is not None else None


def colonnes_de(table):
    """Liste les colonnes existantes d'une table (vide si la table n'existe pas)."""
    from sqlalchemy import inspect
    inspecteur = inspect(get_engine())
    if not inspecteur.has_table(table):
        return []
    return [c["name"] for c in inspecteur.get_columns(table)]
