"""
Connexion PostgreSQL — pool de connexions thread-safe.

Usage :
    from db.client import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()
        conn.commit()
"""

import os
import psycopg2
import psycopg2.pool
from dotenv import load_dotenv

load_dotenv("config/.env")

_DATABASE_URL = os.getenv("DATABASE_URL")
if not _DATABASE_URL:
    raise EnvironmentError("DATABASE_URL manquant dans config/.env")

# Pool de 1 à 5 connexions simultanées (Streamlit est mono-thread par session)
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            dsn=_DATABASE_URL,
            sslmode="require",
            connect_timeout=10,
        )
    return _pool


class _ConnCtx:
    """Context manager : emprunte une connexion, la remet dans le pool à la fin."""
    def __enter__(self):
        self._conn = _get_pool().getconn()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        _get_pool().putconn(self._conn)
        return False   # ne supprime pas l'exception


def get_conn() -> _ConnCtx:
    """Retourne un context manager qui fournit une connexion psycopg2."""
    return _ConnCtx()


def execute(sql: str, params: tuple = (), fetch: str = "none") -> list | dict | None:
    """
    Raccourci pour exécuter une requête simple.

    fetch :
      "none"  → INSERT/UPDATE/DELETE, retourne None
      "one"   → retourne un dict ou None
      "all"   → retourne une liste de dicts
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = None
            if fetch != "none" and cur.description:
                cols = [d[0] for d in cur.description]
                if fetch == "one":
                    row = cur.fetchone()
                    result = dict(zip(cols, row)) if row else None
                elif fetch == "all":
                    result = [dict(zip(cols, row)) for row in cur.fetchall()]
        conn.commit()   # toujours committer après l'exécution
        return result
