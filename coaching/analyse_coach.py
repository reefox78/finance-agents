"""
Moteur de coaching — Analyse d'un ticker.

Règles issues de la littérature technique reconnue :
  - John J. Murphy  : "Technical Analysis of the Financial Markets"
  - Alexander Elder : "Trading for a Living" (Triple Screen, Force Index)
  - Stan Weinstein  : "Secrets for Profiting in Bull and Bear Markets" (Stage Analysis)
  - Van Tharp       : "Trade Your Way to Financial Freedom" (R-multiple, position sizing)
  - Martin Pring    : "Technical Analysis Explained" (momentum, intermarché)
  - PEAD research   : Post-Earnings Announcement Drift (Bernard & Thomas, 1989)

Chaque insight a :
  type     : bullish | bearish | warning | neutral | info
  category : technique | fondamental | risque | momentum | earnings | sentiment | secteur
  message  : explication en français
  rule     : la règle financière sous-jacente (éducatif)
  priority : 1 (critique) → 3 (informatif)
"""
from __future__ import annotations
from typing import Any


# ── Types ─────────────────────────────────────────────────────────────────────

def _insight(
    type_: str,
    category: str,
    message: str,
    rule: str,
    priority: int = 2,
) -> dict:
    return {
        "type":     type_,
        "category": category,
        "message":  message,
        "rule":     rule,
        "priority": priority,
    }


# ── Analyse technique (Murphy) ────────────────────────────────────────────────

def _analyse_technique(tech: dict, scores: dict) -> list[dict]:
    insights = []
    rsi   = tech.get("rsi")
    macd  = tech.get("macd")
    prix  = tech.get("prix_actuel")

    # ── RSI (Wilder, repris par Murphy ch.10) ─────────────────────────────────
    if rsi is not None:
        if rsi < 30:
            insights.append(_insight(
                "bullish", "technique",
                f"RSI à {rsi:.0f} — zone de survente franche. "
                "Les vendeurs s'épuisent, une réversion haussière est probable.",
                "Murphy : RSI < 30 = survente. Signal d'achat contrarian classique.",
                priority=1,
            ))
        elif rsi < 40:
            insights.append(_insight(
                "bullish", "technique",
                f"RSI à {rsi:.0f} — légèrement survendu. Zone favorable pour initier une position longue.",
                "Murphy : RSI entre 30 et 40 = zone de rebond potentiel sans excès baissier.",
                priority=2,
            ))
        elif rsi > 70:
            insights.append(_insight(
                "bearish", "technique",
                f"RSI à {rsi:.0f} — zone de surachat. Le cours a monté trop vite, "
                "risque de consolidation ou retournement.",
                "Murphy : RSI > 70 = surachat. Éviter d'acheter, réduire les positions longues.",
                priority=1,
            ))
        elif rsi > 60:
            insights.append(_insight(
                "warning", "technique",
                f"RSI à {rsi:.0f} — approche de la zone de surachat (>70). "
                "Surveiller un potentiel essoufflement de la hausse.",
                "Murphy : RSI entre 60 et 70 = momentum haussier mais attention au retournement.",
                priority=2,
            ))
        else:
            insights.append(_insight(
                "neutral", "technique",
                f"RSI à {rsi:.0f} — zone neutre (40-60). Pas de signal directionnel fort.",
                "Murphy : RSI en zone neutre = pas de pression acheteuse/vendeuse dominante.",
                priority=3,
            ))

    # ── MACD (Gerald Appel, popularisé par Murphy) ────────────────────────────
    if macd is not None:
        if macd > 0:
            insights.append(_insight(
                "bullish", "technique",
                f"MACD positif ({macd:.3f}) — la moyenne courte est au-dessus de la longue. "
                "Tendance haussière confirmée à court terme.",
                "Murphy : MACD > 0 = momentum haussier. Signal de suivi de tendance.",
                priority=2,
            ))
        else:
            insights.append(_insight(
                "bearish", "technique",
                f"MACD négatif ({macd:.3f}) — momentum baissier à court terme.",
                "Murphy : MACD < 0 = pression vendeuse dominante. Prudence sur les achats.",
                priority=2,
            ))

    # ── Confluence RSI + MACD (Elder — Triple Screen) ─────────────────────────
    if rsi is not None and macd is not None:
        if rsi < 40 and macd > 0:
            insights.append(_insight(
                "bullish", "technique",
                "Confluence haussière : RSI en zone de rebond ET MACD positif. "
                "Signal de triple écran validé (Elder) — configuration d'achat favorable.",
                "Elder (Triple Screen) : acheter quand le filtre long est haussier "
                "et l'oscillateur court est en survente.",
                priority=1,
            ))
        elif rsi > 60 and macd < 0:
            insights.append(_insight(
                "bearish", "technique",
                "Divergence : RSI encore élevé mais MACD déjà négatif. "
                "Le momentum s'affaiblit malgré un cours encore haut — signal de prudence.",
                "Elder : divergence RSI/MACD = perte de momentum. Signal de sortie potentiel.",
                priority=1,
            ))

    # ── Score technique global ─────────────────────────────────────────────────
    s_tech = scores.get("technique")
    if s_tech is not None:
        if s_tech >= 0.5:
            insights.append(_insight(
                "bullish", "technique",
                f"Score technique global élevé ({s_tech:.3f}). "
                "La majorité des indicateurs techniques pointent à la hausse.",
                "Confluence multi-indicateurs : quand RSI, MACD et tendance s'alignent, "
                "le signal est statistiquement plus fiable (Murphy ch.15).",
                priority=2,
            ))
        elif s_tech <= -0.5:
            insights.append(_insight(
                "bearish", "technique",
                f"Score technique fortement négatif ({s_tech:.3f}). "
                "Éviter les achats — la configuration technique est défavorable.",
                "Murphy : ne jamais acheter contre la tendance technique dominante.",
                priority=1,
            ))

    return insights


