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

def calculer_cump(qty_avant: float, pm_avant: float,
                  qty_achat: float, prix: float, frais: float = 0.0) -> tuple[float, float]:
    """
    Formule pure du CUMP (Coût Unitaire Moyen Pondéré).

    Calcule le nouveau CUMP après un achat en partant de l'état COURANT
    de la position (qty_avant, pm_avant) — sans relire l'historique des
    transactions.  Cela garantit un résultat correct même après des
    ventes partielles.

    Args:
        qty_avant : quantité détenue avant cet achat
        pm_avant  : CUMP actuel avant cet achat
        qty_achat : quantité du nouvel achat
        prix      : prix unitaire du nouvel achat
        frais     : frais d'achat (majorent le coût de revient)

    Returns:
        (nouveau_qty, nouveau_cump)

    Exemples:
        Premier achat 10 @ 100 frais=1 :
            calculer_cump(0, 0, 10, 100, 1) → (10.0, 100.1)

        Deuxième achat après vente partielle (5 restants @ CUMP 100, achat 5 @ 80) :
            calculer_cump(5, 100, 5, 80) → (10.0, 90.0)
    """
    nouveau_qty = qty_avant + qty_achat
    if nouveau_qty <= 0:
        return 0.0, 0.0
    nouveau_pm = (qty_avant * pm_avant + qty_achat * prix + frais) / nouveau_qty
    return round(nouveau_qty, 6), round(nouveau_pm, 6)


def calculer_pnl(prix_vente: float, prix_moyen: float,
                 quantite: float, frais: float = 0.0) -> dict:
    """
    Calcule le P&L d'une vente.

    P&L brut = (prix_vente − CUMP) × quantité
    P&L net  = P&L brut − frais de vente
    P&L %    = P&L net / (CUMP × quantité) × 100

    Returns:
        dict avec pnl_brut (€), pnl_net (€), pnl_pct (%)
    """
    pnl_brut = round((prix_vente - prix_moyen) * quantite, 2)
    pnl_net  = round(pnl_brut - frais, 2)
    pnl_pct  = round(pnl_net / (prix_moyen * quantite) * 100, 2) \
               if prix_moyen > 0 and quantite > 0 else 0.0
    return {"pnl_brut": pnl_brut, "pnl_net": pnl_net, "pnl_pct": pnl_pct}


