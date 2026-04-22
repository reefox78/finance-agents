-- ============================================================
-- Migration 002 : Journal de trading
-- ============================================================

CREATE TABLE IF NOT EXISTS public.trade_journal (
    id                UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID         NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    -- Identité du trade
    ticker            VARCHAR(20)  NOT NULL,
    direction         VARCHAR(5)   NOT NULL DEFAULT 'LONG' CHECK (direction IN ('LONG','SHORT')),
    strategy          VARCHAR(50),          -- Swing, Day Trading, Momentum, Breakout, Valeur, Contrarian

    -- Entrée
    entry_price       NUMERIC(18,4) NOT NULL,
    entry_date        DATE          NOT NULL,
    quantity          NUMERIC(18,4) NOT NULL DEFAULT 1,

    -- Signal app au moment de l'entrée (facultatif)
    score_at_entry    NUMERIC(8,4),
    decision_at_entry VARCHAR(10),

    -- Sortie (rempli à la clôture)
    exit_price        NUMERIC(18,4),
    exit_date         DATE,

    -- Résultat (calculé à la clôture)
    pnl               NUMERIC(18,2),        -- en € / unité de devise
    pnl_pct           NUMERIC(8,4),         -- en %

    -- Méta
    notes             TEXT,
    status            VARCHAR(10)  NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trade_journal_user   ON public.trade_journal (user_id, status);
CREATE INDEX IF NOT EXISTS idx_trade_journal_ticker ON public.trade_journal (user_id, ticker);
CREATE INDEX IF NOT EXISTS idx_trade_journal_date   ON public.trade_journal (user_id, exit_date DESC NULLS LAST);

-- Trigger updated_at
DROP TRIGGER IF EXISTS trg_trade_journal_updated_at ON public.trade_journal;
CREATE TRIGGER trg_trade_journal_updated_at
    BEFORE UPDATE ON public.trade_journal
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
