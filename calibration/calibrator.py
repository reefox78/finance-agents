"""
Calibration des poids des agents.

Principe
--------
Pour chaque analyse enregistrée dans data/score_history.json (avec prix +
scores_agents), on récupère le cours réel HORIZON_JOURS jours plus tard
via yfinance, puis on vérifie si chaque agent avait prédit la bonne direction.

  Exactitude = prédictions_correctes / prédictions_non_neutres
  50% = aléatoire (agent inutile)
  70% = agent fiable

Poids suggérés
--------------
  contribution = max(0, exactitude − 0.5) × 2    → 0..1
  Les contributions sont renormalisées pour conserver la même enveloppe
  de poids totaux que les poids par défaut.
  Les agents sans données suffisantes conservent leur poids actuel.

Application
-----------
  Les poids approuvés sont sauvegardés dans config/weights_custom.json.
  orchestrator/scoring.py les charge automatiquement à chaque analyse.
"""

import json
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

from data.score_history import lire_historique, lister_tickers
from orchestrator.scoring import POIDS as POIDS_DEFAUT

ROOT            = Path(__file__).parent.parent
FICHIER_POIDS   = ROOT / "config" / "weights_custom.json"

HORIZON_JOURS   = 7    # jours calendaires pour mesurer la direction réelle
SEUIL_NEUTRE    = 0.05  # scores ≤ ce seuil en valeur absolue = pas de prédiction
MIN_POINTS      = 5    # minimum de prédictions pour être pris en compte

# Agents non calibrables (multiplicateurs, pas scores additifs)
_EXCLUS = {"risque", "multiplicateur", "mult_macro"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prix_n_jours_apres(ticker: str, date_analyse: datetime, n: int) -> float | None:
    """Retourne le 1er cours de clôture disponible >= date_analyse + n jours."""
    date_cible = date_analyse + timedelta(days=n)
    # Pas encore disponible
    if date_cible > datetime.now() - timedelta(days=1):
        return None
    start = date_cible.strftime("%Y-%m-%d")
    end   = (date_cible + timedelta(days=15)).strftime("%Y-%m-%d")
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=True)
        if df.empty:
            return None
        close = df["Close"]
        if hasattr(close, "iloc"):
            val = close.iloc[0]
            if hasattr(val, "item"):
                return float(val.item())
            return float(val)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Calibration par ticker
# ---------------------------------------------------------------------------

def calibrer(ticker: str, horizon: int = HORIZON_JOURS) -> dict:
    """
    Calcule l'exactitude de chaque agent pour un ticker donné.

    Retourne
    --------
    {
      "ticker":          str,
      "nb_points_total": int,   ← entrées avec scores_agents + prix évaluables
      "horizon_jours":   int,
      "agents": {
          "technique": {"nb_predictions": int, "nb_correctes": int, "exactitude": float|None},
          ...
      },
      "poids_suggeres": {agent: float, ...}
    }
    """
    historique   = lire_historique(ticker)
    maintenant   = datetime.now()
    stats: dict  = {}   # agent → {correct: int, total: int}
    nb_points    = 0

    for entree in historique:
        if "scores_agents" not in entree or "prix" not in entree:
            continue
        ts = datetime.fromisoformat(entree["ts"])
        if (maintenant - ts).days < horizon:
            continue   # trop récent

        prix_futur = _prix_n_jours_apres(ticker, ts, horizon)
        if prix_futur is None:
            continue

        prix_analyse   = entree["prix"]
        rendement      = (prix_futur - prix_analyse) / prix_analyse
        direction_reel = 1 if rendement > 0.005 else (-1 if rendement < -0.005 else 0)
        if direction_reel == 0:
            continue   # mouvement trop faible — ne compte pas

        nb_points += 1
        for agent, score in entree["scores_agents"].items():
            if agent in _EXCLUS:
                continue
            if abs(score) < SEUIL_NEUTRE:
                continue   # prédiction neutre — ignorée
            direction_agent = 1 if score > 0 else -1
            if agent not in stats:
                stats[agent] = {"correct": 0, "total": 0}
            stats[agent]["total"]   += 1
            stats[agent]["correct"] += int(direction_agent == direction_reel)

    agents_stats: dict = {}
    for agent, r in stats.items():
        exactitude = (r["correct"] / r["total"]) if r["total"] >= MIN_POINTS else None
        agents_stats[agent] = {
            "nb_predictions": r["total"],
            "nb_correctes":   r["correct"],
            "exactitude":     exactitude,
        }

    return {
        "ticker":          ticker,
        "nb_points_total": nb_points,
        "horizon_jours":   horizon,
        "agents":          agents_stats,
        "poids_suggeres":  _suggerer_poids(agents_stats),
    }


