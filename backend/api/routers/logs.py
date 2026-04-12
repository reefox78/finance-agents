"""
Logs router — liste et lecture des fichiers de log.
Accès restreint aux administrateurs.
Les données sensibles sont masquées avant renvoi au client.
"""
import re
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException

from api.deps import AdminUser

router = APIRouter()

# Dossier logs à la racine du projet (../../ depuis backend/)
_LOGS_DIR = Path(__file__).parent.parent.parent.parent / "logs"

# ─── Sanitisation ────────────────────────────────────────────────────────────

# Patterns sensibles à masquer
_SENSITIVE = [
    # JWT tokens (eyJ...)
    (re.compile(r'eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+'), '[JWT_REDACTED]'),
    # DATABASE_URL / postgres://user:pass@host
    (re.compile(r'postgres(?:ql)?://[^\s"\']+'), '[DB_URL_REDACTED]'),
    # URLs avec mot de passe : scheme://user:pass@host
    (re.compile(r'[a-zA-Z]+://[^:]+:[^@]+@[^\s"\']+'), '[URL_REDACTED]'),
    # Clés API génériques (mots-clés + valeur)
    (re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|pwd)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{8,})["\']?'),
     r'\1=[REDACTED]'),
    # Groq / OpenAI style keys : gsk_... ou sk-...
    (re.compile(r'\b(?:gsk|sk|pk|rk)[-_][A-Za-z0-9]{16,}\b'), '[KEY_REDACTED]'),
    # Adresses e-mail (masque le nom local sauf 2 premiers chars)
    (re.compile(r'\b([A-Za-z0-9._%+\-]{2})[A-Za-z0-9._%+\-]*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\b'),
     r'\1***\2'),
    # Strings base64 longues (≥ 40 chars) hors contexte URL
    (re.compile(r'(?<![/=A-Za-z0-9])[A-Za-z0-9+/]{40,}={0,2}(?![/=A-Za-z0-9])'), '[B64_REDACTED]'),
]


def _sanitize(line: str) -> str:
    for pattern, replacement in _SENSITIVE:
        line = pattern.sub(replacement, line)
    return line


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_component_date(filename: str) -> tuple[str, str]:
    """Extrait composant et date depuis 'dashboard_2026-04-07_16-41-00.log'."""
    stem = Path(filename).stem   # sans .log
    parts = stem.split('_', 1)   # ['dashboard', '2026-04-07_16-41-00']
    component = parts[0] if parts else 'unknown'
    date_part = parts[1].replace('_', ' ') if len(parts) > 1 else ''
    return component, date_part


def _log_level(line: str) -> str:
    """Détecte le niveau de log d'une ligne."""
    upper = line.upper()
    if 'ERROR' in upper or 'EXCEPTION' in upper or 'TRACEBACK' in upper or 'CRITICAL' in upper:
        return 'error'
    if 'WARNING' in upper or 'WARN' in upper:
        return 'warning'
    if 'SUCCESS' in upper or 'ALERTE' in upper or 'ACHETER' in upper:
        return 'success'
    return 'info'


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/files")
def list_log_files(admin: AdminUser) -> list[dict]:
    """Liste les fichiers de log disponibles, du plus récent au plus ancien."""
    if not _LOGS_DIR.exists():
        return []

    files = []
    for f in sorted(_LOGS_DIR.glob("*.log"), reverse=True):
        stat = f.stat()
        component, date_str = _parse_component_date(f.name)
        files.append({
            "name":      f.name,
            "component": component,
            "date":      date_str,
            "size_kb":   round(stat.st_size / 1024, 1),
            "modified":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return files


@router.get("/content/{filename}")
def get_log_content(filename: str, admin: AdminUser) -> dict:
    """
    Retourne le contenu d'un fichier de log ligne par ligne.
    Les données sensibles sont masquées.
    Nom de fichier validé pour prévenir toute traversée de répertoire.
    """
    # Validation : uniquement nom simple, pas de path traversal
    safe_name = Path(filename).name
    if safe_name != filename or not safe_name.endswith('.log'):
        raise HTTPException(status_code=400, detail="Nom de fichier invalide.")

    log_path = _LOGS_DIR / safe_name
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="Fichier introuvable.")

    # Lecture et sanitisation ligne par ligne (max 2000 lignes)
    lines = []
    try:
        with open(log_path, encoding="utf-8", errors="replace") as fh:
            raw_lines = fh.readlines()[-2000:]   # garde les 2000 dernières lignes

        for raw in raw_lines:
            text = _sanitize(raw.rstrip('\n\r'))
            lines.append({
                "text":  text,
                "level": _log_level(text),
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de lecture : {e}")

    component, date_str = _parse_component_date(safe_name)
    return {
        "filename":  safe_name,
        "component": component,
        "date":      date_str,
        "lines":     lines,
        "truncated": len(raw_lines) == 2000,
    }