def _appliquer_achat(position: dict, tx: dict) -> None:
    """
    Met à jour le prix moyen pondéré après un achat.
    Délègue à calculer_cump() — formule standard AMF/Boursorama.
    """
    nouveau_qty, nouveau_pm = calculer_cump(
        position["quantite"], position["prix_moyen"],
        tx["quantite"], tx["prix"], tx.get("frais", 0.0),
    )
    position["quantite"]    = nouveau_qty
    position["prix_moyen"]  = nouveau_pm
    position["transactions"].append(tx)


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def ajouter_achat(ticker: str, prix: float, quantite: float,
                  date: str = None, notes: str = "", frais: float = 0.0,
                  broker_key: str = None) -> dict:
    """
    Enregistre un achat. Recalcule le CUMP (frais inclus) si la position existe déjà.
    broker_key : identifiant du broker utilisé (ex: "trade_republic") — stocké sur la
                 position pour être réutilisé dans la simulation des objectifs.
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

    # Mémorise le broker du premier achat (ou met à jour si fourni)
    if broker_key:
        data["positions"][ticker]["broker_key"] = broker_key

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
    pnl              = calculer_pnl(float(prix_vente), prix_moyen_achat, quantite, frais)
    pnl_brut         = pnl["pnl_brut"]
    pnl_eur          = pnl["pnl_net"]
    pnl_pct          = pnl["pnl_pct"]

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


def supprimer_vente(vente_id: str) -> bool:
    """
    Supprime une vente de l'historique par son ID.
    N'affecte PAS les positions ouvertes (action purement comptable).
    Retourne True si la vente a été trouvée et supprimée.
    """
    data  = _charger()
    avant = len(data["historique_ventes"])
    data["historique_ventes"] = [v for v in data["historique_ventes"] if v["id"] != vente_id]
    if len(data["historique_ventes"]) < avant:
        _sauvegarder(data)
        return True
    return False


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


def definir_objectifs(ticker: str,
                      cible_pct: float | None = None,
                      stop_loss_pct: float | None = None) -> dict:
    """
    Définit la cible de gain et/ou le stop-loss d'une position.
    Ces seuils sont propres à chaque position et prioritaires sur les seuils globaux.

    Args:
        ticker        : symbole de la position (ex: "AAPL")
        cible_pct     : gain visé en % (ex: 15.0 → vendre si +15%)
        stop_loss_pct : perte maximale tolérée en % négatif (ex: -8.0)

    Returns:
        La position mise à jour.
    """
    data   = _charger()
    ticker = ticker.upper().strip()
    pos    = data["positions"].get(ticker)
    if pos is None:
        raise ValueError(f"Position {ticker} introuvable")
    if cible_pct is not None:
        pos["cible_pct"] = round(float(cible_pct), 2)
    if stop_loss_pct is not None:
        pos["stop_loss_pct"] = round(float(stop_loss_pct), 2)
    _sauvegarder(data)
    return pos


def lister_historique() -> list[dict]:
    """Retourne toutes les ventes du plus récent au plus ancien."""
    hist = _charger()["historique_ventes"]
    return sorted(hist, key=lambda x: x.get("date", ""), reverse=True)


def modifier_note_transaction(ticker: str, tx_id: str, note: str) -> None:
    """Met à jour la note d'une transaction identifiée par son id."""
    data   = _charger()
    ticker = ticker.upper().strip()
    pos    = data["positions"].get(ticker, {})
    for tx in pos.get("transactions", []):
        if tx.get("id") == tx_id:
            tx["notes"] = note.strip()
            break
    _sauvegarder(data)


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


def _signal_sortie(pnl_pct: float, score: float,
                   stop_loss_pct: float = -8.0,
                   cible_pct: float = None) -> str:
    if pnl_pct <= stop_loss_pct or score <= -0.10:
        return "VENDRE"
    if cible_pct is not None and pnl_pct >= cible_pct:
        return "VENDRE"   # cible atteinte → prendre les bénéfices
    if pnl_pct <= stop_loss_pct / 2 or score <= 0.05:
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

        stop_loss_pct = pos.get("stop_loss_pct", -8.0)
        cible_pct     = pos.get("cible_pct", None)
        if pnl_pct is not None:
            signal = _signal_sortie(pnl_pct, score, stop_loss_pct, cible_pct)

        # Date du premier achat
        achats = [t for t in pos.get("transactions", []) if t["type"] == "achat"]
        date_premier_achat = min((t["date"] for t in achats), default=None)
        try:
            jours = (datetime.now() - datetime.strptime(date_premier_achat, "%Y-%m-%d")).days \
                    if date_premier_achat else None
        except Exception:
            jours = None

        resultats.append({
            "ticker":        ticker,
            "quantite":      quantite,
            "prix_moyen":    prix_moyen,
            "prix_actuel":   prix_now,
            "valeur":        valeur,
            "investi":       investi,
            "pnl_eur":       pnl_eur,
            "pnl_pct":       pnl_pct,
            "jours":         jours,
            "date_achat":    date_premier_achat,
            "score":         round(score, 4),
            "signal_sortie": signal,
            "cible_pct":     cible_pct,
            "stop_loss_pct": stop_loss_pct,
            # Prix absolus correspondants (calculés depuis le CUMP)
            "prix_cible":    round(prix_moyen * (1 + cible_pct / 100), 4)     if cible_pct     else None,
            "prix_stop":     round(prix_moyen * (1 + stop_loss_pct / 100), 4) if stop_loss_pct else None,
        })

    return resultats
