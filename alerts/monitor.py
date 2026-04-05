"""
Moteur de surveillance des positions ouvertes.
Génère des alertes selon les seuils configurés dans config/alerts.json.

Types d'alertes :
  STOP_LOSS      → P&L < seuil_stop_loss  (ex: -8%)   — critique, sortir
  ALERTE_PNL     → P&L < seuil_alerte     (ex: -4%)   — surveiller
  CIBLE_ATTEINTE → P&L > seuil_cible      (ex: +15%)  — prendre les bénéfices
  SCORE_VENDRE   → score agent < -0.10               — signal de vente
  SCORE_SURVEILLER → score entre -0.10 et 0.05       — attention
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.portfolio import lister_positions, _prix_actuel
from data.alerts_store import creer_alerte, lister_alertes

CONFIG_PATH = Path("config/alerts.json")


def _charger_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "seuils": {
                "pnl_stop_loss_pct": -8.0,
                "pnl_alerte_pct":    -4.0,
                "score_vendre":      -0.10,
                "score_surveiller":   0.05,
                "pnl_cible_pct":     15.0,
            }
        }


def verifier_positions(with_scores: bool = False) -> list[dict]:
    """
    Vérifie toutes les positions ouvertes et génère les alertes nécessaires.

    with_scores=False : vérification rapide basée sur le P&L uniquement (pas d'API externe).
    with_scores=True  : inclut le scoring multi-agents (plus lent, appels yfinance/FRED).

    Retourne la liste des nouvelles alertes créées.
    """
    config  = _charger_config()
    seuils  = config["seuils"]
    positions = lister_positions()
    nouvelles = []

    for pos in positions:
        ticker     = pos["ticker"]
        prix_moyen = pos["prix_moyen"]
        quantite   = pos["quantite"]

        # --- Prix actuel & P&L ---
        prix_now = _prix_actuel(ticker)
        if prix_now is None:
            continue

        pnl_pct = round((prix_now - prix_moyen) / prix_moyen * 100, 2)
        pnl_eur = round((prix_now - prix_moyen) * quantite, 2)

        # --- Stop-loss ---
        if pnl_pct <= seuils["pnl_stop_loss_pct"]:
            a = creer_alerte(
                ticker=ticker,
                type_alerte="STOP_LOSS",
                niveau="CRITIQUE",
                message=(f"{ticker} a perdu {pnl_pct:+.1f}% depuis ton CUMP "
                         f"({prix_moyen:.2f} → {prix_now:.2f}). "
                         f"Stop-loss à {seuils['pnl_stop_loss_pct']}% déclenché."),
                details={"pnl_pct": pnl_pct, "pnl_eur": pnl_eur,
                         "prix_moyen": prix_moyen, "prix_actuel": prix_now},
            )
            if a not in nouvelles:
                nouvelles.append(a)

        # --- Alerte P&L (pré-stop-loss) ---
        elif pnl_pct <= seuils["pnl_alerte_pct"]:
            a = creer_alerte(
                ticker=ticker,
                type_alerte="ALERTE_PNL",
                niveau="SURVEILLER",
                message=(f"{ticker} est en perte de {pnl_pct:+.1f}% "
                         f"({pnl_eur:+.2f}). "
                         f"Stop-loss à {seuils['pnl_stop_loss_pct']}% non encore atteint."),
                details={"pnl_pct": pnl_pct, "pnl_eur": pnl_eur,
                         "prix_moyen": prix_moyen, "prix_actuel": prix_now},
            )
            if a not in nouvelles:
                nouvelles.append(a)

        # --- Cible de gain atteinte ---
        if pnl_pct >= seuils["pnl_cible_pct"]:
            a = creer_alerte(
                ticker=ticker,
                type_alerte="CIBLE_ATTEINTE",
                niveau="INFO",
                message=(f"{ticker} a atteint +{pnl_pct:.1f}% de gain "
                         f"({pnl_eur:+.2f}). "
                         f"Objectif de +{seuils['pnl_cible_pct']}% atteint — envisager la prise de bénéfices."),
                details={"pnl_pct": pnl_pct, "pnl_eur": pnl_eur,
                         "prix_moyen": prix_moyen, "prix_actuel": prix_now},
            )
            if a not in nouvelles:
                nouvelles.append(a)

        # --- Score agents (si demandé) ---
        if with_scores:
            try:
                from orchestrator.orchestrator import run as orchestrer
                r     = orchestrer(ticker, with_llm=False)
                score = r["scoring"]["score_final"]

                if score <= seuils["score_vendre"]:
                    a = creer_alerte(
                        ticker=ticker,
                        type_alerte="SCORE_VENDRE",
                        niveau="VENDRE",
                        message=(f"Les agents recommandent de vendre {ticker} "
                                 f"(score : {score:+.4f}). "
                                 f"Seuil de vente : {seuils['score_vendre']}."),
                        details={"score": score, "decision": r["scoring"]["decision"]},
                    )
                    if a not in nouvelles:
                        nouvelles.append(a)

                elif score <= seuils["score_surveiller"]:
                    a = creer_alerte(
                        ticker=ticker,
                        type_alerte="SCORE_SURVEILLER",
                        niveau="SURVEILLER",
                        message=(f"Le score de {ticker} se dégrade "
                                 f"(score : {score:+.4f}). À surveiller."),
                        details={"score": score},
                    )
                    if a not in nouvelles:
                        nouvelles.append(a)

            except Exception:
                pass

    return nouvelles


def envoyer_email_si_configure(alertes: list[dict]) -> bool:
    """
    Envoie un email récapitulatif si l'email est configuré et activé.
    Retourne True si l'email a été envoyé, False sinon.
    """
    config = _charger_config()
    email_cfg = config.get("email", {})

    if not email_cfg.get("enabled", False):
        return False
    if not email_cfg.get("destinataire", ""):
        return False
    if not alertes:
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        lignes = []
        for a in alertes:
            icone = {"CRITIQUE": "🔴", "VENDRE": "🔴", "SURVEILLER": "🟡", "INFO": "🔵"}.get(a["niveau"], "⚪")
            lignes.append(f"{icone} [{a['ticker']}] {a['message']}")

        corps = "\n\n".join(lignes)
        corps += "\n\n---\nFinance Agents — Système d'alertes automatiques"

        msg = MIMEMultipart()
        msg["From"]    = email_cfg["expediteur"]
        msg["To"]      = email_cfg["destinataire"]
        msg["Subject"] = f"[Finance Agents] {len(alertes)} alerte(s) — {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        msg.attach(MIMEText(corps, "plain", "utf-8"))

        with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as server:
            server.starttls()
            server.login(email_cfg["expediteur"], email_cfg["smtp_password"])
            server.send_message(msg)

        return True

    except Exception as e:
        print(f"[Alertes] Erreur email : {e}")
        return False


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Vérification manuelle des positions...")
    nouvelles = verifier_positions(with_scores=False)
    if nouvelles:
        print(f"  {len(nouvelles)} nouvelle(s) alerte(s) :")
        for a in nouvelles:
            print(f"  → [{a['niveau']}] {a['message']}")
    else:
        print("  Aucune alerte déclenchée.")
