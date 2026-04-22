"""
Fonctions DB pour le journal de trading.
Table : trade_journal
"""
from __future__ import annotations
from datetime import date
from typing import Optional
from db.client import execute


# ── Initialisation ────────────────────────────────────────────────────────────

def init_table() -> None:
    """Crée la table trade_journal si elle n'existe pas (idempotent)."""
    execute("""
        CREATE TABLE IF NOT EXISTS public.trade_journal (
            id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id           UUID         NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            ticker            VARCHAR(20)  NOT NULL,
            direction         VARCHAR(5)   NOT NULL DEFAULT 'LONG'
                              CHECK (direction IN ('LONG','SHORT')),
            strategy          VARCHAR(50),
            entry_price       NUMERIC(18,4) NOT NULL,
            entry_date        DATE          NOT NULL,
            quantity          NUMERIC(18,4) NOT NULL DEFAULT 1,
            score_at_entry    NUMERIC(8,4),
            decision_at_entry VARCHAR(10),
            exit_price        NUMERIC(18,4),
            exit_date         DATE,
            pnl               NUMERIC(18,2),
            pnl_pct           NUMERIC(8,4),
            notes             TEXT,
            status            VARCHAR(10)  NOT NULL DEFAULT 'OPEN'
                              CHECK (status IN ('OPEN','CLOSED')),
            created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
            updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
        )
    """, fetch="none")
    execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_journal_user
        ON public.trade_journal (user_id, status)
    """, fetch="none")
    execute("""
        CREATE INDEX IF NOT EXISTS idx_trade_journal_date
        ON public.trade_journal (user_id, exit_date DESC NULLS LAST)
    """, fetch="none")
    # Trigger updated_at (réutilise la fonction existante du schéma)
    execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_trade_journal_updated_at'
            ) THEN
                CREATE TRIGGER trg_trade_journal_updated_at
                BEFORE UPDATE ON public.trade_journal
                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            END IF;
        END $$;
    """, fetch="none")


# ── CRUD ─────────────────────────────────────────────────────────────────────

