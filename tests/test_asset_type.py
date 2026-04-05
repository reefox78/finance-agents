"""
Tests unitaires — data/asset_type.py
Vérifie la détection automatique du type d'actif à partir du symbole ticker.
"""

import pytest
from data.asset_type import detect_asset_type


# ===========================================================================
# TestActionsUS
# ===========================================================================

class TestActionsUS:

    def test_aapl_est_us_stock(self):
        assert detect_asset_type("AAPL") == "us_stock"

    def test_msft_est_us_stock(self):
        assert detect_asset_type("MSFT") == "us_stock"

    def test_spy_etf_est_us_stock(self):
        assert detect_asset_type("SPY") == "us_stock"

    def test_ticker_minuscule_est_us_stock(self):
        """La détection fonctionne même si le ticker est en minuscules."""
        assert detect_asset_type("aapl") == "us_stock"


# ===========================================================================
# TestActionsEuropeennes
# ===========================================================================

class TestActionsEuropeennes:

    def test_mc_pa_est_eu_stock(self):
        assert detect_asset_type("MC.PA") == "eu_stock"

    def test_sap_de_est_eu_stock(self):
        assert detect_asset_type("SAP.DE") == "eu_stock"

    def test_asml_as_est_eu_stock(self):
        assert detect_asset_type("ASML.AS") == "eu_stock"

    def test_action_londonienne_est_eu_stock(self):
        assert detect_asset_type("SHEL.L") == "eu_stock"

    def test_action_suisse_est_eu_stock(self):
        assert detect_asset_type("NESN.SW") == "eu_stock"


# ===========================================================================
# TestCrypto
# ===========================================================================

class TestCrypto:

    def test_btc_usd_est_crypto(self):
        assert detect_asset_type("BTC-USD") == "crypto"

    def test_eth_usd_est_crypto(self):
        assert detect_asset_type("ETH-USD") == "crypto"

    def test_sol_usd_est_crypto(self):
        assert detect_asset_type("SOL-USD") == "crypto"

    def test_doge_usd_est_crypto(self):
        assert detect_asset_type("DOGE-USD") == "crypto"


# ===========================================================================
# TestForex
# ===========================================================================

class TestForex:

    def test_eurusd_est_forex(self):
        assert detect_asset_type("EURUSD=X") == "forex"

    def test_gbpusd_est_forex(self):
        assert detect_asset_type("GBPUSD=X") == "forex"

    def test_usdjpy_est_forex(self):
        assert detect_asset_type("USDJPY=X") == "forex"

    def test_usdchf_est_forex(self):
        assert detect_asset_type("USDCHF=X") == "forex"


# ===========================================================================
# TestCasBordure
# ===========================================================================

class TestCasBordure:

    def test_ticker_vide_retourne_us_stock_par_defaut(self):
        """Un ticker vide ne doit pas crasher."""
        result = detect_asset_type("")
        assert result in ("us_stock", "eu_stock", "crypto", "forex")

    def test_ticker_inconnu_retourne_us_stock(self):
        """Un ticker totalement inconnu est traité comme us_stock (fallback)."""
        assert detect_asset_type("XYZABC123") == "us_stock"
