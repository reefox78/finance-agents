"""
Gestion du portefeuille avec calcul CUMP (Coût Unitaire Moyen Pondéré).

Logique :
  - Chaque ACHAT recalcule le prix moyen pondéré de la position
  - Chaque VENTE (partielle ou totale) utilise le prix moyen courant pour calculer le P&L
  - Le prix moyen ne change PAS après une vente
  - Si la quantité atteint 0, la position est fermée mais les transactions restent loguées

Structure data/portfolio.json :
{
  "positions": {
    "AAPL": {
      "ticker":       "AAPL",
      "quantite":     2.0,
      "prix_moyen":   112.27,
      "transactions": [
        {"id": "...", "type": "achat", "date": "...", "prix": 100.0, "quantite": 10.0, "notes": ""},
        {"id": "...", "type": "vente", "date": "...", "prix": 150.0, "quantite": 15.0,
         "prix_moyen_achat": 113.33, "pnl_eur": 548.0, "pnl_pct": 32.4, "notes": ""}
      ]
    }
  },
  "historique_ventes": [
    {"id": "...", "ticker": "AAPL", "date": "...", "prix_vente": 150.0,
     "quantite": 15.0, "prix_moyen_achat": 113.33, "pnl_eur": 548.0, "pnl_pct": 32.4, "notes": ""}
  ]
}
"""

import json
import uuid
from pathlib import Path
from datetime import datetime

import yfinance as yf

