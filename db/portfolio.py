"""
Opérations portefeuille — PostgreSQL.
Interface identique à data/portfolio.py, avec user_id en plus.
"""

import uuid
from datetime import datetime
from db.client import execute, get_conn


def _prix_actuel(ticker: str) -> float | None:
    """Récupère le dernier cours via le cache market_data (évite le rate-limit)."""
    try:
        from data.market_data import get_stock_data
        df = get_stock_data(ticker, period="1d")
        if not df.empty:
            return float(df["Close"].iloc[-1])
    except Exception:
        pass
    # Fallback direct yfinance
    try:
        import yfinance as yf
        hist = yf.Ticker(ticker).history(period="1d")
        return float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception:
        return None


def _signal_sortie(pnl_pct: float, score: float,
                   stop_loss_pct: float = -8.0,
                   cible_pct: float = None) -> str:
    if pnl_pct <= stop_loss_pct or score <= -0.10:
        return "VENDRE"
    if cible_pct is not None and pnl_pct >= cible_pct:
        return "VENDRE"
    if pnl_pct <= stop_loss_pct / 2 or score <= 0.05:
        return "SURVEILLER"
    return "TENIR"


# ---------------------------------------------------------------------------
# Helpers internes
# ---------------------------------------------------------------------------

def _new_id() -> str:
    return str(uuid.uuid4())


def _calculer_pnl(prix_vente: float, prix_moyen: float,
                  quantite: float, frais: float = 0.0) -> dict:
    """P&L d'une vente : brut, net (frais déduits), pct."""
    pnl_brut = round((prix_vente - prix_moyen) * quantite, 2)
    pnl_net  = round(pnl_brut - frais, 2)
    pnl_pct  = round(pnl_net / (prix_moyen * quantite) * 100, 2) \
               if prix_moyen > 0 and quantite > 0 else 0.0
    return {"pnl_brut": pnl_brut, "pnl_net": pnl_net, "pnl_pct": pnl_pct}


def _calculer_cump(qty_avant: float, pm_avant: float,
                   qty_achat: float, prix: float, frais: float = 0.0) -> tuple[float, float]:
    """
    Formule pure du CUMP (Coût Unitaire Moyen Pondéré).

    Calcule le nouveau CUMP après un achat en partant de l'état COURANT
    de la position (qty_avant, pm_avant) — sans relire l'historique des
    transactions.  Cela garantit un résultat correct même après des
    ventes partielles.

    Args:
        qty_avant : quantité détenue avant cet achat
        pm_avant  : CUMP actuel avant cet achat
        qty_achat : quantité du nouvel achat
        prix      : prix unitaire du nouvel achat
        frais     : frais d'achat (majorent le coût de revient)

    Returns:
        (nouveau_qty, nouveau_cump)

    Exemples:
        Premier achat 10 @ 100 frais=1 :
            _calculer_cump(0, 0, 10, 100, 1) → (10, 100.1)

        Deuxième achat après vente partielle (5 restants @ CUMP 100, achat 5 @ 80) :
            _calculer_cump(5, 100, 5, 80) → (10, 90.0)
    """
    nouveau_qty = qty_avant + qty_achat
    if nouveau_qty <= 0:
        return 0.0, 0.0
    nouveau_pm = (qty_avant * pm_avant + qty_achat * prix + frais) / nouveau_qty
    return round(nouveau_qty, 6), round(nouveau_pm, 6)


# ---------------------------------------------------------------------------
# Achats
# ---------------------------------------------------------------------------

def ajouter_achat(user_id: str, ticker: str, prix: float, quantite: float,
                  date: str = None, notes: str = "", frais: float = 0.0,
                  broker_key: str = None) -> dict:
    """
    Enregistre un achat et recalcule le CUMP.

    Le CUMP est calculé à partir de l'état COURANT de la position
    (quantite + prix_moyen actuels) sans relire toutes les transactions
    historiques — ce qui garantit un résultat correct après ventes partielles.
    """
    ticker   = ticker.upper().strip()
    date     = date or datetime.now().strftime("%Y-%m-%d")
    prix     = round(float(prix), 6)
    quantite = round(float(quantite), 6)
    frais    = round(float(frais), 4)

    # ── Lire la position AVANT de la modifier ────────────────────────────────
    pos_avant   = get_position(user_id, ticker)
    qty_avant   = float(pos_avant["quantite"])   if pos_avant else 0.0
    pm_avant    = float(pos_avant["prix_moyen"]) if pos_avant else 0.0

    # ── Formule CUMP ──────────────────────────────────────────────────────────
    nouveau_qty, nouveau_pm = _calculer_cump(qty_avant, pm_avant, quantite, prix, frais)

    with get_conn() as conn:
        with conn.cursor() as cur:
            # Upsert position avec les valeurs calculées
            cur.execute(
                """
                INSERT INTO positions (user_id, ticker, quantite, prix_moyen, broker_key)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id, ticker) DO UPDATE
                  SET quantite   = EXCLUDED.quantite,
                      prix_moyen = EXCLUDED.prix_moyen,
                      broker_key = COALESCE(EXCLUDED.broker_key, positions.broker_key)
                """,
                (user_id, ticker, nouveau_qty, nouveau_pm, broker_key)
            )
            # Journaliser la transaction
            cur.execute(
                """
                INSERT INTO transactions
                  (user_id, ticker, type, date, prix, quantite, frais, notes)
                VALUES (%s, %s, 'achat', %s, %s, %s, %s, %s)
                """,
                (user_id, ticker, date, prix, quantite, frais, notes or "")
            )
        conn.commit()

    return get_position(user_id, ticker)


