"""
Tests unitaires — data/fees_tax.py
Vérifie le calcul des frais broker et de la fiscalité française sur les plus-values.
"""

import pytest
from data.fees_tax import calculer_frais, calculer_impots


# ===========================================================================
# TestFraisBroker — types fixe, pct, mixte
# ===========================================================================

class TestFraisBroker:

    # --- Frais fixes (Trade Republic : 1 € quel que soit le montant) ---

    def test_frais_fixe_achat_independant_du_montant(self):
        """Trade Republic : toujours 1 € peu importe le montant."""
        broker = {"type_frais": "fixe", "frais_achat": 1.0, "frais_vente": 1.0}
        assert calculer_frais(100.0,   broker, "achat") == pytest.approx(1.0)
        assert calculer_frais(10000.0, broker, "achat") == pytest.approx(1.0)

    def test_frais_fixe_vente_independant_du_montant(self):
        broker = {"type_frais": "fixe", "frais_achat": 1.0, "frais_vente": 1.0}
        assert calculer_frais(500.0, broker, "vente") == pytest.approx(1.0)

    def test_frais_fixe_zero(self):
        """Revolut Premium : 0 € de frais."""
        broker = {"type_frais": "fixe", "frais_achat": 0.0, "frais_vente": 0.0}
        assert calculer_frais(1000.0, broker, "achat") == pytest.approx(0.0)

    # --- Frais en pourcentage (Boursorama : 0.10% min 0.99 €) ---

    def test_frais_pct_montant_eleve_depasse_minimum(self):
        """Sur 2 000 € à 0.10% : frais = 2 €, supérieur au min 0.99 €."""
        broker = {"type_frais": "pct", "taux_pct": 0.10, "frais_min": 0.99}
        frais = calculer_frais(2000.0, broker, "achat")
        assert frais == pytest.approx(2.0, rel=1e-3)

    def test_frais_pct_petit_montant_applique_minimum(self):
        """Sur 500 € à 0.10% : frais calculés = 0.50 €, mais minimum = 0.99 €."""
        broker = {"type_frais": "pct", "taux_pct": 0.10, "frais_min": 0.99}
        frais = calculer_frais(500.0, broker, "achat")
        assert frais == pytest.approx(0.99)

    def test_frais_pct_sans_minimum(self):
        """0.05% sur 1 000 € sans minimum = 0.50 €."""
        broker = {"type_frais": "pct", "taux_pct": 0.05, "frais_min": 0.0}
        frais = calculer_frais(1000.0, broker, "achat")
        assert frais == pytest.approx(0.50)

    # --- Frais mixtes (DEGIRO : fixe + pourcentage) ---

    def test_frais_mixte_combine_fixe_et_pct(self):
        """DEGIRO : 0.50 € + 0.022% sur 1 000 € = 0.50 + 0.22 = 0.72 €."""
        broker = {"type_frais": "mixte", "frais_achat": 0.50, "taux_pct": 0.022}
        frais = calculer_frais(1000.0, broker, "achat")
        assert frais == pytest.approx(0.72, rel=1e-3)

    def test_frais_mixte_sur_petit_montant(self):
        """DEGIRO : 0.50 € + 0.022% sur 100 € = 0.50 + 0.022 = 0.522 €."""
        broker = {"type_frais": "mixte", "frais_achat": 0.50, "taux_pct": 0.022}
        frais = calculer_frais(100.0, broker, "achat")
        assert frais == pytest.approx(0.522, rel=1e-3)

    # --- Type inconnu → 0 par défaut ---

    def test_type_inconnu_retourne_zero(self):
        broker = {"type_frais": "inconnu"}
        assert calculer_frais(1000.0, broker, "achat") == pytest.approx(0.0)


# ===========================================================================
# TestFiscalite — calcul d'impôt sur plus-values
# ===========================================================================

class TestFiscalite:

    # --- PFU 30% (flat tax) ---

    def test_pfu_30_pct_sur_gain_positif(self):
        """PFU : 30% d'impôt sur un gain de 1 000 € = 300 €."""
        r = calculer_impots(1000.0, "pfu")
        assert r["impots"] == pytest.approx(300.0)
        assert r["pnl_apres_impots"] == pytest.approx(700.0)
        assert r["taux_effectif"] == pytest.approx(30.0)

    def test_pfu_pas_impot_sur_perte(self):
        """Pas d'impôt si P&L négatif."""
        r = calculer_impots(-500.0, "pfu")
        assert r["impots"] == pytest.approx(0.0)
        assert r["pnl_apres_impots"] == pytest.approx(-500.0)

    def test_pfu_pas_impot_si_pnl_zero(self):
        """Pas d'impôt si P&L nul."""
        r = calculer_impots(0.0, "pfu")
        assert r["impots"] == pytest.approx(0.0)

    # --- Barème progressif ---

    def test_bareme_tmi_30_taux_effectif_47_2(self):
        """Barème TMI 30% : taux = 30% IR + 17.2% PS = 47.2%."""
        r = calculer_impots(1000.0, "bareme", tmi=30)
        assert r["taux_effectif"] == pytest.approx(47.2, rel=1e-2)
        assert r["impots"] == pytest.approx(472.0, rel=1e-2)

    def test_bareme_tmi_0_taux_effectif_17_2(self):
        """Barème TMI 0% : seulement les 17.2% de prélèvements sociaux."""
        r = calculer_impots(1000.0, "bareme", tmi=0)
        assert r["taux_effectif"] == pytest.approx(17.2, rel=1e-2)

    def test_bareme_tmi_11(self):
        """Barème TMI 11% : taux = 11% + 17.2% = 28.2%."""
        r = calculer_impots(1000.0, "bareme", tmi=11)
        assert r["taux_effectif"] == pytest.approx(28.2, rel=1e-2)

    def test_bareme_tmi_45_taux_effectif_62_2(self):
        """Barème TMI 45% : taux = 45% + 17.2% = 62.2%."""
        r = calculer_impots(1000.0, "bareme", tmi=45)
        assert r["taux_effectif"] == pytest.approx(62.2, rel=1e-2)

    # --- PEA (17.2% PS après 5 ans) ---

    def test_pea_17_2_pct_uniquement(self):
        """PEA après 5 ans : seulement 17.2% de prélèvements sociaux."""
        r = calculer_impots(1000.0, "pea")
        assert r["taux_effectif"] == pytest.approx(17.2)
        assert r["impots"] == pytest.approx(172.0)
        assert r["pnl_apres_impots"] == pytest.approx(828.0)

    def test_pea_moins_impot_que_pfu(self):
        """PEA toujours moins taxé que PFU (pour gains positifs)."""
        r_pea = calculer_impots(1000.0, "pea")
        r_pfu = calculer_impots(1000.0, "pfu")
        assert r_pea["impots"] < r_pfu["impots"]

    # --- Structure du retour ---

    def test_structure_retour_contient_les_trois_cles(self):
        r = calculer_impots(500.0, "pfu")
        assert "impots" in r
        assert "pnl_apres_impots" in r
        assert "taux_effectif" in r
