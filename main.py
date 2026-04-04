import argparse
from datetime import datetime
from orchestrator.orchestrator import run
from backtesting.backtest import run_backtest


def sauvegarder_rapport(ticker: str, resultat: dict, backtest: dict = None) -> str:
    date = datetime.now().strftime("%Y%m%d_%H%M%S")
    chemin = f"output/rapport_{ticker}_{date}.txt"
    scoring = resultat["scoring"]

    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"RAPPORT D'ANALYSE — {ticker}\n")
        f.write(f"Généré le : {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        f.write("=" * 60 + "\n\n")

        f.write("SCORING PONDÉRÉ\n")
        f.write("-" * 60 + "\n")
        f.write(f"Technique    : {scoring['scores']['technique']} × {scoring['poids']['technique']}\n")
        f.write(f"Fondamental  : {scoring['scores']['fondamental']} × {scoring['poids']['fondamental']}\n")
        f.write(f"Sentiment    : {scoring['scores']['sentiment']} × {scoring['poids']['sentiment']}\n")
        f.write(f"Multiplicateur risque : {scoring['scores']['multiplicateur']}\n")
        f.write(f"Score final  : {scoring['score_final']}\n")
        f.write(f"Décision     : {scoring['decision']}\n\n")

        f.write("RAPPORT LLM\n")
        f.write("-" * 60 + "\n")
        f.write(resultat["rapport"] + "\n\n")

        if backtest:
            f.write("BACKTEST\n")
            f.write("-" * 60 + "\n")
            f.write(f"Période       : {backtest['debut']} → {backtest['fin']}\n")
            f.write(f"Capital départ: {backtest['capital']:,} $\n")
            f.write(f"Capital final : {backtest['valeur_fin']:,} $\n")
            f.write(f"Rendement     : {backtest['rendement']} %\n")

    return chemin


def main():
    parser = argparse.ArgumentParser(
        description="Système multi-agents d'aide à la décision financière"
    )
    parser.add_argument("ticker", type=str, help="Symbole boursier (ex: AAPL)")
    parser.add_argument("--period", type=str, default="3mo")
    parser.add_argument("--backtest", action="store_true")

    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  ANALYSE : {args.ticker.upper()}")
    print(f"{'=' * 60}\n")

    resultat = run(args.ticker)
    scoring  = resultat["scoring"]

    print(resultat["rapport"])
    print(f"\nScore final : {scoring['score_final']} / 1.0")
    print(f"Décision    : {scoring['decision']}")

    backtest = None
    if args.backtest:
        print(f"\n{'=' * 60}")
        print(f"  BACKTEST : {args.ticker.upper()}")
        print(f"{'=' * 60}\n")
        backtest = run_backtest(args.ticker)
        print(f"Capital départ : {backtest['capital']:,} $")
        print(f"Capital final  : {backtest['valeur_fin']:,} $")
        print(f"Rendement      : {backtest['rendement']} %")

    chemin = sauvegarder_rapport(args.ticker, resultat, backtest)
    print(f"\nRapport sauvegardé : {chemin}")


if __name__ == "__main__":
    main()