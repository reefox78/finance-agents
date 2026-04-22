"""
Moteur de coaching — Journal de trading.

Analyse les statistiques de performance réelles du trader et génère
des conseils personnalisés basés sur des règles issues de :

  - Van Tharp   : "Trade Your Way to Financial Freedom"
               → Position sizing, R-multiple, expectancy
  - Alexander Elder : "Trading for a Living"
               → Discipline, gestion des émotions, règle des 2%
  - Mark Douglas : "Trading in the Zone"
               → Psychologie du trading, gestion des séries
  - Michael Covel  : "Trend Following"
               → Profit factor, suivi de tendance
  - Brett Steenbarger : "The Psychology of Trading"
               → Analyse des patterns d'erreur, amélioration continue
"""
from __future__ import annotations


def _tip(
    type_: str,
    category: str,
    title: str,
    message: str,
    action: str,
    rule: str,
    priority: int = 2,
) -> dict:
    return {
        "type":     type_,      # success | warning | danger | info
        "category": category,   # performance | risque | psychologie | stratégie | discipline
        "title":    title,
        "message":  message,
        "action":   action,     # action concrète à faire
        "rule":     rule,
        "priority": priority,
    }


# ── Win Rate (Elder, Van Tharp) ───────────────────────────────────────────────

def _coach_win_rate(stats: dict) -> list[dict]:
    tips = []
    wr = stats.get("win_rate")
    if wr is None:
        return tips

    avg_pnl     = stats.get("avg_pnl") or 0
    avg_pnl_pct = stats.get("avg_pnl_pct") or 0

    if wr < 35:
        tips.append(_tip(
            "danger", "performance",
            "Taux de réussite critique",
            f"Ton win rate est de {wr:.1f}% — tu perds plus de 6 trades sur 10. "
            "Même avec un bon risk/reward, c'est difficile à compenser. "
            "Le problème est probablement dans tes critères d'entrée.",
            "Arrête de trader en réel. Reviens au paper trading et audite tes 10 derniers trades perdants : "
            "as-tu respecté ton setup ? As-tu acheté contre la tendance ?",
            "Van Tharp : un système avec win rate < 35% nécessite un R/R > 2.5 pour être profitable. "
            "Si ce n'est pas le cas, l'espérance mathématique est négative.",
            priority=1,
        ))
    elif wr < 45:
        tips.append(_tip(
            "warning", "performance",
            "Win rate à améliorer",
            f"Win rate de {wr:.1f}%. Acceptable seulement si ton gain moyen est "
            f"significativement plus grand que ta perte moyenne.",
            "Vérifie ton ratio gain/perte moyen. Si ton gain moyen n'est pas au moins "
            "1.5× ta perte moyenne, ton système perd de l'argent à long terme.",
            "Elder : un win rate de 40% avec un R/R de 2:1 génère une espérance positive. "
            "Un win rate de 40% avec R/R de 1:1 mène à la ruine.",
            priority=2,
        ))
    elif wr >= 55:
        tips.append(_tip(
            "success", "performance",
            "Bon taux de réussite",
            f"Win rate de {wr:.1f}% — tu gagnes plus d'1 trade sur 2. "
            "Assure-toi que tes gains moyens sont supérieurs à tes pertes moyennes "
            "pour maximiser ton espérance.",
            "Continue à documenter chaque trade. Identifie les setups qui génèrent "
            "ton meilleur win rate et augmente progressivement ta mise sur ceux-là.",
            "Van Tharp : un win rate élevé est rassurant psychologiquement mais "
            "ce qui compte vraiment est l'expectancy = (Win% × Gain moyen) − (Loss% × Perte moyenne).",
            priority=3,
        ))

    return tips


# ── Profit Factor (Covel, Van Tharp) ─────────────────────────────────────────

