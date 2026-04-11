import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

const BROKERS: Record<string, { frais: string; note: string }> = {
  'Trade Republic':   { frais: '1 € fixe par ordre, tous marchés, 24h/24', note: '' },
  'Degiro':          { frais: '2 € + 0.038% (actions EU)', note: '' },
  'Boursorama':      { frais: '1.99 € min (web)', note: '' },
  'Fortuneo':        { frais: '7.5 € min', note: '' },
  'Interactive Brokers': { frais: '0.35% min 0.35 USD', note: '' },
  'Autre / Manuel':  { frais: 'Frais à saisir manuellement', note: '' },
};

const REGIMES = [
  { key: 'pfu',    label: 'PFU 30 % — Flat tax (défaut)',        taux: 30 },
  { key: 'bareme', label: 'Barème progressif (IR + 17.2 % PS)',   taux: null },
  { key: 'pea',    label: 'PEA après 5 ans (17.2 % PS uniquement)', taux: 17.2 },
];

@Component({
  selector: 'app-portfolio',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './portfolio.component.html',
  styleUrl: './portfolio.component.scss',
})
export class PortfolioComponent implements OnInit {
  // State
  positions   = signal<any[]>([]);
  historique  = signal<any[]>([]);
  loading     = signal(false);
  analyzing   = signal(false);
  error       = signal('');
  toast       = signal('');

  // Settings
  brokers       = Object.keys(BROKERS);
  brokerInfo    = BROKERS;
  regimes       = REGIMES;
  selectedBroker = 'Trade Republic';
  selectedRegime = 'pfu';
  tmi            = 30;
  modeRapide     = true;

  // UI toggles
  showBroker  = false;
  showAchat   = false;
  expandedPos: Record<string, 'none' | 'objectifs' | 'vente' | 'transactions'> = {};
  posTransactions: Record<string, any[]> = {};

  // Achat form
  achat = { ticker: '', prix: 0, quantite: 1, date: '', frais: 1, notes: '' };

  // Vente form
  vente: Record<string, { qty: number; prix: number; date: string; notes: string; frais: number }> = {};

  // Objectifs form
  objectifs: Record<string, { stop: number; cible: number }> = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadPositions();
    this.api.getHistorique().subscribe({ next: h => this.historique.set(h), error: () => {} });
  }

  loadPositions(): void {
    this.loading.set(true);
    this.api.getPositions().subscribe({
      next: p => { this.positions.set(p); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur'); this.loading.set(false); },
    });
  }

  analyserPositions(): void {
    this.analyzing.set(true);
    this.error.set('');
    this.api.evaluatePositions(!this.modeRapide).subscribe({
      next: p => { this.positions.set(p); this.analyzing.set(false); this._toast('Positions mises à jour.'); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur'); this.analyzing.set(false); },
    });
  }

  submitAchat(): void {
    this.api.addAchat({ ...this.achat, broker_key: this.selectedBroker }).subscribe({
      next: () => {
        this.showAchat = false;
        this.achat = { ticker: '', prix: 0, quantite: 1, date: '', frais: 1, notes: '' };
        this.loadPositions();
        this._toast('Achat enregistré.');
      },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  submitVente(ticker: string, pos: any): void {
    const v = this.vente[ticker];
    if (!v) return;
    this.api.addVente({ ticker, prix_vente: v.prix, quantite: v.qty, date: v.date, notes: v.notes, frais: v.frais }).subscribe({
      next: () => {
        this.expandedPos[ticker] = 'none';
        this.loadPositions();
        this.api.getHistorique().subscribe({ next: h => this.historique.set(h), error: () => {} });
        this._toast(`Vente ${ticker} enregistrée.`);
      },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  submitObjectifs(ticker: string): void {
    const o = this.objectifs[ticker];
    if (!o) return;
    this.api.setObjectifs({ ticker, stop_loss_pct: o.stop, cible_pct: o.cible }).subscribe({
      next: () => { this.expandedPos[ticker] = 'none'; this._toast('Objectifs enregistrés.'); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  supprimerPosition(ticker: string): void {
    if (!confirm(`Supprimer la position ${ticker} sans historique ?`)) return;
    this.api.deletePosition(ticker).subscribe({
      next: () => { this.loadPositions(); this._toast(`${ticker} supprimé.`); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  toggleExpand(ticker: string, mode: 'objectifs' | 'vente' | 'transactions', pos: any): void {
    if (this.expandedPos[ticker] === mode) {
      this.expandedPos[ticker] = 'none';
      return;
    }
    this.expandedPos[ticker] = mode;
    if (mode === 'vente') {
      this.vente[ticker] = { qty: pos.quantite, prix: pos.prix_actuel ?? pos.prix_moyen, date: '', notes: '', frais: 1 };
    }
    if (mode === 'objectifs') {
      this.objectifs[ticker] = { stop: pos.stop_loss_pct ?? -8, cible: pos.cible_pct ?? 15 };
    }
    if (mode === 'transactions' && !this.posTransactions[ticker]) {
      this.api.getTransactions(ticker).subscribe({ next: t => this.posTransactions[ticker] = t, error: () => {} });
    }
  }

  // Stats
  get totalInvesti(): number { return this.positions().reduce((s, p) => s + (p.prix_moyen * p.quantite), 0); }
  get totalValeur(): number  { return this.positions().reduce((s, p) => s + (p.valeur ?? p.prix_moyen * p.quantite), 0); }
  get totalPnl(): number     { return this.totalValeur - this.totalInvesti; }
  get totalPnlPct(): number  { return this.totalInvesti ? (this.totalPnl / this.totalInvesti) * 100 : 0; }
  get nbVendre(): number     { return this.positions().filter(p => p.signal_sortie === 'VENDRE').length; }
  get nbSurveiller(): number { return this.positions().filter(p => p.signal_sortie === 'SURVEILLER').length; }

  // Historique stats
  get hTrades(): number    { return this.historique().length; }
  get hWins(): number      { return this.historique().filter((h: any) => h.pnl_net > 0).length; }
  get hWinRate(): string   { return this.hTrades ? ((this.hWins / this.hTrades) * 100).toFixed(0) : '0'; }
  get hPnlTotal(): number  { return this.historique().reduce((s: number, h: any) => s + (h.pnl_net ?? 0), 0); }
  get hFraisTotal(): number { return this.historique().reduce((s: number, h: any) => s + (h.frais ?? 0), 0); }

  pnlClass(v: number | null): string {
    if (v === null || v === undefined) return '';
    return v > 0 ? 'pos' : v < 0 ? 'neg' : '';
  }

  signalIcon(s: string): string {
    if (!s) return '—';
    if (s === 'ACHETER' || s === 'TENIR') return '🟢';
    if (s === 'VENDRE')                   return '🔴';
    return '🟡';
  }

  get currentRegimeTaux(): number {
    if (this.selectedRegime === 'pfu')    return 30;
    if (this.selectedRegime === 'pea')    return 17.2;
    return this.tmi + 17.2;
  }

  private _toast(msg: string): void {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(''), 3500);
  }
}
