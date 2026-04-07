"""
Test rapide de la couche db/ après correction des FK.
Usage : python db/test_db.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.auth import inscrire, connecter
from db.client import execute
from db.portfolio import ajouter_achat, lister_positions, ajouter_vente
from db.alerts_store import ajouter_alerte, lister_alertes
from db.score_history import enregistrer_score, lire_historique

EMAIL    = "test_fk@example.com"
PASSWORD = "TestFix123"
USERNAME = "test_fk_user"

def cleanup(email):
    row = execute("SELECT id FROM users WHERE email = %s", (email,), fetch="one")
    if row:
        execute("DELETE FROM users WHERE id = %s", (row["id"],))
        print(f"  [cleanup] user {email} supprime")

def main():
    print("\n=== Test couche db/ ===\n")
    cleanup(EMAIL)

    # 1. Inscription
    print("1. Inscription...")
    user = inscrire(USERNAME, EMAIL, PASSWORD)
    print(f"   OK -> user_id = {user['id']}")

    uid = user["id"]

    # 2. Connexion
    print("2. Connexion...")
    u2 = connecter(EMAIL, PASSWORD)
    assert u2["id"] == uid
    print(f"   OK -> {u2['username']}")

    # 3. Achat (le test qui echouait avec FK violation)
    print("3. Ajout achat AAPL...")
    pos = ajouter_achat(uid, "AAPL", prix=150.0, quantite=10, frais=1.0)
    print(f"   OK -> quantite={pos['quantite']} prix_moyen={pos['prix_moyen']}")

    # 4. Lister positions
    print("4. Lister positions...")
    positions = lister_positions(uid)
    assert len(positions) == 1
    print(f"   OK -> {len(positions)} position(s)")

    # 5. Vente
    print("5. Vente AAPL...")
    result = ajouter_vente(uid, "AAPL", prix_vente=160.0, quantite=5, frais=1.0)
    print(f"   OK -> pnl_brut={result['pnl_brut']} pnl_eur={result['pnl_eur']}")

    # 6. Score history
    print("6. Enregistrement score...")
    enregistrer_score(uid, "AAPL", score=0.42, decision="ACHETER",
                      prix=160.0, scores_agents={"technical": 0.5, "macro": 0.3})
    hist = lire_historique(uid, "AAPL")
    assert len(hist) == 1
    print(f"   OK -> {len(hist)} entree(s) dans historique")

    # 7. Alertes
    print("7. Ajout alerte...")
    ajouter_alerte(uid, "AAPL", "info", "Test alerte")
    alertes = lister_alertes(uid)
    assert len(alertes) == 1
    print(f"   OK -> {len(alertes)} alerte(s)")

    # Cleanup
    cleanup(EMAIL)

    print("\n=== TOUS LES TESTS PASSES ===\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nERREUR : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