def _coach_profit_factor(stats: dict) -> list[dict]:
    tips = []
    pf = stats.get("profit_factor")
    if pf is None:
        return tips

    if pf < 1.0:
        tips.append(_tip(
            "danger", "performance",
            "Système perdant (Profit Factor < 1)",
            f"Ton profit factor est de {pf:.2f}. Cela signifie que pour 1€ gagné, "
            f"tu perds {1/pf:.2f}€. Ton système détruit du capital.",
            "STOP trading réel immédiatement. Reviens en paper trading jusqu'à atteindre "
            "un profit factor > 1.3 sur 20 trades consécutifs.",
            "Covel (Trend Following) : un PF < 1 signifie que ta méthode est mathématiquement "
            "perdante. Aucune gestion du risque ne peut sauver un système à espérance négative.",
            priority=1,
        ))
    elif pf < 1.5:
        tips.append(_tip(
            "warning", "performance",
            "Profit Factor marginal",
            f"Profit factor de {pf:.2f}. Ton système est légèrement profitable "
            "mais peu robuste — une série de pertes peut rapidement le mettre dans le rouge.",
            "Travaille sur la qualité des entrées : attends des setups avec un R/R minimum de 2:1 "
            "et évite les trades 'moyens' sans conviction.",
            "Van Tharp : un PF entre 1 et 1.5 est fragile. "
            "Les frais de courtage et le slippage peuvent l'effacer. Viser PF > 1.5.",
            priority=2,
        ))
    elif pf >= 2.0:
        tips.append(_tip(
            "success", "performance",
            "Excellent Profit Factor",
            f"Profit factor de {pf:.2f} — système très solide. "
            "Tu génères {pf:.1f}€ pour chaque euro perdu.",
            "Tu peux progressivement augmenter ta taille de position (+ 10-20% par mois max) "
            "tout en gardant ta règle des 1-2% de risque par trade.",
            "Van Tharp : PF > 2 = système robuste. Attention à ne pas over-fitter "
            "(résultats sur petit échantillon peuvent être trompeurs — viser 50+ trades).",
            priority=3,
        ))

    return tips


# ── Drawdown (Elder — règle des 6%) ──────────────────────────────────────────

def _coach_drawdown(stats: dict) -> list[dict]:
    tips = []
    dd = stats.get("max_drawdown")
    if dd is None:
        return tips

    # max_drawdown est négatif dans notre système
    dd_abs = abs(dd)

    if dd_abs > 500:
        tips.append(_tip(
            "danger", "risque",
            "Drawdown maximum préoccupant",
            f"Ta perte maximale en séquence est de {dd_abs:.0f}€. "
            "Ce niveau de drawdown peut détruire la confiance et mener à des décisions émotionnelles.",
            "Applique la règle des 6% d'Elder : si tu perds 6% de ton capital dans le mois, "
            "tu arrêtes de trader jusqu'au mois suivant. Revois ta taille de position.",
            "Elder (Trading for a Living) : la règle des 6% mensuels protège ton capital "
            "ET ta psychologie. Un trader qui subit un gros drawdown prend des risques "
            "inconsidérés pour 'se refaire' — spirale dangereuse.",
            priority=1,
        ))
    elif dd_abs > 200:
        tips.append(_tip(
            "warning", "risque",
            "Drawdown à surveiller",
            f"Drawdown max de {dd_abs:.0f}€. Reste dans des limites acceptables "
            "si ton capital total est > 2000€, mais à surveiller.",
            "Définis une limite mensuelle de perte en % de ton capital. "
            "Si tu l'atteins, tu t'arrêtes — pas de discussion.",
            "Elder : les meilleures règles sont celles qu'on se fixe à l'avance, "
            "quand les émotions ne sont pas impliquées.",
            priority=2,
        ))

    return tips


# ── Série perdante (Douglas — psychologie) ────────────────────────────────────