# ── Analyse fondamentale (Graham, Zweig) ─────────────────────────────────────

def _analyse_fondamental(scores: dict, info: dict | None) -> list[dict]:
    insights = []
    s_fond = scores.get("fondamental")

    if s_fond is not None:
        if s_fond >= 0.4:
            insights.append(_insight(
                "bullish", "fondamental",
                f"Fondamentaux solides (score {s_fond:.3f}). "
                "Valorisation et santé financière favorables.",
                "Graham (L'investisseur intelligent) : "
                "les fondamentaux solides donnent une marge de sécurité sur l'investissement.",
                priority=2,
            ))
        elif s_fond <= -0.3:
            insights.append(_insight(
                "warning", "fondamental",
                f"Fondamentaux faibles (score {s_fond:.3f}). "
                "La valorisation ou la santé financière soulève des questions.",
                "Graham : éviter les titres sans marge de sécurité fondamentale.",
                priority=2,
            ))

    return insights


# ── Earnings Surprise (PEAD — Bernard & Thomas 1989) ─────────────────────────

def _analyse_earnings(scores: dict, earnings: dict | None) -> list[dict]:
    insights = []
    s_earn = scores.get("earnings_surprise")

    if earnings and earnings.get("disponible"):
        latest = earnings.get("latest_surprise")
        avg    = earnings.get("avg_surprise")
        beats  = earnings.get("nb_beats", 0)
        total  = earnings.get("nb_quarters", 0)
        next_e = earnings.get("next_earnings")

        # PEAD : surprise positive récente
        if latest is not None and latest > 5:
            insights.append(_insight(
                "bullish", "earnings",
                f"Dernière surprise EPS : +{latest:.1f}%. "
                "Les études montrent que les actions qui battent les attentes "
                "continuent de surperformer 60 jours après la publication.",
                "PEAD (Post-Earnings Announcement Drift) — Bernard & Thomas 1989 : "
                "surprise > 5% génère une dérive haussière statistiquement significative.",
                priority=1,
            ))
        elif latest is not None and latest < -5:
            insights.append(_insight(
                "bearish", "earnings",
                f"Déception EPS : {latest:.1f}%. "
                "Le PEAD baissier suggère une sous-performance probable dans les 60 prochains jours.",
                "PEAD : une surprise négative crée une dérive baissière persistante. "
                "Éviter l'achat dans les semaines suivant la déception.",
                priority=1,
            ))

        # Régularité des beats
        if total >= 3 and beats >= total - 1:
            insights.append(_insight(
                "bullish", "earnings",
                f"Historique de beats : {beats}/{total} trimestres au-dessus des attentes. "
                "La régularité des résultats réduit le risque de surprise négative.",
                "Zweig : les entreprises avec un historique régulier de beats "
                "ont une prime de valorisation justifiée.",
                priority=2,
            ))

        # Alerte earnings proche
        if next_e:
            insights.append(_insight(
                "warning", "earnings",
                f"⚠️ Prochains résultats le {next_e}. "
                "L'incertitude pré-earnings augmente la volatilité. "
                "Réduire la position ou utiliser un stop plus large.",
                "Van Tharp : réduire l'exposition avant les événements binaires "
                "(earnings, BCE, FOMC) car la volatilité implicite gonfle le risque réel.",
                priority=1,
            ))

    return insights