# ---------------------------------------------------------------------------
# Calibration globale (tous tickers agrégés)
# ---------------------------------------------------------------------------

def calibrer_global(horizon: int = HORIZON_JOURS) -> dict:
    """
    Agrège les données de calibration de tous les tickers disponibles.
    Retourne le même format que calibrer() mais sans le champ "ticker".
    """
    tickers           = lister_tickers()
    aggreg: dict      = {}
    nb_tickers_actifs = 0
    nb_points_total   = 0

    for ticker in tickers:
        r = calibrer(ticker, horizon)
        if r["nb_points_total"] == 0:
            continue
        nb_tickers_actifs += 1
        nb_points_total   += r["nb_points_total"]
        for agent, s in r["agents"].items():
            if agent not in aggreg:
                aggreg[agent] = {"correct": 0, "total": 0}
            aggreg[agent]["correct"] += s["nb_correctes"]
            aggreg[agent]["total"]   += s["nb_predictions"]

    agents_stats: dict = {}
    for agent, r in aggreg.items():
        exactitude = (r["correct"] / r["total"]) if r["total"] >= MIN_POINTS else None
        agents_stats[agent] = {
            "nb_predictions": r["total"],
            "nb_correctes":   r["correct"],
            "exactitude":     exactitude,
        }

    return {
        "nb_tickers":      nb_tickers_actifs,
        "nb_points_total": nb_points_total,
        "agents":          agents_stats,
        "poids_suggeres":  _suggerer_poids(agents_stats),
    }


# ---------------------------------------------------------------------------
# Suggestion de poids
# ---------------------------------------------------------------------------

def _suggerer_poids(agents_stats: dict) -> dict:
    """
    Calcule des poids suggérés proportionnels à (exactitude − 50%).
    Les agents sans données suffisantes conservent leur poids actuel.
    """
    poids_defaut_agents = {k: v for k, v in POIDS_DEFAUT.items() if k not in _EXCLUS}

    contrib:              dict  = {}
    total_contrib:        float = 0.0
    total_poids_connus:   float = 0.0
    total_poids_inconnus: float = 0.0

    for agent, poids in poids_defaut_agents.items():
        stats = agents_stats.get(agent)
        if stats and stats["exactitude"] is not None:
            c = max(0.0, stats["exactitude"] - 0.5) * 2   # 0..1
            contrib[agent]     = c
            total_contrib     += c
            total_poids_connus += poids
        else:
            total_poids_inconnus += poids

    poids_suggeres: dict = {}
    for agent, poids in poids_defaut_agents.items():
        if agent in contrib:
            if total_contrib > 0:
                poids_suggeres[agent] = round(
                    contrib[agent] / total_contrib * total_poids_connus, 4
                )
            else:
                poids_suggeres[agent] = poids
        else:
            poids_suggeres[agent] = poids   # conserve le poids actuel

    return poids_suggeres


# ---------------------------------------------------------------------------
# Sauvegarde / chargement des poids custom
# ---------------------------------------------------------------------------

def sauvegarder_poids(poids: dict) -> None:
    """Sauvegarde les poids approuvés dans config/weights_custom.json."""
    FICHIER_POIDS.parent.mkdir(exist_ok=True)
    with open(FICHIER_POIDS, "w", encoding="utf-8") as f:
        json.dump(poids, f, indent=2)


def charger_poids_custom() -> dict | None:
    """
    Charge les poids custom si le fichier existe.
    Retourne None si aucun fichier ou fichier invalide.
    """
    if not FICHIER_POIDS.exists():
        return None
    try:
        with open(FICHIER_POIDS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def supprimer_poids_custom() -> None:
    """Supprime le fichier de poids custom (retour aux défauts)."""
    if FICHIER_POIDS.exists():
        FICHIER_POIDS.unlink()


if __name__ == "__main__":
    r = calibrer_global()
    print(f"\n=== Calibration globale ({r['nb_tickers']} tickers, {r['nb_points_total']} points) ===")
    print(f"{'Agent':<18} {'Prédictions':>12} {'Correctes':>10} {'Exactitude':>12} {'Poids actuel':>13} {'Poids suggéré':>14}")
    print("-" * 82)
    for agent, s in sorted(r["agents"].items()):
        ex = f"{s['exactitude']*100:.1f}%" if s["exactitude"] is not None else "N/A"
        pa = POIDS_DEFAUT.get(agent, 0)
        ps = r["poids_suggeres"].get(agent, pa)
        print(f"{agent:<18} {s['nb_predictions']:>12} {s['nb_correctes']:>10} {ex:>12} {pa:>13.4f} {ps:>14.4f}")
