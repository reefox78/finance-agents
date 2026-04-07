-- ============================================================
-- Migration : ajout support Google OAuth
-- À exécuter dans Supabase SQL Editor (une seule fois)
-- ============================================================

-- password_hash devient nullable (comptes créés via Google n'ont pas de mot de passe)
ALTER TABLE public.users ALTER COLUMN password_hash DROP NOT NULL;

-- google_id : identifiant unique fourni par Google (champ "sub")
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255);

-- auth_provider : 'local' (email+mdp) ou 'google'
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'local';

-- Index pour retrouver un compte par google_id rapidement
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id ON public.users (google_id)
    WHERE google_id IS NOT NULL;

-- Marquer les comptes existants comme 'local'
UPDATE public.users SET auth_provider = 'local' WHERE auth_provider IS NULL;

-- Vérification
SELECT id, username, email, auth_provider, google_id IS NOT NULL AS has_google
FROM public.users
ORDER BY created_at DESC
LIMIT 10;
