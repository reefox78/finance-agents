"""
Applique la migration is_admin et se désigne admin.
Usage : python scripts/migrate_admin.py [email_admin]
  Si email_admin est fourni, ce compte devient admin.
  Sinon, le premier compte créé devient admin.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv("config/.env")

from db.client import execute


def run(admin_email: str | None = None) -> None:
    # 1. Ajoute la colonne si absente
    execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
    )
    print("Colonne is_admin : OK")

    # 2. Désigne l'admin
    if admin_email:
        email = admin_email.strip().lower()
        user = execute("SELECT id, username FROM users WHERE email = %s", (email,), fetch="one")
        if not user:
            print(f"Aucun compte trouvé pour {email}")
            sys.exit(1)
        execute("UPDATE users SET is_admin = TRUE WHERE email = %s", (email,))
        print(f"Admin : {user['username']} ({email})")
    else:
        execute(
            "UPDATE users SET is_admin = TRUE WHERE created_at = (SELECT MIN(created_at) FROM users)"
        )
        user = execute("SELECT username, email FROM users WHERE is_admin = TRUE LIMIT 1", fetch="one")
        if user:
            print(f"Admin (premier compte) : {user['username']} ({user['email']})")

    print("Migration terminée.")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else None)
