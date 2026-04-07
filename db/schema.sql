-- ============================================================
-- Finance Agents — Schéma PostgreSQL (Supabase)
-- Connexion directe via psycopg2, auth custom bcrypt
-- ============================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- TABLE : users
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(50)  UNIQUE NOT NULL,
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,   -- bcrypt, jamais le mot de passe en clair
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TABLE : positions
-- ============================================================
CREATE TABLE IF NOT EXISTS positions (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    ticker        VARCHAR(30)   NOT NULL,
    quantite      NUMERIC(18,6) NOT NULL DEFAULT 0,
    prix_moyen    NUMERIC(18,6) NOT NULL DEFAULT 0,
    broker_key    VARCHAR(50),
    stop_loss_pct NUMERIC(8,4),
    cible_pct     NUMERIC(8,4),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, ticker)
);

-- ============================================================
-- TABLE : transactions
-- ============================================================
CREATE TABLE IF NOT EXISTS transactions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    ticker           VARCHAR(30)   NOT NULL,
    type             VARCHAR(10)   NOT NULL CHECK (type IN ('achat', 'vente')),
    date             DATE          NOT NULL,
    prix             NUMERIC(18,6) NOT NULL,
    quantite         NUMERIC(18,6) NOT NULL,
    frais            NUMERIC(10,4) NOT NULL DEFAULT 0,
    pnl_brut         NUMERIC(18,2),
    pnl_eur          NUMERIC(18,2),
    prix_moyen_achat NUMERIC(18,6),
    notes            TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TABLE : score_history
-- ============================================================
CREATE TABLE IF NOT EXISTS score_history (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    ticker        VARCHAR(30)  NOT NULL,
    ts            TIMESTAMPTZ  NOT NULL DEFAULT now(),
    score         NUMERIC(8,4) NOT NULL,
    decision      VARCHAR(10)  NOT NULL,
    prix          NUMERIC(18,6),
    scores_agents JSONB,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================
-- TABLE : alerts
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    ticker     VARCHAR(30) NOT NULL,
    type       VARCHAR(50) NOT NULL,
    message    TEXT        NOT NULL,
    lue        BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- INDEX
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_positions_user       ON positions     (user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user    ON transactions  (user_id, ticker);
CREATE INDEX IF NOT EXISTS idx_score_history_user   ON score_history (user_id, ticker, ts DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user_non_lues ON alerts        (user_id, lue);

-- ============================================================
-- TRIGGER : updated_at automatique sur positions
-- ============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_positions_updated_at ON positions;
CREATE TRIGGER trg_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
