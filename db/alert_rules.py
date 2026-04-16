"""
Alert rules — PostgreSQL.
Gestion des règles d'alerte automatiques (conditions sur prix, RSI, score).
"""

import logging
import os
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from db.client import execute

log = logging.getLogger(__name__)

# Conditions supportées
CONDITIONS = {
    "PRIX_DESSUS",
    "PRIX_DESSOUS",
    "RSI_DESSOUS",
    "RSI_DESSUS",
    "SCORE_DESSUS",
    "SCORE_DESSOUS",
}

_CONDITION_LABELS = {
    "PRIX_DESSUS":  "Prix au-dessus de",
    "PRIX_DESSOUS": "Prix en dessous de",
    "RSI_DESSOUS":  "RSI en dessous de",
    "RSI_DESSUS":   "RSI au-dessus de",
    "SCORE_DESSUS": "Score agents >",
    "SCORE_DESSOUS": "Score agents <",
}


def init_table() -> None:
    """Crée la table alert_rules si elle n'existe pas."""
    execute(
        """
        CREATE TABLE IF NOT EXISTS alert_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            ticker VARCHAR(20) NOT NULL,
            condition VARCHAR(30) NOT NULL,
            valeur FLOAT NOT NULL,
            actif BOOLEAN DEFAULT TRUE,
            notif_email BOOLEAN DEFAULT FALSE,
            derniere_alerte TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        )
        """,
    )
    log.info("Table alert_rules vérifiée/créée.")


def _serialize(row: dict) -> dict:
    """Convertit les types non-JSON (UUID, datetime) en str."""
    if row is None:
        return row
    row = dict(row)
    row["id"] = str(row["id"])
    row["user_id"] = str(row["user_id"])
    if row.get("derniere_alerte"):
        row["derniere_alerte"] = row["derniere_alerte"].isoformat()
    if row.get("created_at"):
        row["created_at"] = row["created_at"].isoformat()
    return row


