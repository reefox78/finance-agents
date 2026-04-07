"""
Migration one-shot : JSON → PostgreSQL.

Importe les données existantes (portfolio.json, score_history.json, alerts.json)
pour un utilisateur donné.

Usage :
    python db/migrate.py --email ton@email.com
"""

import json
import argparse
from pathlib import Path
from db.auth import connecter
from db.client import execute, get_conn

ROOT = Path(__file__).parent.parent


def migrer_portfolio(user_id: str) -> None:
    fichier = ROOT / "data" / "portfolio.json"
    if not fichier.exists():
        print("  Pas de portfolio.json — ignoré")
        return

    data = json.loads(fichier.read_text(encoding="utf-8"))
    positions = data.get("positions", {})
    nb_pos = 0
    nb_tx  = 0

    with get_conn() as conn:
        for ticker, pos in positions.items():
            with conn.cursor() as cur:
                # Upsert position
                cur.execute(
                    """
                    INSERT INTO positions
                      (user_id, ticker, quantite, prix_moyen, broker_key,
                       stop_loss_pct, cible_pct)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, ticker) DO UPDATE
                      SET quantite      = EXCLUDED.quantite,
                          prix_moyen    = EXCLUDED.prix_moyen,
                          broker_key    = EXCLUDED.broker_key,
                          stop_loss_pct = EXCLUDED.stop_loss_pct,
                          cible_pct     = EXCLUDED.cible_pct
                    """,
                    (user_id, ticker,
                     pos.get("quantite", 0),
                     pos.get("prix_moyen", 0),
                     pos.get("broker_key"),
                     pos.get("stop_loss_pct"),
                     pos.get("cible_pct"))
                )
                nb_pos += 1

                # Transactions
                for tx in pos.get("transactions", []):
                    cur.execute(
                        """
                        INSERT INTO transactions
                          (user_id, ticker, type, date, prix, quantite, frais,
                           pnl_brut, pnl_eur, prix_moyen_achat, notes)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING
                        """,
                        (user_id, ticker,
                         tx.get("type"),
                         tx.get("date"),
                         tx.get("prix", 0),
                         tx.get("quantite", 0),
                         tx.get("frais", 0),
                         tx.get("pnl_brut"),
                         tx.get("pnl_eur"),
                         tx.get("prix_moyen_achat"),
                         tx.get("notes") or "")
                    )
                    nb_tx += 1
        conn.commit()

    print(f"  Portfolio : {nb_pos} positions, {nb_tx} transactions importées")


def migrer_score_history(user_id: str) -> None:
    fichier = ROOT / "data" / "score_history.json"
    if not fichier.exists():
        print("  Pas de score_history.json — ignoré")
        return

    data  = json.loads(fichier.read_text(encoding="utf-8"))
    nb    = 0

    with get_conn() as conn:
        for ticker, entrees in data.items():
            for e in entrees:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO score_history
                          (user_id, ticker, ts, score, decision, prix, scores_agents)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (user_id, ticker,
                         e.get("ts"),
                         e.get("score", 0),
                         e.get("decision", "NEUTRE"),
                         e.get("prix"),
                         json.dumps(e.get("scores_agents")) if e.get("scores_agents") else None)
                    )
                    nb += 1
        conn.commit()

    print(f"  Score history : {nb} entrées importées")


def migrer_alertes(user_id: str) -> None:
    fichier = ROOT / "data" / "alerts.json"
    if not fichier.exists():
        print("  Pas de alerts.json — ignoré")
        return

    data = json.loads(fichier.read_text(encoding="utf-8"))
    nb   = 0

    with get_conn() as conn:
        for alerte in data if isinstance(data, list) else data.get("alertes", []):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO alerts (user_id, ticker, type, message, lue, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id,
                     alerte.get("ticker", ""),
                     alerte.get("type", "info"),
                     alerte.get("message", ""),
                     alerte.get("lue", False),
                     alerte.get("date") or alerte.get("created_at"))
                )
                nb += 1
        conn.commit()

    print(f"  Alertes : {nb} importées")


def main():
    parser = argparse.ArgumentParser(description="Migration JSON → PostgreSQL")
    parser.add_argument("--email", required=True, help="Email du compte à utiliser")
    parser.add_argument("--password", default=None, help="Mot de passe (demandé si absent)")
    args = parser.parse_args()

    import getpass
    password = args.password or getpass.getpass(f"Mot de passe pour {args.email} : ")

    try:
        user = connecter(args.email, password)
    except ValueError as e:
        print(f"Erreur de connexion : {e}")
        return

    print(f"\nMigration pour {user['username']} ({user['id']})...")
    migrer_portfolio(user["id"])
    migrer_score_history(user["id"])
    migrer_alertes(user["id"])
    print("\nMigration terminée ✅")


if __name__ == "__main__":
    main()