# ---------------------------------------------------------------------------
# Ventes
# ---------------------------------------------------------------------------

def ajouter_vente(user_id: str, ticker: str, prix_vente: float, quantite: float,
                  date: str = None, notes: str = "", frais: float = 0.0) -> dict:
    """Enregistre une vente et recalcule la position."""
    ticker   = ticker.upper().strip()
    date     = date or datetime.now().strftime("%Y-%m-%d")
    pos      = get_position(user_id, ticker)

    if not pos or float(pos["quantite"]) <= 0:
        raise ValueError(f"Aucune position ouverte pour {ticker}")

    quantite = round(float(quantite), 6)
    if quantite > float(pos["quantite"]) + 1e-9:
        raise ValueError(
            f"Quantité insuffisante : tu as {pos['quantite']} {ticker}, "
            f"tu essaies de vendre {quantite}"
        )

    frais            = round(float(frais), 4)
    prix_moyen_achat = float(pos["prix_moyen"])
    pnl              = _calculer_pnl(float(prix_vente), prix_moyen_achat, quantite, frais)
    pnl_brut         = pnl["pnl_brut"]
    pnl_eur          = pnl["pnl_net"]

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transactions
                  (user_id, ticker, type, date, prix, quantite, frais,
                   pnl_brut, pnl_eur, prix_moyen_achat, notes)
                VALUES (%s, %s, 'vente', %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, ticker, date,
                 round(float(prix_vente), 6), quantite, frais,
                 pnl_brut, pnl_eur, round(prix_moyen_achat, 6), notes or "")
            )
            tx_id = cur.fetchone()[0]

            # Réduit la quantité en position
            cur.execute(
                """
                UPDATE positions
                SET quantite = quantite - %s
                WHERE user_id = %s AND ticker = %s
                """,
                (quantite, user_id, ticker)
            )
        conn.commit()

    return {"id": str(tx_id), "pnl_brut": pnl_brut, "pnl_eur": pnl_eur, "pnl_pct": pnl["pnl_pct"]}


# ---------------------------------------------------------------------------
# Lecture
# ---------------------------------------------------------------------------

def _normaliser_position(row: dict | None) -> dict | None:
    """Convertit Decimal → float et UUID → str pour une position."""
    if row is None:
        return None
    row = dict(row)
    for k in ("quantite", "prix_moyen", "stop_loss_pct", "cible_pct"):
        if row.get(k) is not None:
            row[k] = float(row[k])
    row["id"]      = str(row["id"])
    row["user_id"] = str(row["user_id"])
    return row


def get_position(user_id: str, ticker: str) -> dict | None:
    row = execute(
        "SELECT * FROM positions WHERE user_id = %s AND ticker = %s",
        (user_id, ticker.upper().strip()), fetch="one"
    )
    return _normaliser_position(row)


def lister_positions(user_id: str) -> list[dict]:
    rows = execute(
        "SELECT * FROM positions WHERE user_id = %s AND quantite > 0 ORDER BY ticker",
        (user_id,), fetch="all"
    )
    return [_normaliser_position(r) for r in rows] if rows else []


def lister_transactions(user_id: str, ticker: str) -> list[dict]:
    rows = execute(
        """
        SELECT * FROM transactions
        WHERE user_id = %s AND ticker = %s
        ORDER BY date DESC, created_at DESC
        """,
        (user_id, ticker.upper().strip()), fetch="all"
    )
    if not rows:
        return []
    result = []
    for r in rows:
        row = dict(r)
        for k in ("prix", "quantite", "frais", "pnl_brut", "pnl_eur", "prix_moyen_achat"):
            if row.get(k) is not None:
                row[k] = float(row[k])
        row["id"]      = str(row["id"])
        row["user_id"] = str(row["user_id"])
        if row.get("date"):
            row["date"] = str(row["date"])
        result.append(row)
    return result


def lister_historique(user_id: str) -> list[dict]:
    """Toutes les ventes (historique réalisé) avec pnl_pct calculé."""
    rows = execute(
        """
        SELECT *,
            CASE WHEN prix_moyen_achat > 0 AND quantite > 0
                 THEN ROUND(pnl_eur / (prix_moyen_achat * quantite) * 100, 2)
                 ELSE 0
            END AS pnl_pct,
            prix AS prix_vente
        FROM transactions
        WHERE user_id = %s AND type = 'vente'
        ORDER BY date DESC, created_at DESC
        """,
        (user_id,), fetch="all"
    )
    if not rows:
        return []
    # Convertir Decimal → float et UUID → str
    result = []
    for r in rows:
        row = dict(r)
        for k in ("prix", "quantite", "frais", "pnl_brut", "pnl_eur",
                  "pnl_pct", "prix_moyen_achat", "prix_vente"):
            if row.get(k) is not None:
                row[k] = float(row[k])
        row["id"] = str(row["id"])
        row["user_id"] = str(row["user_id"])
        if row.get("date"):
            row["date"] = str(row["date"])
        result.append(row)
    return result