# ── Short Interest (Descartes du short squeeze) ───────────────────────────────

def _analyse_short_interest(scores: dict, short: dict | None) -> list[dict]:
    insights = []

    if short and short.get("disponible"):
        pct        = short.get("short_pct")
        days_cover = short.get("days_to_cover")
        mom_change = short.get("mom_change_pct")

        if pct is not None and pct > 20:
            insights.append(_insight(
                "warning", "risque",
                f"Short interest élevé : {pct:.1f}% du float vendus à découvert. "
                "Risque de short squeeze en cas de news positive — volatilité accrue dans les deux sens.",
                "Short Squeeze : quand > 20% du float est shorté, une bonne news force "
                "les vendeurs à découvert à racheter en urgence, amplifiant la hausse.",
                priority=1,
            ))
        elif pct is not None and pct > 10:
            insights.append(_insight(
                "warning", "risque",
                f"Short interest notable : {pct:.1f}% du float. "
                "Présence significative de vendeurs à découvert — surveiller les news.",
                "Short interest > 10% = signal que des investisseurs institutionnels "
                "anticipent une baisse. Peut aussi signaler un potentiel squeeze.",
                priority=2,
            ))

        if days_cover is not None and days_cover > 5:
            insights.append(_insight(
                "warning", "risque",
                f"Days to cover : {days_cover:.1f} jours. "
                "Il faudrait {days_cover:.0f} jours de volume moyen pour que tous les shorts couvrent. "
                "Position courte très concentrée.",
                "Days to Cover > 5 = position short crowdée. "
                "Un retournement pourrait être violent (short squeeze).",
                priority=2,
            ))

        if mom_change is not None and mom_change > 20:
            insights.append(_insight(
                "bearish", "sentiment",
                f"Short interest en hausse de +{mom_change:.1f}% vs mois précédent. "
                "Les institutionnels augmentent leur position baissière.",
                "Hausse rapide du short interest = signal que des pros parient "
                "contre le titre. Signal contrarian négatif.",
                priority=2,
            ))

    return insights


# ── Analyse de risque sectoriel (Pring — intermarché) ────────────────────────

def _analyse_secteur(sector_risk: dict | None) -> list[dict]:
    insights = []
    if not sector_risk:
        return insights

    mult   = sector_risk.get("mult_sectoriel", 1.0)
    perf5j = sector_risk.get("driver_perf_5j")
    driver = sector_risk.get("driver", "")
    alerte = sector_risk.get("alerte", False)

    if alerte and mult < 0.80:
        insights.append(_insight(
            "bearish", "secteur",
            f"⚠️ Choc sectoriel détecté. {driver} en baisse de {abs(perf5j):.1f}% sur 5 jours. "
            f"Multiplicateur sectoriel : ×{mult:.2f}. Tout le secteur est sous pression.",
            "Pring (intermarché) : quand le driver de référence d'un secteur s'effondre, "
            "l'ensemble des titres du secteur sous-performe — réduire l'exposition.",
            priority=1,
        ))
    elif alerte and mult > 1.15:
        insights.append(_insight(
            "bullish", "secteur",
            f"Vent sectoriel favorable. {driver} en hausse de {perf5j:.1f}% sur 5 jours. "
            f"Multiplicateur sectoriel : ×{mult:.2f}.",
            "Pring : quand le driver sectoriel performe, "
            "les titres du secteur bénéficient d'un tailwind macroéconomique.",
            priority=2,
        ))

    return insights


# ── Analyse macro (Pring — cycle économique) ─────────────────────────────────

