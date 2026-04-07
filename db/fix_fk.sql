-- ============================================================
-- Fix FK constraints : pointer explicitement vers public.users
-- A exécuter dans Supabase SQL Editor si les tables existent déjà
-- ============================================================

-- positions
ALTER TABLE public.positions DROP CONSTRAINT IF EXISTS positions_user_id_fkey;
ALTER TABLE public.positions
    ADD CONSTRAINT positions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- transactions
ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_user_id_fkey;
ALTER TABLE public.transactions
    ADD CONSTRAINT transactions_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- score_history
ALTER TABLE public.score_history DROP CONSTRAINT IF EXISTS score_history_user_id_fkey;
ALTER TABLE public.score_history
    ADD CONSTRAINT score_history_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- alerts
ALTER TABLE public.alerts DROP CONSTRAINT IF EXISTS alerts_user_id_fkey;
ALTER TABLE public.alerts
    ADD CONSTRAINT alerts_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- Vérification
SELECT
    tc.table_name,
    tc.constraint_name,
    ccu.table_schema AS foreign_schema,
    ccu.table_name   AS foreign_table
FROM information_schema.table_constraints AS tc
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND tc.table_schema = 'public'
  AND ccu.column_name = 'id'
ORDER BY tc.table_name;