def list_trades(
    user_id: str,
    status:   Optional[str] = None,   # OPEN | CLOSED | None = all
    strategy: Optional[str] = None,
    ticker:   Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    conditions = ["user_id = %s"]
    params: list = [user_id]

    if status:
        conditions.append("status = %s")
        params.append(status.upper())
    if strategy:
        conditions.append("strategy = %s")
        params.append(strategy)
    if ticker:
        conditions.append("ticker ILIKE %s")
        params.append(f"%{ticker.upper()}%")

    where = " AND ".join(conditions)
    params.append(limit)
    return execute(
        f"""
        SELECT id, ticker, direction, strategy,
               entry_price, entry_date, quantity,
               score_at_entry, decision_at_entry,
               exit_price, exit_date,
               pnl, pnl_pct, notes, status,
               created_at, updated_at
        FROM trade_journal
        WHERE {where}
        ORDER BY
            CASE WHEN status = 'OPEN' THEN 0 ELSE 1 END,
            entry_date DESC
        LIMIT %s
        """,
        params,
        fetch="all",
    ) or []


def add_trade(
    user_id:           str,
    ticker:            str,
    direction:         str,
    entry_price:       float,
    entry_date:        str,      # ISO date string
    quantity:          float,
    strategy:          Optional[str]   = None,
    score_at_entry:    Optional[float] = None,
    decision_at_entry: Optional[str]   = None,
    notes:             Optional[str]   = None,
) -> dict:
    return execute(
        """
        INSERT INTO trade_journal
            (user_id, ticker, direction, strategy,
             entry_price, entry_date, quantity,
             score_at_entry, decision_at_entry, notes, status)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'OPEN')
        RETURNING id, ticker, direction, strategy,
                  entry_price, entry_date, quantity,
                  score_at_entry, decision_at_entry,
                  exit_price, exit_date, pnl, pnl_pct, notes, status,
                  created_at, updated_at
        """,
        [
            user_id, ticker.upper(), direction.upper(), strategy,
            entry_price, entry_date, quantity,
            score_at_entry, decision_at_entry, notes,
        ],
        fetch="one",
    )


def close_trade(
    user_id:    str,
    trade_id:   str,
    exit_price: float,
    exit_date:  str,  # ISO date string
) -> dict | None:
    """Clôture un trade et calcule le P&L."""
    trade = execute(
        "SELECT * FROM trade_journal WHERE id = %s AND user_id = %s AND status = 'OPEN'",
        [trade_id, user_id],
        fetch="one",
    )
    if not trade:
        return None

    entry  = float(trade["entry_price"])
    qty    = float(trade["quantity"])
    direct = trade["direction"]

    if direct == "LONG":
        pnl     = (exit_price - entry) * qty
        pnl_pct = (exit_price - entry) / entry * 100
    else:  # SHORT
        pnl     = (entry - exit_price) * qty
        pnl_pct = (entry - exit_price) / entry * 100

    return execute(
        """
        UPDATE trade_journal
        SET exit_price = %s,
            exit_date  = %s,
            pnl        = %s,
            pnl_pct    = %s,
            status     = 'CLOSED'
        WHERE id = %s AND user_id = %s
        RETURNING id, ticker, direction, strategy,
                  entry_price, entry_date, quantity,
                  score_at_entry, decision_at_entry,
                  exit_price, exit_date, pnl, pnl_pct, notes, status,
                  created_at, updated_at
        """,
        [exit_price, exit_date, round(pnl, 2), round(pnl_pct, 4), trade_id, user_id],
        fetch="one",
    )


def update_notes(user_id: str, trade_id: str, notes: str) -> dict | None:
    return execute(
        """
        UPDATE trade_journal SET notes = %s
        WHERE id = %s AND user_id = %s
        RETURNING id, ticker, notes, status
        """,
        [notes, trade_id, user_id],
        fetch="one",
    )


def delete_trade(user_id: str, trade_id: str) -> bool:
    result = execute(
        "DELETE FROM trade_journal WHERE id = %s AND user_id = %s RETURNING id",
        [trade_id, user_id],
        fetch="one",
    )
    return result is not None


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats(user_id: str) -> dict:
    """
    Calcule les métriques de performance du journal :
    - Globales : total trades, win rate, P&L total, profit factor, max drawdown
    - Par stratégie : breakdown win rate + P&L
    - Equity curve : P&L cumulé par date de clôture
    - Streak : série gagnante / perdante en cours
    """
    closed = execute(
        """
        SELECT ticker, strategy, pnl, pnl_pct, exit_date, direction
        FROM trade_journal
        WHERE user_id = %s AND status = 'CLOSED'
        ORDER BY exit_date ASC
        """,
        [user_id],
        fetch="all",
    ) or []

    open_count = execute(
        "SELECT COUNT(*) AS n FROM trade_journal WHERE user_id = %s AND status = 'OPEN'",
        [user_id],
        fetch="one",
    )

    total_closed = len(closed)
    total_open   = int(open_count["n"]) if open_count else 0

    if total_closed == 0:
        return {
            "total_trades":  total_open,
            "open_trades":   total_open,
            "closed_trades": 0,
            "win_rate":      None,
            "total_pnl":     0.0,
            "avg_pnl":       None,
            "avg_pnl_pct":   None,
            "profit_factor": None,
            "max_drawdown":  None,
            "best_trade":    None,
            "worst_trade":   None,
            "by_strategy":   {},
            "equity_curve":  [],
            "current_streak":{"type": None, "count": 0},
        }

    pnls = [float(r["pnl"] or 0) for r in closed]
    wins  = [p for p in pnls if p > 0]
    losses= [p for p in pnls if p <= 0]

    total_pnl    = round(sum(pnls), 2)
    win_rate     = round(len(wins) / total_closed * 100, 1)
    avg_pnl      = round(sum(pnls) / total_closed, 2)
    avg_pnl_pct  = round(sum(float(r["pnl_pct"] or 0) for r in closed) / total_closed, 2)
    profit_factor = round(sum(wins) / abs(sum(losses)), 2) if losses and sum(losses) != 0 else None

    # Max drawdown (peak-to-trough sur l'equity curve)
    cumul    = 0.0
    peak     = 0.0
    drawdown = 0.0
    for p in pnls:
        cumul += p
        if cumul > peak:
            peak = cumul
        dd = peak - cumul
        if dd > drawdown:
            drawdown = dd
    max_drawdown = round(-drawdown, 2)

    # Best / worst trade
    best  = max(closed, key=lambda r: float(r["pnl"] or 0))
    worst = min(closed, key=lambda r: float(r["pnl"] or 0))

    # Par stratégie
    by_strategy: dict = {}
    for r in closed:
        strat = r["strategy"] or "Autre"
        s = by_strategy.setdefault(strat, {"trades":0,"wins":0,"pnl":0.0})
        p = float(r["pnl"] or 0)
        s["trades"] += 1
        s["pnl"]    += p
        if p > 0:
            s["wins"] += 1
    for strat, s in by_strategy.items():
        s["pnl"]      = round(s["pnl"], 2)
        s["win_rate"] = round(s["wins"] / s["trades"] * 100, 1) if s["trades"] else 0

    # Equity curve (cumul par exit_date)
    equity_curve: list[dict] = []
    cumul = 0.0
    for r in closed:
        cumul += float(r["pnl"] or 0)
        equity_curve.append({
            "date":  str(r["exit_date"]),
            "cumul": round(cumul, 2),
            "pnl":   round(float(r["pnl"] or 0), 2),
        })

    # Streak actuelle (à partir de la fin)
    streak_type  = None
    streak_count = 0
    for p in reversed(pnls):
        t = "win" if p > 0 else "loss"
        if streak_type is None:
            streak_type = t
            streak_count = 1
        elif t == streak_type:
            streak_count += 1
        else:
            break

    return {
        "total_trades":  total_closed + total_open,
        "open_trades":   total_open,
        "closed_trades": total_closed,
        "win_rate":      win_rate,
        "total_pnl":     total_pnl,
        "avg_pnl":       avg_pnl,
        "avg_pnl_pct":   avg_pnl_pct,
        "profit_factor": profit_factor,
        "max_drawdown":  max_drawdown,
        "best_trade":    {"ticker": best["ticker"], "pnl": float(best["pnl"] or 0)},
        "worst_trade":   {"ticker": worst["ticker"], "pnl": float(worst["pnl"] or 0)},
        "by_strategy":   by_strategy,
        "equity_curve":  equity_curve,
        "current_streak":{"type": streak_type, "count": streak_count},
    }
