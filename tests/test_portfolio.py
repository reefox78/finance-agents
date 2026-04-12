"""
Tests unitaires — data/portfolio.py
Vérifie le calcul CUMP, la gestion des achats/ventes, des frais, et de l'historique.

Équivalent JUnit : chaque classe = un groupe de tests, chaque méthode = un cas précis.
Les tests sont isolés : chacun utilise un fichier portfolio temporaire (tmp_path).
"""

import pytest
import data.portfolio as portfolio
from data.portfolio import calculer_cump, calculer_pnl


# ===========================================================================
# TestCalculerCUMP — formule pure, sans accès fichier
# ===========================================================================

class TestCalculerCUMP:
    """
    Tests de la formule CUMP isolée.
    Ces tests détectent le bug classique : recalcul incorrect après vente partielle.
    """

    def test_premier_achat_sans_frais(self):
        """Premier achat depuis zéro — cas de base."""
        qty, cump = calculer_cump(0, 0, 10, 100)
        assert qty  == pytest.approx(10.0)
        assert cump == pytest.approx(100.0)

    def test_premier_achat_avec_frais(self):
        """Les frais majorent le CUMP : (10×100 + 1) / 10 = 100.10."""
        qty, cump = calculer_cump(0, 0, 10, 100, frais=1.0)
        assert qty  == pytest.approx(10.0)
        assert cump == pytest.approx(100.10, rel=1e-4)

    def test_deuxieme_achat_recalcule_cump(self):
        """
        Deux achats successifs :
          Achat 1 : 10 @ 100 → CUMP = 100
          Achat 2 : 20 @ 120 → CUMP = (10×100 + 20×120) / 30 = 113.33…
        """
        qty1, cump1 = calculer_cump(0, 0, 10, 100)
        qty2, cump2 = calculer_cump(qty1, cump1, 20, 120)
        assert qty2  == pytest.approx(30.0)
        assert cump2 == pytest.approx(113.333, rel=1e-3)

    def test_achat_apres_vente_partielle(self):
        """
        BUG CLASSIQUE — ce test révèle le défaut de _recalculer_cump (db).

        Si on re-somme toutes les transactions d'achat au lieu de partir
        de l'état courant, on obtient qty=15 et CUMP≈93.33 au lieu de
        qty=10 et CUMP=90.

        Scénario :
          Achat : 10 @ 100 → qty=10, CUMP=100
          Vente : 5 @ 110  → qty=5,  CUMP inchangé = 100
          Achat : 5 @ 80   → doit donner qty=10, CUMP=(5×100 + 5×80)/10 = 90
        """
        _, cump1 = calculer_cump(0, 0, 10, 100)         # achat initial
        # après vente partielle : qty=5, CUMP toujours 100
        qty_apres_vente = 5.0
        qty_final, cump_final = calculer_cump(qty_apres_vente, cump1, 5, 80)
        assert qty_final  == pytest.approx(10.0)
        assert cump_final == pytest.approx(90.0, rel=1e-4)

    def test_achat_prix_zero_retourne_zero(self):
        """Quantité nulle → aucune position (cas de reset)."""
        qty, cump = calculer_cump(0, 0, 0, 100)
        assert qty  == pytest.approx(0.0)
        assert cump == pytest.approx(0.0)

    def test_frais_eleves_impactent_cump(self):
        """Des frais élevés augmentent significativement le CUMP."""
        _, cump_sans = calculer_cump(0, 0, 1, 1000, frais=0)
        _, cump_avec = calculer_cump(0, 0, 1, 1000, frais=10)
        assert cump_avec > cump_sans
        assert cump_avec == pytest.approx(1010.0, rel=1e-4)

    def test_achat_fractionne_crypto(self):
        """Achat de 0.001 BTC — les quantités fractionnaires fonctionnent."""
        qty, cump = calculer_cump(0, 0, 0.001, 70000)
        assert qty  == pytest.approx(0.001, rel=1e-6)
        assert cump == pytest.approx(70000.0)


# ===========================================================================
# TestCalculerPNL — formule pure P&L
# ===========================================================================

