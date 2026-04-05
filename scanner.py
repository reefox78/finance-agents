"""
Scanner multi-tickers.

Usage:
    python scanner.py                          # scan complet de la watchlist
    python scanner.py --categorie us_stocks    # une seule catégorie
    python scanner.py --tickers AAPL MSFT NVDA # tickers manuels
    python scanner.py --min-score 0.10         # filtrer par score minimum
"""

import argparse
import csv
import json
import sys
import io
from datetime import datetime
from pathlib import Path

# Encodage UTF-8 pour le terminal Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from orchestrator.orchestrator import run

WATCHLIST_PATH = Path("config/watchlist.json")
OUTPUT_DIR     = Path("output")

# Largeurs des colonnes pour l'affichage
COL = {"ticker": 10, "type": 10, "decision": 9, "score": 8,
       "tech": 7, "risque": 7, "sent": 7, "macro": 7, "insider": 8}

# Couleurs ANSI (désactivées si terminal ne supporte pas)
VERT   = "\033[92m"
ROUGE  = "\033[91m"
JAUNE  = "\033[93m"
RESET  = "\033[0m"


def _couleur_decision(decision: str) -> str:
    if decision == "ACHETER": return f"{VERT}{decision}{RESET}"
    if decision == "VENDRE":  return f"{ROUGE}{decision}{RESET}"
    return decision


def _couleur_score(score: float) -> str:
    s = f"{score:+.4f}"
    if score >= 0.10:  return f"{VERT}{s}{RESET}"
    if score <= -0.10: return f"{ROUGE}{s}{RESET}"
    return f"{JAUNE}{s}{RESET}"


def _charger_watchlist(categorie: str = None) -> list[str]:
    """Charge les tickers depuis config/watchlist.json."""
    with open(WATCHLIST_PATH, encoding="utf-8") as f:
        data = json.load(f)

    if categorie:
        if categorie not in data:
            print(f"Categorie inconnue : {categorie}. Disponibles : {list(data.keys())}")
            sys.exit(1)
        return data[categorie]

    # Toutes les catégories
    tickers = []
    for v in data.values():
        tickers.extend(v)
    return tickers


def _analyser_ticker(ticker: str) -> dict | None:
    """Lance l'analyse sans LLM et retourne un dict résumé, ou None si erreur."""
    try:
        r = run(ticker, with_llm=False)
        s = r["scoring"]

        s_tech   = r["tech"].get("score_final", 0.0)
        risque   = r["risk"]["risque"] if r["risk"] else "N/A"
        signal_s = r["sent"]["signal"] if r["sent"] else "N/A"
        s_macro  = r["macro"]["score_final"] if r["macro"] else None
        signal_i = r["insider"]["signal"] if r["insider"] else "N/A"

        # Nouveaux agents (signal abrege : A/N/V ou -)
        def _sig(agent): return agent["signal"][0] if agent else "-"
        sig_opts = _sig(r.get("options_flow"))
        sig_sec  = _sig(r.get("sec_filings"))
        sig_si   = _sig(r.get("short_interest"))
        sig_eps  = _sig(r.get("earnings_surprise"))

        return {
            "ticker":   ticker,
            "type":     r["asset_type"],
            "decision": s["decision"],
            "score":    s["score_final"],
            "tech":     round(s_tech, 4),
            "risque":   risque,
            "sent":     signal_s,
            "macro":    round(s_macro, 4) if s_macro is not None else "N/A",
            "insider":  signal_i,
            "opts":     sig_opts,
            "sec":      sig_sec,
            "si":       sig_si,
            "eps":      sig_eps,
        }
    except Exception as e:
        print(f"  [ERREUR] {ticker} : {e}")
        return None


