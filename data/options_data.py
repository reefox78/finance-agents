"""
Données de flux options via yfinance.
Disponible pour les actions US uniquement.
"""

import yfinance as yf
import pandas as pd
from data.market_data import get_ticker_raw_info


def get_options_flow(ticker: str, nb_expirations: int = 2) -> dict:
    """
    Analyse les chaînes d'options pour détecter :
    - Le ratio put/call (sentiment directionnel)
    - L'activité anormale (volume >> open interest)
    - Le skew IV (prime de risque baissier vs haussier)

    Retourne un dict avec les métriques brutes.
    Le prix spot est récupéré via le cache centralisé (TTL 30 min).
    Les chaînes d'options sont dynamiques : toujours fraîches.
    """
    try:
        stock = yf.Ticker(ticker)
        expirations = stock.options

        if not expirations:
            return {"disponible": False, "raison": "Pas d'options listées"}

        # Prix spot depuis cache centralisé
        try:
            raw_info    = get_ticker_raw_info(ticker)
            current_price = raw_info.get("regularMarketPrice") or raw_info.get("currentPrice")
        except Exception:
            current_price = None

        if not current_price:
            hist = stock.history(period="1d")
            current_price = float(hist["Close"].iloc[-1]) if not hist.empty else None

        total_call_vol = 0
        total_put_vol  = 0
        total_call_oi  = 0
        total_put_oi   = 0
        unusual_calls  = 0
        unusual_puts   = 0

        # IV skew : OTM puts vs OTM calls sur la première expiration
        skew_iv = None

        for i, exp in enumerate(expirations[:nb_expirations]):
            chain = stock.option_chain(exp)
            calls = chain.calls.fillna(0)
            puts  = chain.puts.fillna(0)

            total_call_vol += calls["volume"].sum()
            total_put_vol  += puts["volume"].sum()
            total_call_oi  += calls["openInterest"].sum()
            total_put_oi   += puts["openInterest"].sum()

            # Activité anormale : volume > 5× open interest (et > 100 contrats min)
            oi_min = calls["openInterest"].replace(0, 1)
            unusual_calls += int(((calls["volume"] > 5 * oi_min) & (calls["volume"] > 100)).sum())

            oi_min_p = puts["openInterest"].replace(0, 1)
            unusual_puts  += int(((puts["volume"] > 5 * oi_min_p) & (puts["volume"] > 100)).sum())

            # IV skew sur la première expiration uniquement
            if i == 0 and current_price:
                low_strike  = current_price * 0.95
                high_strike = current_price * 1.05

                otm_puts  = puts[puts["strike"] < low_strike]["impliedVolatility"]
                otm_calls = calls[calls["strike"] > high_strike]["impliedVolatility"]

                if not otm_puts.empty and not otm_calls.empty:
                    skew_iv = round(float(otm_puts.mean()) - float(otm_calls.mean()), 4)

        return {
            "disponible":   True,
            "call_volume":  int(total_call_vol),
            "put_volume":   int(total_put_vol),
            "call_oi":      int(total_call_oi),
            "put_oi":       int(total_put_oi),
            "pc_ratio_vol": round(total_put_vol / total_call_vol, 3) if total_call_vol > 0 else None,
            "pc_ratio_oi":  round(total_put_oi  / total_call_oi,  3) if total_call_oi  > 0 else None,
            "unusual_calls":unusual_calls,
            "unusual_puts": unusual_puts,
            "skew_iv":      skew_iv,
        }

    except Exception as e:
        return {"disponible": False, "raison": str(e)}