PORTFOLIO_PATH = Path("data/portfolio.json")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _charger() -> dict:
    if PORTFOLIO_PATH.exists():
        with open(PORTFOLIO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return _migrer(data)
    return {"positions": {}, "historique_ventes": []}


def _migrer(data: dict) -> dict:
    """Migre l'ancien format (liste de positions) vers le nouveau format (CUMP)."""
    # Déjà au nouveau format
    if isinstance(data.get("positions"), dict):
        if "historique_ventes" not in data:
            data["historique_ventes"] = []
        return data

    # Ancien format : positions = liste, historique = liste
    nouveau = {"positions": {}, "historique_ventes": []}

    # Migrer les positions ouvertes (ancien format)
    for pos in data.get("positions", []):
        ticker = pos["ticker"]
        if ticker not in nouveau["positions"]:
            nouveau["positions"][ticker] = {
                "ticker":       ticker,
                "quantite":     0.0,
                "prix_moyen":   0.0,
                "transactions": [],
            }
        p = nouveau["positions"][ticker]
        # Reconstituer un achat depuis l'ancienne position
        tx = {
            "id":       pos.get("id", _new_id()),
            "type":     "achat",
            "date":     pos.get("date_achat", datetime.now().strftime("%Y-%m-%d")),
            "prix":     pos["prix_achat"],
            "quantite": pos["quantite"],
            "notes":    pos.get("notes", ""),
        }
        _appliquer_achat(p, tx)

    # Migrer l'historique des ventes (ancien format)
    for trade in data.get("historique", []):
        nouveau["historique_ventes"].append({
            "id":               trade.get("id", _new_id()),
            "ticker":           trade["ticker"],
            "date":             trade.get("date_vente", ""),
            "prix_vente":       trade.get("prix_vente", 0),
            "quantite":         trade.get("quantite", 0),
            "prix_moyen_achat": trade.get("prix_achat", 0),
            "pnl_eur":          trade.get("pnl_eur", 0),
            "pnl_pct":          trade.get("pnl_pct", 0),
            "notes":            trade.get("notes_vente") or trade.get("notes_achat") or "",
        })

    _sauvegarder(nouveau)
    return nouveau


def _sauvegarder(data: dict) -> None:
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PORTFOLIO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _new_id() -> str:
    return str(uuid.uuid4())[:8]


# ---------------------------------------------------------------------------
# Mécanique CUMP
# ---------------------------------------------------------------------------

def _appliquer_achat(position: dict, tx: dict) -> None:
    """
    Met à jour le prix moyen pondéré après un achat.
    CUMP avec frais = (qty_avant×pm_avant + qty_achat×prix + frais) / (qty_avant + qty_achat)
    Les frais d'achat majorent le coût de revient — méthode standard AMF/Boursorama.
    """
    q_avant  = position["quantite"]
    pm_avant = position["prix_moyen"]
    q_achat  = tx["quantite"]
    p_achat  = tx["prix"]
    frais    = tx.get("frais", 0.0)

    nouveau_total = q_avant + q_achat
    if nouveau_total > 0:
        position["prix_moyen"] = round(
            (q_avant * pm_avant + q_achat * p_achat + frais) / nouveau_total, 6
        )
    position["quantite"] = round(nouveau_total, 6)
    position["transactions"].append(tx)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def ajouter_achat(ticker: str, prix: float, quantite: float,
                  date: str = None, notes: str = "", frais: float = 0.0) -> dict:
    """
    Enregistre un achat. Recalcule le CUMP (frais inclus) si la position existe déjà.
    Retourne la position mise à jour.
    """
    data   = _charger()
    ticker = ticker.upper().strip()

    if ticker not in data["positions"]:
        data["positions"][ticker] = {
            "ticker":       ticker,
            "quantite":     0.0,
            "prix_moyen":   0.0,
            "transactions": [],
        }

    tx = {
        "id":       _new_id(),
        "type":     "achat",
        "date":     date or datetime.now().strftime("%Y-%m-%d"),
        "prix":     round(float(prix), 6),
        "quantite": round(float(quantite), 6),
        "frais":    round(float(frais), 4),
        "notes":    notes,
    }
    _appliquer_achat(data["positions"][ticker], tx)
    _sauvegarder(data)
    return data["positions"][ticker]


def ajouter_vente(ticker: str, prix_vente: float, quantite: float,
                  date: str = None, notes: str = "", frais: float = 0.0) -> dict:
    """
    Enregistre une vente (partielle ou totale).
    P&L net = (prix_vente - CUMP) × qty - frais_vente
    Retourne le trade enregistré. Lève ValueError si quantité insuffisante.
    """
    data   = _charger()
    ticker = ticker.upper().strip()
    pos    = data["positions"].get(ticker)

    if pos is None or pos["quantite"] <= 0:
        raise ValueError(f"Aucune position ouverte pour {ticker}")

    quantite = round(float(quantite), 6)
    if quantite > pos["quantite"] + 1e-9:
        raise ValueError(
            f"Quantité insuffisante : tu as {pos['quantite']} {ticker}, "
            f"tu essaies de vendre {quantite}"
        )

    frais            = round(float(frais), 4)
    prix_moyen_achat = pos["prix_moyen"]
    pnl_brut         = round((float(prix_vente) - prix_moyen_achat) * quantite, 2)
    pnl_eur          = round(pnl_brut - frais, 2)   # net après frais de vente
    pnl_pct          = round(pnl_eur / (prix_moyen_achat * quantite) * 100, 2) \
                       if prix_moyen_achat else 0.0

    tx_vente = {
        "id":               _new_id(),
        "type":             "vente",
        "date":             date or datetime.now().strftime("%Y-%m-%d"),
        "prix":             round(float(prix_vente), 6),
        "quantite":         quantite,
        "frais":            frais,
        "prix_moyen_achat": round(prix_moyen_achat, 6),
        "pnl_brut":         pnl_brut,
        "pnl_eur":          pnl_eur,
        "pnl_pct":          pnl_pct,
        "notes":            notes,
    }

    # Mise à jour de la position (le prix moyen ne change pas après une vente)
    pos["quantite"] = round(pos["quantite"] - quantite, 6)
    pos["transactions"].append(tx_vente)

    # Si position soldée
    if pos["quantite"] < 1e-9:
        pos["quantite"]   = 0.0
        pos["prix_moyen"] = 0.0

    # Ajout à l'historique global des ventes
    vente_hist = {k: v for k, v in tx_vente.items()}
    vente_hist["ticker"] = ticker
    vente_hist["prix_vente"] = tx_vente["prix"]
    data["historique_ventes"].append(vente_hist)
    _sauvegarder(data)
    return vente_hist


def supprimer_position(ticker: str) -> bool:
    """Supprime entièrement une position (sans laisser de trace dans l'historique)."""
    data   = _charger()
    ticker = ticker.upper().strip()
    if ticker in data["positions"]:
        del data["positions"][ticker]
        _sauvegarder(data)
        return True
    return False


def lister_positions() -> list[dict]:
    """Retourne les positions avec quantité > 0."""
    data = _charger()
    return [p for p in data["positions"].values() if p["quantite"] > 1e-9]


def lister_historique() -> list[dict]:
    """Retourne toutes les ventes du plus récent au plus ancien."""
    hist = _charger()["historique_ventes"]
    return sorted(hist, key=lambda x: x.get("date", ""), reverse=True)


def lister_transactions(ticker: str) -> list[dict]:
    """Retourne le log complet des transactions pour un ticker."""
    data   = _charger()
    ticker = ticker.upper().strip()
    pos    = data["positions"].get(ticker, {})
    txs    = pos.get("transactions", [])
    return sorted(txs, key=lambda x: x.get("date", ""), reverse=True)


# ---------------------------------------------------------------------------
# Évaluation P&L latent + signal de sortie
# ---------------------------------------------------------------------------

def _prix_actuel(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).info
        prix = info.get("regularMarketPrice") or info.get("currentPrice")
        if prix:
            return float(prix)
        hist = yf.Ticker(ticker).history(period="1d")
        return float(hist["Close"].iloc[-1]) if not hist.empty else None
    except Exception:
        return None


def _signal_sortie(pnl_pct: float, score: float) -> str:
    if pnl_pct <= -8.0 or score <= -0.10:
        return "VENDRE"
    if pnl_pct <= -4.0 or score <= 0.05:
        return "SURVEILLER"
    return "TENIR"


def evaluer_positions(with_scores: bool = True) -> list[dict]:
    """
    Retourne les positions actives enrichies :
    prix_actuel, pnl_latent_eur, pnl_latent_pct, score, signal_sortie.
    """
    from orchestrator.orchestrator import run as orchestrer

    positions = lister_positions()
    resultats = []

    for pos in positions:
        ticker     = pos["ticker"]
        prix_moyen = pos["prix_moyen"]
        quantite   = pos["quantite"]
        investi    = round(prix_moyen * quantite, 2)

        prix_now = _prix_actuel(ticker)
        if prix_now:
            pnl_eur = round((prix_now - prix_moyen) * quantite, 2)
            pnl_pct = round((prix_now - prix_moyen) / prix_moyen * 100, 2)
            valeur  = round(prix_now * quantite, 2)
        else:
            pnl_eur = pnl_pct = valeur = None

        score  = 0.0
        signal = "SURVEILLER"

        if with_scores:
            try:
                r     = orchestrer(ticker, with_llm=False)
                score = r["scoring"]["score_final"]
            except Exception:
                pass

        if pnl_pct is not None:
            signal = _signal_sortie(pnl_pct, score)

        # Date du premier achat
        achats = [t for t in pos.get("transactions", []) if t["type"] == "achat"]
        date_premier_achat = min((t["date"] for t in achats), default=None)
        try:
            jours = (datetime.now() - datetime.strptime(date_premier_achat, "%Y-%m-%d")).days \
                    if date_premier_achat else None
        except Exception:
            jours = None

        resultats.append({
            "ticker":       ticker,
            "quantite":     quantite,
            "prix_moyen":   prix_moyen,
            "prix_actuel":  prix_now,
            "valeur":       valeur,
            "investi":      investi,
            "pnl_eur":      pnl_eur,
            "pnl_pct":      pnl_pct,
            "jours":        jours,
            "date_achat":   date_premier_achat,
            "score":        round(score, 4),
            "signal_sortie":signal,
        })

    return resultats
