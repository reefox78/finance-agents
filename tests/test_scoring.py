"""
Tests unitaires — orchestrator/scoring.py
Vérifie le calcul du score pondéré, la renormalisation et les décisions.
"""

import pytest
from orchestrator.scoring import calculer_score, signal_en_score, macro_en_multiplicateur, SEUIL_ACHAT, SEUIL_VENTE


# ---------------------------------------------------------------------------
# Helpers pour construire des agents factices
# ---------------------------------------------------------------------------

def tech(score):
    return {"score_final": score, "signal": "NEUTRE"}

def fund(score):
    return {"score_final": score, "signal": "NEUTRE"}

def risk(mult):
    return {"multiplicateur": mult, "risque": "MODERE"}

def sent(signal):
    return {"signal": signal}

def macro(score):
    return {"score_final": score, "signal": "NEUTRE"}

def trends(score):
    return {"score_final": score}

def insider(score):
    return {"score_final": score, "signal": "NEUTRE"}


# ===========================================================================
# TestSignalEnScore — conversion signal texte → float
# ===========================================================================

class TestSignalEnScore:

    def test_acheter_vaut_0_5(self):
        assert signal_en_score("ACHETER") == pytest.approx(0.5)

    def test_vendre_vaut_moins_0_5(self):
        assert signal_en_score("VENDRE") == pytest.approx(-0.5)

    def test_neutre_vaut_0(self):
        assert signal_en_score("NEUTRE") == pytest.approx(0.0)

    def test_signal_inconnu_vaut_0(self):
        assert signal_en_score("INCONNU") == pytest.approx(0.0)


# ===========================================================================
# TestMacroMultiplicateur — transformation score macro → multiplicateur
# ===========================================================================

class TestMacroMultiplicateur:

    def test_macro_tres_positive_donne_110(self):
        assert macro_en_multiplicateur(0.5) == pytest.approx(1.10)

    def test_macro_legerement_positive_donne_100(self):
        assert macro_en_multiplicateur(0.1) == pytest.approx(1.00)

    def test_macro_legerement_negative_donne_090(self):
        assert macro_en_multiplicateur(-0.2) == pytest.approx(0.90)

    def test_macro_tres_negative_donne_075(self):
        assert macro_en_multiplicateur(-0.5) == pytest.approx(0.75)

    def test_frontiere_zero_donne_100(self):
        assert macro_en_multiplicateur(0.0) == pytest.approx(1.00)


# ===========================================================================
# TestDecision — seuils ACHETER / NEUTRE / VENDRE
# ===========================================================================

class TestDecision:

    def test_score_superieur_seuil_achat_donne_ACHETER(self):
        r = calculer_score(tech(1.0))
        assert r["decision"] == "ACHETER"

    def test_score_inferieur_seuil_vente_donne_VENDRE(self):
        r = calculer_score(tech(-1.0))
        assert r["decision"] == "VENDRE"

    def test_score_entre_seuils_donne_NEUTRE(self):
        r = calculer_score(tech(0.0))
        assert r["decision"] == "NEUTRE"

    def test_score_exactement_au_seuil_achat_donne_ACHETER(self):
        # Avec tech uniquement et pas de multiplicateurs : score_final = score_tech
        r = calculer_score(tech(SEUIL_ACHAT))
        assert r["decision"] == "ACHETER"

    def test_score_exactement_au_seuil_vente_donne_VENDRE(self):
        r = calculer_score(tech(SEUIL_VENTE))
        assert r["decision"] == "VENDRE"


# ===========================================================================
# TestRenormalisation — agents absents → poids recalculés
# ===========================================================================

class TestRenormalisation:

    def test_score_avec_technique_seul_non_dilue(self):
        """Avec un seul agent, le score final = score_technique (pas divisé par 1)."""
        r = calculer_score(tech(0.5))
        # Avec technique seul, poids_actifs = 0.25, score_brut = 0.5×0.25 / 0.25 = 0.5
        assert r["score_final"] == pytest.approx(0.5, abs=0.01)

    def test_ajout_fondamental_neutre_ne_change_pas_decision(self):
        """Ajouter un agent fondamental neutre ne doit pas changer une décision ACHETER."""
        sans_fund = calculer_score(tech(0.8))
        avec_fund = calculer_score(tech(0.8), fund=fund(0.0))
        assert sans_fund["decision"] == avec_fund["decision"] == "ACHETER"

    def test_agent_none_ignore_dans_calcul(self):
        """Un agent None ne doit pas impacter le score (poids = 0 pour cet agent)."""
        r_sans = calculer_score(tech(0.5))
        r_avec = calculer_score(tech(0.5), fund=None, sent=None)
        assert r_sans["score_final"] == pytest.approx(r_avec["score_final"])


# ===========================================================================
# TestMultiplicateurs — impact des multiplicateurs risque et macro
# ===========================================================================

class TestMultiplicateurs:

    def test_multiplicateur_risque_eleve_penalise_score(self):
        """Un multiplicateur de risque < 1 doit réduire le score positif."""
        sans = calculer_score(tech(0.5))
        avec = calculer_score(tech(0.5), risk=risk(0.5))
        assert avec["score_final"] < sans["score_final"]

    def test_multiplicateur_macro_negatif_penalise_score(self):
        """Une macro très négative (mult 0.75) réduit le score."""
        sans = calculer_score(tech(0.5))
        avec = calculer_score(tech(0.5), macro=macro(-0.5))
        assert avec["score_final"] < sans["score_final"]

    def test_multiplicateur_macro_positif_booste_score(self):
        """Une macro très positive (mult 1.10) augmente le score."""
        sans = calculer_score(tech(0.5))
        avec = calculer_score(tech(0.5), macro=macro(0.5))
        assert avec["score_final"] > sans["score_final"]

    def test_score_final_borne_entre_moins1_et_1(self):
        """Le score est toujours dans [-1, 1] même avec des valeurs extrêmes."""
        r = calculer_score(tech(1.0), risk=risk(2.0), macro=macro(1.0))
        assert -1.0 <= r["score_final"] <= 1.0


# ===========================================================================
# TestScoreComplet — combinaison de plusieurs agents
# ===========================================================================

class TestScoreComplet:

    def test_tous_agents_positifs_donne_score_positif(self):
        """Tous les agents positifs → score final positif → décision ACHETER."""
        r = calculer_score(
            tech=tech(0.8),
            fund=fund(0.6),
            sent=sent("ACHETER"),
            risk=risk(1.0),
            trends=trends(1.0),
            insider=insider(0.5),
            macro=macro(0.3),
        )
        assert r["score_final"] > 0
        assert r["decision"] == "ACHETER"

    def test_tous_agents_negatifs_donne_score_negatif(self):
        """Tous les agents négatifs → score final négatif → décision VENDRE."""
        r = calculer_score(
            tech=tech(-0.8),
            fund=fund(-0.6),
            sent=sent("VENDRE"),
            risk=risk(1.0),
            macro=macro(-0.5),
        )
        assert r["score_final"] < 0
        assert r["decision"] == "VENDRE"

    def test_structure_retour_complete(self):
        """Le dict retourné contient toutes les clés attendues."""
        r = calculer_score(tech(0.3))
        assert "score_final" in r
        assert "decision" in r
        assert "scores" in r
        assert "poids" in r
        assert "technique" in r["scores"]
        assert "multiplicateur" in r["scores"]
        assert "mult_macro" in r["scores"]
