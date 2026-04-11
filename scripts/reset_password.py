"""
Reset le mot de passe d'un utilisateur directement en base.
Usage : python scripts/reset_password.py <email> <nouveau_mot_de_passe>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv("config/.env")

import bcrypt
from db.client import execute


def reset_password(email: str, new_password: str) -> None:
    # Vérifie que le compte existe
    user = execute(
        "SELECT id, username FROM users WHERE email = %s",
        (email.strip().lower(),), fetch="one"
    )
    if not user:
        print(f"Aucun compte trouvé pour {email}")
        sys.exit(1)

    # Hash + update
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt(rounds=12)).decode()
    execute(
        "UPDATE users SET password_hash = %s WHERE email = %s",
        (hashed, email.strip().lower())
    )
    print(f"Mot de passe réinitialisé pour {user['username']} ({email})")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage : python scripts/reset_password.py <email> <nouveau_mot_de_passe>")
        sys.exit(1)

    reset_password(sys.argv[1], sys.argv[2])