def _analyse_macro(scores: dict) -> list[dict]:
    insights = []
    s_macro = scores.get("macro")
    mult_macro = scores.get("mult_macro")

    if mult_macro is not None and mult_macro < 0.85:
        insights.append(_insight(
            "bearish", "risque",
            f"Environnement macro défavorable (multiplicateur ×{mult_macro:.2f}). "
            "Les conditions de marché globales pénalisent les positions acheteuses.",
            "Pring : dans un environnement macro baissier (taux en hausse, récession), "
            "même les bons titres sous-performent — réduire l'exposition globale.",
            priority=1,
        ))
    elif mult_macro is not None and mult_macro > 1.10:
        insights.append(_insight(
            "bullish", "risque",
            f"Vent macro favorable (×{mult_macro:.2f}). "
            "L'environnement global soutient les actifs risqués.",
            "Pring : en expansion macro avec taux accommodants, "
            "les actions bénéficient d'un soutien systémique.",
            priority=2,
        ))

    return insights


# ── Analyse options flow ──────────────────────────────────────────────────────

def _analyse_options(scores: dict, options: dict | None) -> list[dict]:
    insights = []

    if options and options.get("disponible"):
        pc_vol = options.get("pc_ratio_vol")
        skew   = options.get("skew_iv")
        unusual_calls = options.get("unusual_calls", 0)
        unusual_puts  = options.get("unusual_puts", 0)

        if pc_vol is not None:
            if pc_vol > 1.5:
                insights.append(_insight(
                    "bearish", "sentiment",
                    f"Ratio put/call élevé ({pc_vol:.2f}) — les traders achètent beaucoup de puts (protection baissière). "
                    "Sentiment institutionnel défensif.",
                    "Options flow : put/call > 1.5 = hedging massif ou anticipation de baisse par les pros.",
                    priority=2,
                ))
            elif pc_vol < 0.5:
                insights.append(_insight(
                    "bullish", "sentiment",
                    f"Ratio put/call faible ({pc_vol:.2f}) — fort biais haussier sur les options. "
                    "Les traders anticipent une hausse.",
                    "Options flow : put/call < 0.5 = euphorie haussière. "
                    "Attention : signal contrarian à l'extrême (trop de confiance).",
                    priority=2,
                ))

        if unusual_calls > 3:
            insights.append(_insight(
                "bullish", "sentiment",
                f"{unusual_calls} blocs d'appels inhabituels détectés (volume >> open interest). "
                "Signal d'achat potentiel par des intervenants informés.",
                "Unusual options activity : des achats massifs de calls avec volume > 5× OI "
                "suggèrent qu'un intervenant anticipe un mouvement haussier fort.",
                priority=1,
            ))

        if skew is not None and skew > 0.05:
            insights.append(_insight(
                "warning", "risque",
                f"IV skew négatif élevé ({skew:.3f}) — les puts OTM sont beaucoup plus chers que les calls. "
                "Le marché price une probabilité élevée de chute brutale.",
                "IV skew : prime élevée sur les puts = marché en mode protection. "
                "Réduire la taille de position ou acheter une protection.",
                priority=2,
            ))

    return insights


# ── Score final et decision (Van Tharp — position sizing) ────────────────────