def _afficher_tableau(resultats: list[dict]) -> None:
    """Affiche le tableau de résultats trié par score décroissant."""
    if not resultats:
        print("Aucun résultat.")
        return

    # Tri : ACHETER en premier, VENDRE en dernier, par score décroissant
    tries = sorted(resultats, key=lambda x: x["score"], reverse=True)

    sep    = "-" * 100
    entete = (f"{'TICKER':<10} {'TYPE':<10} {'DECISION':<9} {'SCORE':>8}  "
              f"{'TECH':>7}  {'RISQUE':<7}  {'SENT':<7}  {'MACRO':>7}  "
              f"{'INSID':<5}  {'OPTS':<4}  {'SEC':<4}  {'SI':<4}  {'EPS':<4}")

    print(f"\n{sep}")
    print(entete)
    print(sep)

    for r in tries:
        macro_str = str(r["macro"]) if r["macro"] != "N/A" else " N/A"
        ligne = (f"{r['ticker']:<10} {r['type']:<10} "
                 f"{r['decision']:<9} {r['score']:>+8.4f}  "
                 f"{r['tech']:>+7.4f}  {r['risque']:<7}  "
                 f"{r['sent']:<7}  {macro_str:>7}  "
                 f"{r['insider'][0]:<5}  {r['opts']:<4}  {r['sec']:<4}  {r['si']:<4}  {r['eps']:<4}")
        if r["decision"] == "ACHETER":
            print(f"{VERT}{ligne}{RESET}")
        elif r["decision"] == "VENDRE":
            print(f"{ROUGE}{ligne}{RESET}")
        else:
            print(ligne)

    print(sep)

    acheter = sum(1 for r in tries if r["decision"] == "ACHETER")
    neutre  = sum(1 for r in tries if r["decision"] == "NEUTRE")
    vendre  = sum(1 for r in tries if r["decision"] == "VENDRE")
    print(f"Signaux : {VERT}ACHETER {acheter}{RESET}  |  NEUTRE {neutre}  |  {ROUGE}VENDRE {vendre}{RESET}")


def _sauvegarder_csv(resultats: list[dict]) -> str:
    """Sauvegarde les résultats dans output/scan_YYYYMMDD_HHMMSS.csv."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin   = OUTPUT_DIR / f"scan_{date_str}.csv"

    champs = ["ticker", "type", "decision", "score", "tech",
              "risque", "sent", "macro", "insider",
              "opts", "sec", "si", "eps", "date"]

    with open(chemin, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=champs)
        writer.writeheader()
        for r in resultats:
            writer.writerow({**r, "date": datetime.now().strftime("%Y-%m-%d %H:%M")})

    return str(chemin)


def main():
    parser = argparse.ArgumentParser(description="Scanner multi-tickers finance-agents")
    parser.add_argument("--categorie", type=str, default=None,
                        help="Catégorie watchlist : us_stocks, eu_stocks, crypto, forex")
    parser.add_argument("--tickers", nargs="+", default=None,
                        help="Liste de tickers manuels (ex: AAPL MSFT NVDA)")
    parser.add_argument("--min-score", type=float, default=None,
                        help="Afficher uniquement les tickers avec score >= min-score")
    args = parser.parse_args()

    # --- Sélection des tickers ---
    if args.tickers:
        tickers = args.tickers
    else:
        tickers = _charger_watchlist(args.categorie)

    date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    print(f"\n{'='*60}")
    print(f"  SCAN DE MARCHE — {date_str}")
    print(f"  {len(tickers)} tickers a analyser")
    print(f"{'='*60}\n")

    # --- Analyse de chaque ticker ---
    resultats = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] ", end="", flush=True)
        r = _analyser_ticker(ticker)
        if r:
            resultats.append(r)

    # --- Filtrage optionnel ---
    if args.min_score is not None:
        resultats = [r for r in resultats if r["score"] >= args.min_score]

    # --- Affichage ---
    _afficher_tableau(resultats)

    # --- Sauvegarde CSV ---
    if resultats:
        chemin = _sauvegarder_csv(resultats)
        print(f"\nSauvegarde : {chemin}")


if __name__ == "__main__":
    main()
