import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta


def get_insider_trading(ticker: str, jours: int = 90) -> dict:
    """
    Récupère les transactions des dirigeants via OpenInsider.
    """
    headers = {"User-Agent": "Mozilla/5.0"}
    url     = f"http://openinsider.com/screener?s={ticker}&fd=90&xp=1&xs=1&action=1"

    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return _resultat_vide(ticker)

        soup   = BeautifulSoup(response.text, "html.parser")
        tables = soup.find_all("table")

        if len(tables) < 12:
            return _resultat_vide(ticker)

        tableau      = tables[11]
        lignes       = tableau.find_all("tr")[1:]
        transactions = []
        date_limite  = datetime.now() - timedelta(days=jours)

        for ligne in lignes:
            try:
                cols = ligne.find_all("td")
                if len(cols) < 12:
                    continue

                date_str    = cols[2].get_text(strip=True)
                nom_insider = cols[4].get_text(strip=True)
                poste       = cols[5].get_text(strip=True)
                type_trade  = cols[6].get_text(strip=True)
                prix        = cols[7].get_text(strip=True).replace("$", "").replace(",", "")
                valeur      = cols[11].get_text(strip=True).replace("$", "").replace(",", "").replace("+", "").replace("-", "")

                if not date_str:
                    continue

                try:
                    date_transaction = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    if date_transaction < date_limite:
                        continue
                except Exception:
                    continue

                if type_trade.startswith("P"):
                    type_t = "ACHAT"
                elif type_trade.startswith("S"):
                    type_t = "VENTE"
                else:
                    continue

                transactions.append({
                    "date":    date_str[:10],
                    "insider": nom_insider,
                    "poste":   poste,
                    "type":    type_t,
                    "prix":    float(prix) if prix else 0.0,
                    "valeur":  float(valeur) if valeur else 0.0,
                })

            except Exception:
                continue

        if not transactions:
            return _resultat_vide(ticker)

        achats      = [t for t in transactions if t["type"] == "ACHAT"]
        ventes      = [t for t in transactions if t["type"] == "VENTE"]
        total_achat = sum(t["valeur"] for t in achats)
        total_vente = sum(t["valeur"] for t in ventes)
        ratio       = total_achat / (total_vente + 1)

        if ratio > 2.0:
            score  = 1.0
            signal = "ACHETER"
        elif ratio > 0.5:
            score  = 0.0
            signal = "NEUTRE"
        else:
            score  = -1.0
            signal = "VENDRE"

        return {
            "ticker":       ticker,
            "transactions": transactions[:10],
            "nb_achats":    len(achats),
            "nb_ventes":    len(ventes),
            "total_achat":  round(total_achat, 0),
            "total_vente":  round(total_vente, 0),
            "ratio":        round(ratio, 4),
            "score_final":  score,
            "signal":       signal,
        }

    except Exception as e:
        print(f"Erreur insider trading : {e}")
        return _resultat_vide(ticker)


def _resultat_vide(ticker: str) -> dict:
    return {
        "ticker":       ticker,
        "transactions": [],
        "nb_achats":    0,
        "nb_ventes":    0,
        "total_achat":  0,
        "total_vente":  0,
        "ratio":        0,
        "score_final":  0.0,
        "signal":       "NEUTRE",
    }


if __name__ == "__main__":
    resultat = get_insider_trading("AAPL")

    print(f"--- Insider Trading : {resultat['ticker']} ---")
    print(f"Nb achats  : {resultat['nb_achats']}")
    print(f"Nb ventes  : {resultat['nb_ventes']}")
    print(f"Total achat: {resultat['total_achat']:,} $")
    print(f"Total vente: {resultat['total_vente']:,} $")
    print(f"Ratio      : {resultat['ratio']}")
    print(f"Score      : {resultat['score_final']}")
    print(f"Signal     : {resultat['signal']}")
    print(f"\nDernières transactions :")
    for t in resultat["transactions"]:
        signe = "🟢" if t["type"] == "ACHAT" else "🔴"
        print(f"  {signe} [{t['date']}] {t['insider']} ({t['poste']}) — {t['valeur']:,} $")