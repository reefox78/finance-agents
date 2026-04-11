-- Migration : ajout colonne is_admin sur users
-- À exécuter une fois manuellement ou via migrate_admin.py

ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- Donne le rôle admin au premier compte créé (le tien)
UPDATE users SET is_admin = TRUE
WHERE created_at = (SELECT MIN(created_at) FROM users);