def evaluer_positions(user_id: str, with_scores: bool = True) -> list[dict]:
    """
    Retourne les positions actives enrichies avec P&L, score et signal de sortie.
    Interface identique à data/portfolio.evaluer_positions, avec user_id.
    """
    from orchestrator.orchestrator import run as orchestrer

    positions = lister_positions(user_id)
    resultats = []

    for pos in positions:
        ticker        = pos["ticker"]
        prix_moyen    = float(pos["prix_moyen"])
        quantite      = float(pos["quantite"])
        stop_loss_pct = float(pos["stop_loss_pct"]) if pos.get("stop_loss_pct") else -8.0
        cible_pct     = float(pos["cible_pct"])     if pos.get("cible_pct")     else None
        investi       = round(prix_moyen * quantite, 2)

        prix_now = _prix_actuel(ticker)
        if prix_now:
            pnl_eur = round((prix_now - prix_moyen) * quantite, 2)
            pnl_pct = round((prix_now - prix_moyen) / prix_moyen * 100, 2)
            valeur  = round(prix_now * quantite, 2)
        else:
            pnl_eur = pnl_pct = valeur = None

        score  = 0.0
        signal = "SURVEILLER"

        if with_scores:
            try:
                r     = orchestrer(ticker, with_llm=False, user_id=user_id)
                score = r["scoring"]["score_final"]
            except Exception:
                pass

        if pnl_pct is not None:
            signal = _signal_sortie(pnl_pct, score, stop_loss_pct, cible_pct)

        # Date du premier achat depuis transactions
        date_premier_achat = None
        jours = None
        try:
            row = execute(
                """
                SELECT MIN(date) AS premiere_date FROM transactions
                WHERE user_id = %s AND ticker = %s AND type = 'achat'
                """,
                (user_id, ticker), fetch="one"
            )
            if row and row["premiere_date"]:
                date_premier_achat = str(row["premiere_date"])
                jours = (datetime.now().date() -
                         datetime.strptime(date_premier_achat, "%Y-%m-%d").date()).days
        except Exception:
            pass

        resultats.append({
            "ticker":        ticker,
            "quantite":      quantite,
            "prix_moyen":    prix_moyen,
            "prix_actuel":   prix_now,
            "valeur":        valeur,
            "investi":       investi,
            "pnl_eur":       pnl_eur,
            "pnl_pct":       pnl_pct,
            "jours":         jours,
            "date_achat":    date_premier_achat,
            "score":         round(score, 4),
            "signal_sortie": signal,
            "cible_pct":     cible_pct,
            "stop_loss_pct": stop_loss_pct,
            "prix_cible":    round(prix_moyen * (1 + cible_pct / 100), 4)     if cible_pct     else None,
            "prix_stop":     round(prix_moyen * (1 + stop_loss_pct / 100), 4) if stop_loss_pct else None,
            "broker_key":    pos.get("broker_key"),
        })

    return resultats


# ---------------------------------------------------------------------------
# Modification
# ---------------------------------------------------------------------------

def definir_objectifs(user_id: str, ticker: str,
                      cible_pct: float = None,
                      stop_loss_pct: float = None) -> None:
    execute(
        """
        UPDATE positions
        SET cible_pct     = COALESCE(%s, cible_pct),
            stop_loss_pct = COALESCE(%s, stop_loss_pct)
        WHERE user_id = %s AND ticker = %s
        """,
        (cible_pct, stop_loss_pct, user_id, ticker.upper().strip())
    )


def modifier_note_transaction(user_id: str, tx_id: str, note: str) -> None:
    execute(
        "UPDATE transactions SET notes = %s WHERE id = %s AND user_id = %s",
        (note.strip(), tx_id, user_id)
    )


def supprimer_position(user_id: str, ticker: str) -> None:
    """
    Supprime la position ET toutes ses transactions.

    Important : supprimer les transactions évite que `ajouter_achat`
    hérite d'un historique fantôme si le ticker est rajouté plus tard.
    """
    ticker = ticker.upper().strip()
    execute(
        "DELETE FROM transactions WHERE user_id = %s AND ticker = %s",
        (user_id, ticker)
    )
    execute(
        "DELETE FROM positions WHERE user_id = %s AND ticker = %s",
        (user_id, ticker)
    )


def supprimer_vente(user_id: str, tx_id: str) -> None:
    execute(
        "DELETE FROM transactions WHERE id = %s AND user_id = %s AND type = 'vente'",
        (tx_id, user_id)
    )