def _coach_streak(stats: dict) -> list[dict]:
    tips = []
    streak = stats.get("current_streak", {})
    if not streak:
        return tips

    stype  = streak.get("type")
    scount = streak.get("count", 0)

    if stype == "loss" and scount >= 3:
        tips.append(_tip(
            "danger", "psychologie",
            f"⚠️ Série de {scount} pertes consécutives",
            f"Tu es sur une série de {scount} trades perdants. "
            "Dans cet état, le cerveau cherche à 'se refaire' en prenant plus de risques — "
            "c'est le piège le plus dangereux en trading.",
            "Pause obligatoire : ne place aucun trade pendant 24-48h minimum. "
            "Revois les {scount} trades perdants : étaient-ils conformes à ton plan ? "
            "Si oui, c'est la variance normale. Si non, tu as un problème de discipline.",
            "Douglas (Trading in the Zone) : une série de pertes active le biais de récence. "
            "Le trader modifie son système ou prend trop de risques pour 'rattraper' — "
            "ce qui empire toujours la situation.",
            priority=1,
        ))
    elif stype == "loss" and scount == 2:
        tips.append(_tip(
            "warning", "psychologie",
            "2 pertes d'affilée — vigilance",
            "2 trades perdants consécutifs. Pas encore alarmant mais surveille ton état émotionnel.",
            "Avant le prochain trade : vérifie que tu respectes ton setup habituel "
            "et que tu ne cherches pas à 'te rattraper'. Si tu ressens de l'urgence, attends.",
            "Douglas : la discipline, c'est de trader exactement pareil après 2 pertes qu'après 2 gains.",
            priority=2,
        ))
    elif stype == "win" and scount >= 4:
        tips.append(_tip(
            "warning", "psychologie",
            f"🔥 {scount} gains consécutifs — attention au biais de confiance",
            f"Série de {scount} trades gagnants. L'excès de confiance est aussi dangereux "
            "que la peur — il pousse à sur-trader et à négliger la gestion du risque.",
            "Maintiens exactement la même taille de position et les mêmes règles d'entrée. "
            "Ne 'récompense' pas ta série en prenant plus de risque.",
            "Steenbarger : l'euphorie post-gains est l'ennemi de la discipline. "
            "Les traders qui survivent ont le même comportement après 5 gains qu'après 5 pertes.",
            priority=2,
        ))

    return tips


# ── Analyse par stratégie ─────────────────────────────────────────────────────

def _coach_strategy(stats: dict) -> list[dict]:
    tips = []
    by_strat = stats.get("by_strategy", {})
    if not by_strat or len(by_strat) < 2:
        return tips

    # Trouver la meilleure et la pire stratégie
    best_strat  = max(by_strat.items(), key=lambda x: x[1].get("pnl", 0))
    worst_strat = min(by_strat.items(), key=lambda x: x[1].get("pnl", 0))

    b_name, b_data = best_strat
    w_name, w_data = worst_strat

    if b_data["pnl"] > 0 and w_data["pnl"] < 0:
        tips.append(_tip(
            "info", "stratégie",
            f"Spécialise-toi sur '{b_name}'",
            f"Ta stratégie '{b_name}' génère {b_data['pnl']:+.0f}€ avec un win rate de {b_data['win_rate']:.0f}%. "
            f"Ta stratégie '{w_name}' perd {w_data['pnl']:.0f}€. "
            "Concentrer ton énergie sur ce qui fonctionne est plus rentable qu'essayer de tout améliorer.",
            f"Dans les 30 prochains jours, trade uniquement en '{b_name}'. "
            "Laisse '{w_name}' en paper trading le temps de comprendre pourquoi elle perd.",
            "Steenbarger : les traders professionnels se spécialisent. "
            "L'excellence dans une stratégie vaut mieux que la médiocrité dans cinq.",
            priority=1,
        ))

    # Stratégie avec bon win rate mais mauvais PnL = problème de R/R
    for name, data in by_strat.items():
        wr  = data.get("win_rate", 0)
        pnl = data.get("pnl", 0)
        trades = data.get("trades", 0)
        if trades >= 3 and wr > 55 and pnl < 0:
            tips.append(_tip(
                "warning", "stratégie",
                f"Problème de Risk/Reward sur '{name}'",
                f"'{name}' a un win rate de {wr:.0f}% mais génère quand même des pertes ({pnl:.0f}€). "
                "Cela signifie que tes pertes sont bien plus grosses que tes gains sur cette stratégie.",
                f"Sur '{name}' : vérifie que ton stop-loss n'est pas trop large et que tu prends bien tes profits "
                "avant qu'ils ne s'évaporent. Vise un R/R minimum de 1.5:1.",
                "Van Tharp : un win rate élevé avec R/R < 1 est le piège classique du trader débutant. "
                "Tu prends de gros risques pour de petits gains — et une seule grosse perte efface tout.",
                priority=1,
            ))

    return tips


