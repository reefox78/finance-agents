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

load_dotenv("config/.env")   # local dev — ignoré silencieusement si absent

# Pool initialisé au premier appel (lazy)
_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise EnvironmentError(
                "DATABASE_URL manquant. Configurez config/.env."
            )
        # ⚠️  Sous Docker, utiliser l'URL du session pooler Supabase (IPv4) :
        # postgresql://postgres.PROJECT_REF:PWD@aws-0-REGION.pooler.supabase.com:5432/postgres
        # La connexion directe (db.PROJECT.supabase.co) utilise IPv6 → inaccessible sous Docker.
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=10,   # augmenté pour absorber les requêtes concurrentes
            dsn=db_url,
            sslmode="require",
            connect_timeout=10,
        )
    return _pool


def _reset_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Force la recréation du pool (utile si pool épuisé par des connexions leakées)."""
    global _pool
    if _pool and not _pool.closed:
        try:
            _pool.closeall()
        except Exception:
            pass
    _pool = None
    return _get_pool()


class _ConnCtx:
    """Context manager : emprunte une connexion, la remet dans le pool à la fin."""
    def __enter__(self):
        # Sauvegarder la référence exacte du pool utilisé pour getconn(),
        # sinon si le pool est recréé entre __enter__ et __exit__ (Python 3.14 /
        # Starlette threadpool), putconn() lèverait PoolError "unkeyed connection".
        try:
            self._pool = _get_pool()
            self._conn = self._pool.getconn()
        except psycopg2.pool.PoolError as e:
            if "exhausted" in str(e):
                # Pool épuisé (connexions leakées) → reset forcé et réessai unique
                import logging as _log
                _log.getLogger(__name__).warning("Pool épuisé, reset forcé du pool DB")
                self._pool = _reset_pool()
                self._conn = self._pool.getconn()
            else:
                raise
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            try:
                self._conn.rollback()
            except Exception:
                pass
        try:
            self._pool.putconn(self._conn)
        except Exception:
            # Connexion déjà fermée ou pool recréé — on ferme proprement
            try:
                self._conn.close()
            except Exception:
                pass
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
