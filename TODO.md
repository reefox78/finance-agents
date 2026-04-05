# TODO — Finance Agents

Les tâches terminées restent visibles pour garder l'historique.

---

## ✅ Fait

- [x] Agents d'analyse : technique, fondamental, sentiment, risque, macro, insider, trends
- [x] 4 nouveaux agents : options flow, SEC 8-K filings, short interest, earnings surprise
- [x] Scanner multi-tickers avec watchlist configurable
- [x] Backtest (mode technique et multi-agents), graphique Plotly interactif
- [x] Dashboard 4 onglets : Analyse / Scanner / Portefeuille / Backtest
- [x] Portefeuille avec CUMP (Coût Unitaire Moyen Pondéré) — achats partiels, ventes partielles
- [x] Frais broker intégrés dans le CUMP (Trade Republic, Revolut, DEGIRO, Boursorama, IBKR)
- [x] Fiscalité France : PFU 30%, barème progressif (TMI), PEA après 5 ans
- [x] Suppression de lignes dans l'historique des ventes
- [x] Tooltips sur tous les termes techniques (CUMP, P&L brut/net, ticker…)
- [x] Prix d'achat pré-rempli au dernier cours dans le formulaire d'achat
- [x] Sélecteur ticker avec noms des sociétés (AAPL (Apple), BTC-USD (Bitcoin)…)
- [x] 92 tests unitaires pytest (portfolio, scoring, frais/fiscalité, asset type)
- [x] Système d'alertes : stop-loss, alerte P&L, cible de gain, score agents
- [x] Scheduler d'alertes en arrière-plan (`python alerts/scheduler.py`)
- [x] Badge 🔔 sur l'onglet Portefeuille quand alertes non lues
- [x] Commande unique de démarrage (`python start.py`)
- [x] Fix affichage agents Analyse — 4 par ligne au lieu de tout sur une seule ligne
- [x] Prix cible + stop-loss par position — bouton 🎯 Objectifs par position dans le portefeuille

---

## ⬜ À faire

- [ ] **Email alertes** — configurer `config/alerts.json` (email.enabled, destinataire, smtp_password)
      → Infrastructure prête, il suffit de renseigner les credentials
- [x] **Prix cible + stop-loss par position** — définir un objectif de vente par ticker,
      l'app surveille et alerte automatiquement
- [ ] **Historique du score** — tracer l'évolution du score d'un ticker dans le temps
      pour détecter une dégradation progressive avant une chute
- [ ] **Calibration des poids** — ajuster les poids des agents selon leurs performances
      historiques (backtest par agent)
- [ ] **Import CSV broker** — importer les trades depuis un export Trade Republic / Revolut
      pour éviter la saisie manuelle
- [ ] **Rapport PDF / email hebdomadaire** — résumé du portefeuille chaque lundi matin
- [ ] **Corrélation portefeuille** — détecter les sur-expositions sectorielles
      (ex: 80% tech sans le savoir)

---

## 💡 Idées (non priorisées)

- Notifications push mobile (Pushover / Telegram bot)
- Comparaison côte-à-côte de deux tickers
- Optimisation de la taille de position (Kelly criterion)