def _analyse_score_final(score_final: float, decision: str, scores: dict) -> list[dict]:
    insights = []

    # Cohérence entre agents — Van Tharp : "confidence in system"
    agent_keys = ["technique", "fondamental", "sentiment", "macro", "trends",
                  "insider", "options_flow", "short_interest", "earnings_surprise", "volume_delta"]
    vals = [scores.get(k) for k in agent_keys if scores.get(k) is not None]
    if vals:
        bullish_count = sum(1 for v in vals if v > 0.05)
        bearish_count = sum(1 for v in vals if v < -0.05)
        agreement_pct = max(bullish_count, bearish_count) / len(vals) * 100

        if agreement_pct >= 75:
            direction = "haussier" if bullish_count > bearish_count else "baissier"
            insights.append(_insight(
                "bullish" if bullish_count > bearish_count else "bearish",
                "technique",
                f"Forte convergence des signaux : {int(agreement_pct)}% des agents sont {direction}s. "
                "La probabilité d'un mouvement dans ce sens est plus élevée.",
                "Van Tharp : la convergence multi-systèmes augmente la confiance dans le signal. "
                "Plus les agents s'accordent, plus le R-multiple attendu est favorable.",
                priority=1,
            ))
        elif agreement_pct < 55:
            insights.append(_insight(
                "neutral", "technique",
                f"Signaux mixtes — seulement {int(agreement_pct)}% des agents dans le même sens. "
                "Attendre un signal plus clair avant d'entrer en position.",
                "Van Tharp : un signal sans confluence = faible espérance mathématique. "
                "Mieux vaut rater une opportunité que prendre un trade peu probable.",
                priority=2,
            ))

    # Recommandation de sizing (Van Tharp — R-multiple)
    if decision == "ACHETER" and score_final > 0.15:
        risk_pct = min(2.0, round(score_final * 4, 1))  # max 2% du capital
        insights.append(_insight(
            "info", "risque",
            f"Position sizing suggéré : ne pas risquer plus de {risk_pct}% du capital total sur ce trade. "
            "Placer un stop-loss sous le support technique le plus proche.",
            "Van Tharp (Trade Your Way to Financial Freedom) : "
            "ne jamais risquer plus de 1-2% du capital par trade. "
            "Le sizing est la variable qui détermine la survie à long terme.",
            priority=1,
        ))
    elif decision == "VENDRE" or score_final < -0.15:
        insights.append(_insight(
            "warning", "risque",
            "Signal de vente ou de prudence. Si vous êtes en position : "
            "vérifier votre stop-loss et envisager de réduire l'exposition.",
            "Weinstein (Stage Analysis) : sortir d'une position quand le titre entre en Stage 4 "
            "(déclin). Ne pas espérer un retournement sans signal technique confirmé.",
            priority=1,
        ))

    return insights


# ── Point d'entrée principal ──────────────────────────────────────────────────

def generate_coaching(result: dict) -> dict:
    """
    Génère les insights de coaching à partir d'une réponse d'analyse complète.

    result : dict retourné par l'orchestrateur (scoring, tech, earnings, sector_risk, etc.)

    Retourne :
        insights   : liste triée par priorité
        resume     : phrase de synthèse
        score_final: score numérique
        decision   : ACHETER | NEUTRE | VENDRE
    """
    scores      = result.get("scoring", {}).get("scores", {})
    score_final = result.get("scoring", {}).get("score_final", 0) or 0
    decision    = result.get("scoring", {}).get("decision", "NEUTRE")
    tech        = result.get("tech") or {}
    earnings    = result.get("earnings")
    sector_risk = result.get("sector_risk")
    short       = result.get("short_interest")
    options     = result.get("options_flow")
    info        = result.get("info")

    insights: list[dict] = []
    insights += _analyse_technique(tech, scores)
    insights += _analyse_fondamental(scores, info)
    insights += _analyse_earnings(scores, earnings)
    insights += _analyse_short_interest(scores, short)
    insights += _analyse_secteur(sector_risk)
    insights += _analyse_macro(scores)
    insights += _analyse_options(scores, options)
    insights += _analyse_score_final(score_final, decision, scores)

    # Tri : priorité 1 en premier, puis bullish/bearish avant neutral/info
    order = {"bullish": 0, "bearish": 0, "warning": 1, "neutral": 2, "info": 2}
    insights.sort(key=lambda x: (x["priority"], order.get(x["type"], 3)))

    # Résumé synthétique
    if score_final > 0.3:
        resume = f"Signal haussier solide ({score_final:+.3f}). Les conditions techniques et fondamentales sont favorables à une entrée en position longue avec gestion stricte du risque."
    elif score_final > 0.1:
        resume = f"Signal légèrement positif ({score_final:+.3f}). Des éléments encourageants mais sans conviction forte — attendre un signal de confirmation avant d'entrer."
    elif score_final < -0.3:
        resume = f"Signal baissier fort ({score_final:+.3f}). Éviter les achats, envisager une réduction d'exposition si vous êtes en position."
    elif score_final < -0.1:
        resume = f"Signal légèrement négatif ({score_final:+.3f}). Prudence — les conditions ne sont pas réunies pour un achat opportun."
    else:
        resume = f"Signal neutre ({score_final:+.3f}). Pas de biais directionnel clair. Attendre que les conditions se clarifient."

    return {
        "insights":    insights,
        "resume":      resume,
        "score_final": score_final,
        "decision":    decision,
        "nb_insights": len(insights),
    }