def ajouter_regle(
    user_id: str,
    ticker: str,
    condition: str,
    valeur: float,
    notif_email: bool = False,
) -> dict:
    if condition not in CONDITIONS:
        raise ValueError(f"Condition inconnue : {condition}. Valeurs : {CONDITIONS}")
    row = execute(
        """
        INSERT INTO alert_rules (user_id, ticker, condition, valeur, notif_email)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (user_id, ticker.upper().strip(), condition, float(valeur), notif_email),
        fetch="one",
    )
    return _serialize(row)


def lister_regles(user_id: str) -> list[dict]:
    rows = execute(
        "SELECT * FROM alert_rules WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
        fetch="all",
    ) or []
    return [_serialize(r) for r in rows]


def supprimer_regle(user_id: str, regle_id: str) -> None:
    execute(
        "DELETE FROM alert_rules WHERE id = %s AND user_id = %s",
        (regle_id, user_id),
    )


def toggle_regle(user_id: str, regle_id: str) -> dict:
    row = execute(
        """
        UPDATE alert_rules
        SET actif = NOT actif
        WHERE id = %s AND user_id = %s
        RETURNING *
        """,
        (regle_id, user_id),
        fetch="one",
    )
    if row is None:
        raise ValueError(f"Règle {regle_id} introuvable pour user {user_id}")
    return _serialize(row)


def maj_derniere_alerte(regle_id: str) -> None:
    execute(
        "UPDATE alert_rules SET derniere_alerte = NOW() WHERE id = %s",
        (regle_id,),
    )


# ---------------------------------------------------------------------------
# Logique de vérification
# ---------------------------------------------------------------------------

def _get_prix(ticker: str) -> float | None:
    """Retourne le prix courant via yfinance fast_info."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        return float(price) if price else None
    except Exception as e:
        log.warning("Impossible de récupérer le prix de %s : %s", ticker, e)
        return None


def _get_rsi(ticker: str, period: int = 14) -> float | None:
    """Calcule le RSI sur les 30 derniers jours."""
    try:
        import yfinance as yf
        import pandas as pd

        df = yf.download(ticker, period="1mo", interval="1d", progress=False, auto_adjust=True)
        if df.empty or len(df) < period + 1:
            return None

        close = df["Close"].squeeze()
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi = 100 - (100 / (1 + rs))
        val = rsi.dropna().iloc[-1] if not rsi.dropna().empty else None
        return float(val) if val is not None else None
    except Exception as e:
        log.warning("Impossible de calculer le RSI de %s : %s", ticker, e)
        return None


def _get_score(ticker: str) -> float | None:
    """Retourne le score orchestrateur, None si erreur."""
    try:
        from orchestrator.orchestrator import get_score  # type: ignore
        return float(get_score(ticker))
    except Exception as e:
        log.debug("Score non disponible pour %s : %s", ticker, e)
        return None


def _envoyer_email(sujet: str, corps: str) -> None:
    """Envoie un email via SMTP. Skip silencieux si non configuré."""
    host = os.getenv("SMTP_HOST")
    if not host:
        return
    try:
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER", "")
        pwd  = os.getenv("SMTP_PASS", "")
        from_ = os.getenv("SMTP_FROM", user)
        to_   = os.getenv("SMTP_TO", user)

        msg = MIMEText(corps, "plain", "utf-8")
        msg["Subject"] = sujet
        msg["From"] = from_
        msg["To"] = to_

        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            if port != 465:
                smtp.starttls()
            if user and pwd:
                smtp.login(user, pwd)
            smtp.sendmail(from_, [to_], msg.as_string())
        log.info("Email envoyé : %s", sujet)
    except Exception as e:
        log.warning("Envoi email échoué : %s", e)


def checker_regles(user_id: str) -> list[dict]:
    """
    Vérifie toutes les règles actives d'un user.
    Pour chaque règle déclenchée :
      - Insère une alerte dans la table alerts
      - Met à jour derniere_alerte
      - Envoie email si notif_email=True et SMTP configuré
    Retourne la liste des alertes déclenchées.
    """
    from db.alerts_store import ajouter_alerte  # import local pour éviter circulaire

    regles = execute(
        "SELECT * FROM alert_rules WHERE user_id = %s AND actif = TRUE",
        (user_id,),
        fetch="all",
    ) or []

    if not regles:
        return []

    # Regrouper par ticker pour limiter les appels yfinance
    tickers_uniques = list({r["ticker"] for r in regles})

    prix_cache:  dict[str, float | None] = {}
    rsi_cache:   dict[str, float | None] = {}
    score_cache: dict[str, float | None] = {}

    # Pré-fetch par condition requise
    conditions_par_ticker: dict[str, set] = {}
    for r in regles:
        t = r["ticker"]
        conditions_par_ticker.setdefault(t, set()).add(r["condition"])

    for ticker in tickers_uniques:
        conds = conditions_par_ticker[ticker]
        if any(c.startswith("PRIX") for c in conds):
            prix_cache[ticker] = _get_prix(ticker)
        if any(c.startswith("RSI") for c in conds):
            rsi_cache[ticker] = _get_rsi(ticker)
        if any(c.startswith("SCORE") for c in conds):
            score_cache[ticker] = _get_score(ticker)

    declenchees: list[dict] = []
    now = datetime.utcnow()
    cooldown = timedelta(hours=4)

    for regle in regles:
        regle_id = str(regle["id"])
        ticker   = regle["ticker"]
        cond     = regle["condition"]
        valeur   = float(regle["valeur"])

        # Anti-spam : skip si déclenchée dans les 4 dernières heures
        derniere = regle.get("derniere_alerte")
        if derniere and (now - derniere) < cooldown:
            log.debug("Règle %s anti-spam — ignorée", regle_id)
            continue

        # Récupère la valeur courante selon la condition
        if cond.startswith("PRIX"):
            courant = prix_cache.get(ticker)
        elif cond.startswith("RSI"):
            courant = rsi_cache.get(ticker)
        elif cond.startswith("SCORE"):
            courant = score_cache.get(ticker)
        else:
            log.warning("Condition inconnue : %s", cond)
            continue

        if courant is None:
            log.debug("Valeur non disponible pour %s/%s — règle ignorée", ticker, cond)
            continue

        # Évaluation
        declenche = False
        if cond in ("PRIX_DESSUS", "RSI_DESSUS", "SCORE_DESSUS"):
            declenche = courant > valeur
        elif cond in ("PRIX_DESSOUS", "RSI_DESSOUS", "SCORE_DESSOUS"):
            declenche = courant < valeur

        if not declenche:
            continue

        # Création du message
        label = _CONDITION_LABELS.get(cond, cond)
        message = (
            f"[Règle auto] {ticker} — {label} {valeur:.2f} "
            f"(valeur actuelle : {courant:.2f})"
        )

        # Insertion alerte
        try:
            alerte = ajouter_alerte(user_id, ticker, "info", message)
            maj_derniere_alerte(regle_id)
            declenchees.append(alerte)
            log.info("Alerte déclenchée : %s", message)
        except Exception as e:
            log.error("Impossible d'insérer l'alerte pour règle %s : %s", regle_id, e)
            continue

        # Email optionnel
        if regle.get("notif_email"):
            _envoyer_email(
                sujet=f"[Finance Agents] Alerte {ticker}",
                corps=message,
            )

    return declenchees