class TestCalculerPNL:

    def test_gain_simple(self):
        """P&L = (110 - 100) × 10 = 100€ brut, 100€ net (sans frais)."""
        r = calculer_pnl(prix_vente=110, prix_moyen=100, quantite=10)
        assert r["pnl_brut"] == pytest.approx(100.0)
        assert r["pnl_net"]  == pytest.approx(100.0)
        assert r["pnl_pct"]  == pytest.approx(10.0)

    def test_frais_reduisent_pnl_net(self):
        """P&L brut = 100€, frais = 1€ → P&L net = 99€."""
        r = calculer_pnl(prix_vente=110, prix_moyen=100, quantite=10, frais=1.0)
        assert r["pnl_brut"] == pytest.approx(100.0)
        assert r["pnl_net"]  == pytest.approx(99.0)
        assert r["pnl_pct"]  == pytest.approx(9.9)

    def test_perte(self):
        """Vente en dessous du CUMP → P&L négatif."""
        r = calculer_pnl(prix_vente=80, prix_moyen=100, quantite=10)
        assert r["pnl_brut"] == pytest.approx(-200.0)
        assert r["pnl_net"]  == pytest.approx(-200.0)
        assert r["pnl_pct"]  < 0

    def test_pnl_pct_coherent_avec_pnl_net(self):
        """pnl_pct = pnl_net / (prix_moyen × qty) × 100."""
        r = calculer_pnl(prix_vente=150, prix_moyen=100, quantite=5, frais=2)
        attendu = r["pnl_net"] / (100 * 5) * 100
        assert r["pnl_pct"] == pytest.approx(attendu, rel=1e-4)

    def test_vente_au_cump_pnl_zero_avant_frais(self):
        """Vente exactement au CUMP → P&L brut = 0."""
        r = calculer_pnl(prix_vente=100, prix_moyen=100, quantite=10)
        assert r["pnl_brut"] == pytest.approx(0.0)

    def test_vente_au_cump_pnl_net_negatif_si_frais(self):
        """Vente au CUMP avec frais → P&L net légèrement négatif (les frais pèsent)."""
        r = calculer_pnl(prix_vente=100, prix_moyen=100, quantite=10, frais=1.0)
        assert r["pnl_net"] == pytest.approx(-1.0)

    def test_prix_moyen_zero_retourne_pct_zero(self):
        """Prix moyen nul (cas de données corrompues) → pct = 0 sans division par zéro."""
        r = calculer_pnl(prix_vente=100, prix_moyen=0, quantite=10)
        assert r["pnl_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fixture : rédirige PORTFOLIO_PATH vers un fichier temporaire pour chaque test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def portfolio_tmp(tmp_path, monkeypatch):
    """Chaque test démarre avec un portefeuille vide et isolé."""
    monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", tmp_path / "portfolio.json")


# ===========================================================================
# TestAchat — enregistrement d'achats et calcul CUMP
# ===========================================================================

class TestAchat:

    def test_premier_achat_quantite_et_prix_corrects(self):
        """Un premier achat crée une position avec la quantité et le prix exacts."""
        pos = portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        assert pos["quantite"] == 10.0
        assert pos["prix_moyen"] == pytest.approx(100.0)

    def test_premier_achat_avec_frais_integres_dans_cump(self):
        """Les frais d'achat augmentent le CUMP : (10×100 + 1) / 10 = 100.10."""
        pos = portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0, frais=1.0)
        assert pos["prix_moyen"] == pytest.approx(100.10, rel=1e-4)

    def test_deuxieme_achat_recalcule_cump(self):
        """Le CUMP est correctement recalculé après un second achat.

        Achat 1 : 10 @ 100  → base = 1 000
        Achat 2 : 20 @ 120  → base = 2 400
        CUMP    : 3 400 / 30 = 113.333…
        """
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        pos = portfolio.ajouter_achat("AAPL", prix=120.0, quantite=20.0)
        assert pos["quantite"] == pytest.approx(30.0)
        assert pos["prix_moyen"] == pytest.approx(113.333, rel=1e-3)

    def test_cump_ne_change_pas_apres_vente(self):
        """Le CUMP ne doit PAS être modifié après une vente partielle."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        cump_avant = portfolio.lister_positions()[0]["prix_moyen"]
        portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=5.0)
        cump_apres = portfolio.lister_positions()[0]["prix_moyen"]
        assert cump_avant == pytest.approx(cump_apres)

    def test_achat_apres_vente_partielle_recalcule_cump(self):
        """Un achat après vente partielle recalcule le CUMP sur les unités restantes.

        Achat : 10 @ 100 → CUMP = 100
        Vente : 5 @ 110  → reste 5 @ CUMP 100
        Achat : 5 @ 80   → CUMP = (5×100 + 5×80) / 10 = 90
        """
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=5.0)
        pos = portfolio.ajouter_achat("AAPL", prix=80.0, quantite=5.0)
        assert pos["prix_moyen"] == pytest.approx(90.0, rel=1e-4)

    def test_transaction_achat_enregistree_dans_journal(self):
        """L'achat apparaît dans le journal des transactions."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0, notes="test")
        txs = portfolio.lister_transactions("AAPL")
        assert len(txs) == 1
        assert txs[0]["type"] == "achat"
        assert txs[0]["prix"] == pytest.approx(100.0)
        assert txs[0]["quantite"] == pytest.approx(10.0)
        assert txs[0]["notes"] == "test"

    def test_frais_achat_stockes_dans_transaction(self):
        """Les frais sont bien conservés dans la transaction."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0, frais=1.5)
        txs = portfolio.lister_transactions("AAPL")
        assert txs[0]["frais"] == pytest.approx(1.5)


# ===========================================================================
# TestVente — ventes partielles, totales, P&L et erreurs
# ===========================================================================

class TestVente:

    def test_vente_totale_solde_la_position(self):
        """Après vente totale, la quantité passe à 0."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0)
        positions = portfolio.lister_positions()
        assert len(positions) == 0   # plus aucune position active

    def test_vente_partielle_reduit_quantite(self):
        """Une vente partielle réduit la quantité sans clore la position."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=3.0)
        pos = portfolio.lister_positions()[0]
        assert pos["quantite"] == pytest.approx(7.0)

    def test_pnl_brut_calcule_correctement(self):
        """P&L brut = (prix_vente − CUMP) × quantité."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        trade = portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0)
        # P&L brut = (120 - 100) × 10 = 200
        assert trade["pnl_brut"] == pytest.approx(200.0)

    def test_pnl_net_deduit_frais_vente(self):
        """P&L net = P&L brut − frais de vente."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        trade = portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0, frais=1.0)
        # P&L net = 200 - 1 = 199
        assert trade["pnl_eur"] == pytest.approx(199.0)

    def test_pnl_negatif_si_vente_sous_cump(self):
        """P&L négatif si on vend en dessous du CUMP."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        trade = portfolio.ajouter_vente("AAPL", prix_vente=80.0, quantite=10.0)
        assert trade["pnl_eur"] < 0

    def test_vente_superieure_a_la_quantite_leve_erreur(self):
        """Vendre plus que ce qu'on possède doit lever ValueError."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=5.0)
        with pytest.raises(ValueError, match="Quantité insuffisante"):
            portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=10.0)

    def test_vente_sans_position_leve_erreur(self):
        """Vendre un ticker sans position ouverte doit lever ValueError."""
        with pytest.raises(ValueError, match="Aucune position ouverte"):
            portfolio.ajouter_vente("MSFT", prix_vente=200.0, quantite=1.0)

    def test_vente_enregistree_dans_historique(self):
        """La vente apparaît dans l'historique global."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0)
        hist = portfolio.lister_historique()
        assert len(hist) == 1
        assert hist[0]["ticker"] == "AAPL"

    def test_vente_enregistree_dans_journal_transactions(self):
        """La vente apparaît aussi dans le journal des transactions du ticker."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=5.0)
        txs = portfolio.lister_transactions("AAPL")
        types = [t["type"] for t in txs]
        assert "achat" in types
        assert "vente" in types


# ===========================================================================
# TestScenarioComplet — le scénario décrit par l'utilisateur
# ===========================================================================

class TestScenarioComplet:

    def test_scenario_10_20_moins15_7_moins20_reste_2(self):
        """
        Scénario complet :
          Achat  10 @ 100  → CUMP = 100,      total = 10
          Achat  20 @ 120  → CUMP = 113.33…,  total = 30
          Vente  15        → CUMP inchangé,    total = 15
          Achat   7 @ 110  → CUMP recalculé,   total = 22
          Vente  20        → total = 2 restant
        """
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_achat("AAPL", prix=120.0, quantite=20.0)
        cump_apres_2_achats = portfolio.lister_positions()[0]["prix_moyen"]
        assert cump_apres_2_achats == pytest.approx(113.333, rel=1e-3)

        portfolio.ajouter_vente("AAPL", prix_vente=115.0, quantite=15.0)
        pos = portfolio.lister_positions()[0]
        assert pos["quantite"] == pytest.approx(15.0)
        assert pos["prix_moyen"] == pytest.approx(113.333, rel=1e-3)  # CUMP inchangé

        portfolio.ajouter_achat("AAPL", prix=110.0, quantite=7.0)
        pos = portfolio.lister_positions()[0]
        assert pos["quantite"] == pytest.approx(22.0)
        # CUMP = (15×113.333 + 7×110) / 22 ≈ 112.272…
        assert pos["prix_moyen"] == pytest.approx(112.272, rel=1e-3)

        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=20.0)
        pos = portfolio.lister_positions()[0]
        assert pos["quantite"] == pytest.approx(2.0)

    def test_historique_contient_deux_ventes(self):
        """Le scénario génère bien 2 entrées dans l'historique."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_achat("AAPL", prix=120.0, quantite=20.0)
        portfolio.ajouter_vente("AAPL", prix_vente=115.0, quantite=15.0)
        portfolio.ajouter_achat("AAPL", prix=110.0, quantite=7.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=20.0)
        assert len(portfolio.lister_historique()) == 2

    def test_journal_contient_cinq_transactions(self):
        """Le journal du ticker enregistre les 5 opérations (3 achats + 2 ventes)."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_achat("AAPL", prix=120.0, quantite=20.0)
        portfolio.ajouter_vente("AAPL", prix_vente=115.0, quantite=15.0)
        portfolio.ajouter_achat("AAPL", prix=110.0, quantite=7.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=20.0)
        txs = portfolio.lister_transactions("AAPL")
        assert len(txs) == 5


# ===========================================================================
# TestHistorique — gestion de l'historique des ventes
# ===========================================================================

class TestHistorique:

    def test_supprimer_vente_retire_entree(self):
        """supprimer_vente() retire la vente de l'historique."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        trade = portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0)
        assert len(portfolio.lister_historique()) == 1
        portfolio.supprimer_vente(trade["id"])
        assert len(portfolio.lister_historique()) == 0

    def test_supprimer_vente_id_inexistant_retourne_false(self):
        """Supprimer un ID inexistant retourne False sans erreur."""
        resultat = portfolio.supprimer_vente("id-inexistant-xyz")
        assert resultat is False

    def test_supprimer_vente_ne_restaure_pas_la_position(self):
        """La suppression d'une vente dans l'historique N'affecte PAS les positions."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        trade = portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=10.0)
        # La position est soldée
        assert len(portfolio.lister_positions()) == 0
        portfolio.supprimer_vente(trade["id"])
        # La suppression de l'historique ne restaure pas la position
        assert len(portfolio.lister_positions()) == 0

    def test_historique_trie_plus_recent_en_premier(self):
        """L'historique est trié du plus récent au plus ancien."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=5.0, date="2026-01-01")
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=5.0, date="2026-06-01")
        hist = portfolio.lister_historique()
        assert hist[0]["date"] >= hist[1]["date"]

    def test_supprimer_une_vente_parmi_plusieurs(self):
        """Supprimer une vente n'affecte pas les autres entrées de l'historique."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=20.0)
        t1 = portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=5.0)
        t2 = portfolio.ajouter_vente("AAPL", prix_vente=115.0, quantite=5.0)
        portfolio.supprimer_vente(t1["id"])
        hist = portfolio.lister_historique()
        assert len(hist) == 1
        assert hist[0]["id"] == t2["id"]


# ===========================================================================
# TestPositions — gestion des positions ouvertes
# ===========================================================================

class TestPositions:

    def test_supprimer_position_retire_entierement(self):
        """supprimer_position() efface la position et ses transactions."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.supprimer_position("AAPL")
        assert len(portfolio.lister_positions()) == 0

    def test_supprimer_position_ne_touche_pas_historique(self):
        """La suppression d'une position n'efface pas l'historique des ventes."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=120.0, quantite=5.0)
        portfolio.supprimer_position("AAPL")
        assert len(portfolio.lister_historique()) == 1

    def test_plusieurs_tickers_independants(self):
        """Deux tickers ont des positions indépendantes."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=5.0)
        portfolio.ajouter_achat("MSFT", prix=200.0, quantite=3.0)
        positions = portfolio.lister_positions()
        tickers = {p["ticker"] for p in positions}
        assert "AAPL" in tickers
        assert "MSFT" in tickers
        assert len(positions) == 2

    def test_ticker_majuscule_normalise(self):
        """Le ticker est normalisé en majuscules."""
        portfolio.ajouter_achat("aapl", prix=100.0, quantite=5.0)
        pos = portfolio.lister_positions()[0]
        assert pos["ticker"] == "AAPL"

    def test_lister_positions_exclut_positions_soldees(self):
        """lister_positions() n'inclut pas les positions avec quantité = 0."""
        portfolio.ajouter_achat("AAPL", prix=100.0, quantite=10.0)
        portfolio.ajouter_vente("AAPL", prix_vente=110.0, quantite=10.0)
        assert len(portfolio.lister_positions()) == 0


# ===========================================================================
# TestMigration — compatibilité avec l'ancien format JSON
# ===========================================================================

class TestMigration:

    def test_migration_ancien_format_liste(self, tmp_path, monkeypatch):
        """L'ancien format (positions = liste) est migré automatiquement."""
        import json
        chemin = tmp_path / "portfolio.json"
        ancien = {
            "positions": [
                {"ticker": "AAPL", "prix_achat": 100.0, "quantite": 5.0,
                 "date_achat": "2025-01-01", "notes": "ancien achat"}
            ],
            "historique": [],
        }
        chemin.write_text(json.dumps(ancien), encoding="utf-8")
        monkeypatch.setattr(portfolio, "PORTFOLIO_PATH", chemin)

        positions = portfolio.lister_positions()
        assert len(positions) == 1
        assert positions[0]["ticker"] == "AAPL"
        assert positions[0]["quantite"] == pytest.approx(5.0)
        assert positions[0]["prix_moyen"] == pytest.approx(100.0)