# ── Volume de trading (sur-trading) ──────────────────────────────────────────

def _coach_volume(stats: dict) -> list[dict]:
    tips = []
    total = stats.get("closed_trades", 0)

    if total >= 30:
        tips.append(_tip(
            "warning", "discipline",
            "Volume de trades important",
            f"{total} trades clôturés. Un volume élevé peut signifier du sur-trading : "
            "entrer en position par ennui, impatience ou revanche plutôt que sur signal réel.",
            "Calcule ton ratio signal/bruit : combien de trades respectaient vraiment "
            "ton setup ? Si < 80%, tu entres trop souvent.",
            "Elder : 'Trade less, make more'. Chaque trade supplémentaire augmente "
            "les frais et le risque d'erreur émotionnelle. Les meilleurs traders font peu de trades mais bons.",
            priority=2,
        ))

    return tips


# ── Point d'entrée ────────────────────────────────────────────────────────────

def generate_journal_coaching(stats: dict) -> dict:
    """
    Génère des conseils personnalisés à partir des stats du journal.

    stats : dict retourné par db.journal.get_stats()

    Retourne :
        tips     : liste de conseils triés par priorité
        niveau   : débutant | intermédiaire | avancé
        synthese : phrase de bilan global
    """
    if stats.get("closed_trades", 0) < 3:
        return {
            "tips": [{
                "type":     "info",
                "category": "discipline",
                "title":    "Commence à remplir ton journal",
                "message":  "Tu as besoin d'au moins 3 trades clôturés pour générer des statistiques significatives.",
                "action":   "Enregistre tes trades passés rétrospectivement pour commencer à avoir des données.",
                "rule":     "Van Tharp : sans données, tu pilotes à l'aveugle. Le journal est le fondement de tout progrès.",
                "priority": 1,
            }],
            "niveau":   "débutant",
            "synthese": "Pas encore assez de données pour une analyse. Continue à remplir ton journal.",
        }

    tips: list[dict] = []
    tips += _coach_win_rate(stats)
    tips += _coach_profit_factor(stats)
    tips += _coach_drawdown(stats)
    tips += _coach_streak(stats)
    tips += _coach_strategy(stats)
    tips += _coach_volume(stats)

    # Tri par priorité
    tips.sort(key=lambda x: x["priority"])

    # Niveau du trader
    pf = stats.get("profit_factor") or 0
    wr = stats.get("win_rate") or 0
    total = stats.get("closed_trades", 0)

    if pf >= 1.8 and wr >= 50 and total >= 20:
        niveau = "avancé"
    elif pf >= 1.2 and total >= 10:
        niveau = "intermédiaire"
    else:
        niveau = "débutant"

    # Synthèse
    pnl_total = stats.get("total_pnl", 0) or 0
    if pnl_total > 0 and pf and pf >= 1.5:
        synthese = f"Performance globale positive : +{pnl_total:.0f}€ avec un profit factor de {pf:.2f}. " \
                   "Ton système est viable — travaille sur la régularité et le scaling."
    elif pnl_total > 0:
        synthese = f"Légèrement profitable (+{pnl_total:.0f}€) mais le système manque de robustesse. " \
                   "Concentre-toi sur l'amélioration du profit factor avant d'augmenter les mises."
    elif pnl_total < 0:
        synthese = f"Performance négative ({pnl_total:.0f}€). " \
                   "Reviens aux fondamentaux : respect du stop-loss, qualité des entrées, R/R minimum 1.5:1."
    else:
        synthese = "Résultat à l'équilibre. Améliore la sélection des trades pour basculer en positif."

    return {
        "tips":     tips,
        "niveau":   niveau,
        "synthese": synthese,
        "nb_tips":  len(tips),
    }
