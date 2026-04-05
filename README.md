# Finance Agents — Aide à la décision financière

Système multi-agents d'analyse boursière avec portefeuille, alertes et backtest.

---

## Démarrage rapide

```bash
# Tout lancer en une commande (dashboard + alertes)
python start.py

# Dashboard uniquement (sans surveillance en arrière-plan)
python start.py --no-alerts

# Changer le port (défaut : 8501)
python start.py --port 8502
```

Le dashboard s'ouvre automatiquement sur **http://localhost:8501**

---

## Commandes individuelles

```bash
# Dashboard seul
streamlit run output/dashboard.py

# Scheduler d'alertes seul (surveillance des positions)
python alerts/scheduler.py

# Scanner en ligne de commande
python scanner.py                           # toute la watchlist
python scanner.py --categorie us_stocks     # une catégorie
python scanner.py --tickers AAPL MSFT NVDA  # tickers manuels
python scanner.py --min-score 0.10          # filtrer par score

# Analyse d'un ticker en ligne de commande
python main.py AAPL
python main.py AAPL --backtest

# Tests unitaires
python -m pytest tests/ -v
```

---

## Structure du projet

```
finance-agents/
├── start.py                  # Démarrage en une commande
├── scanner.py                # Scanner multi-tickers CLI
├── main.py                   # Analyse CLI d'un ticker
│
├── agents/                   # Agents d'analyse
│   ├── technical.py          # Analyse technique (RSI, MACD, Bollinger)
│   ├── fundamental.py        # Analyse fondamentale (PER, dividende)
│   ├── sentiment.py          # Sentiment des news
│   ├── risk.py               # Risque (volatilité, drawdown)
│   ├── macro.py              # Contexte macro (taux, chômage, spread)
│   ├── insider.py            # Transactions des dirigeants
│   ├── trends.py             # Google Trends
│   ├── options_flow.py       # Flux options (P/C ratio, IV skew)
│   ├── sec_filings.py        # Événements réglementaires SEC 8-K
│   ├── short_interest.py     # Intérêt à la vente / short squeeze
│   └── earnings_surprise.py  # Anomalie post-résultats
│
├── orchestrator/
│   ├── orchestrator.py       # Coordination des agents
│   └── scoring.py            # Score pondéré final
│
├── data/
│   ├── portfolio.py          # Portefeuille CUMP (achats, ventes, historique)
│   ├── fees_tax.py           # Frais broker + fiscalité France
│   ├── alerts_store.py       # Persistance des alertes
│   ├── market_data.py        # Prix, infos, news (yfinance)
│   └── ...                   # Autres sources de données
│
├── alerts/
│   ├── monitor.py            # Moteur de surveillance (stop-loss, cible, score)
│   └── scheduler.py          # Boucle de vérification automatique
│
├── backtesting/
│   └── backtest.py           # Backtest sur données historiques
│
├── output/
│   └── dashboard.py          # Interface Streamlit (4 onglets)
│
├── config/
│   ├── watchlist.json        # Tickers à surveiller par catégorie
│   ├── alerts.json           # Seuils d'alerte + config email
│   └── brokers.json          # Frais par broker
│
└── tests/                    # Tests unitaires (92 tests)
    ├── test_portfolio.py
    ├── test_scoring.py
    ├── test_fees_tax.py
    └── test_asset_type.py
```

---

## Configuration

### Activer les alertes email
Éditer `config/alerts.json` :
```json
"email": {
  "enabled": true,
  "destinataire": "ton@email.com",
  "expediteur": "ton@gmail.com",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_password": "mot_de_passe_application"
}
```

### Modifier les seuils d'alerte
```json
"seuils": {
  "pnl_stop_loss_pct": -8.0,   // alerte critique si perte > 8%
  "pnl_alerte_pct":   -4.0,   // avertissement si perte > 4%
  "pnl_cible_pct":    15.0    // alerte gain si profit > 15%
}
```

### Modifier la fréquence de surveillance
```json
"planning": {
  "intervalle_minutes": 60,    // vérification toutes les heures
  "avec_scores": false         // true = analyse complète (plus lent)
}
```

---

## Dépendances

```bash
pip install -r requirements.txt
```
