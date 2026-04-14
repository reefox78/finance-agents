import { Component, OnInit, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize, timeout, catchError, debounceTime, distinctUntilChanged, switchMap } from 'rxjs/operators';
import { of, Subject, Subscription } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';
import {
  WATCHLIST, WATCHLIST_CATEGORIES, TICKER_NAMES, tickerLabel,
  BROKER_CALC, BROKERS_INFO,
} from '../../core/constants/watchlist';

const REGIMES = [
  { key: 'pfu',    label: 'PFU 30 % — Flat tax (défaut)',          taux: 30 },
  { key: 'bareme', label: 'Barème progressif (IR + 17.2 % PS)',     taux: null },
  { key: 'pea',    label: 'PEA après 5 ans (17.2 % PS uniquement)', taux: 17.2 },
];

@Component({
  selector: 'app-portfolio',
  standalone: true,
  imports: [CommonModule, FormsModule, LoadingOverlayComponent],
  templateUrl: './portfolio.component.html',
  styleUrl: './portfolio.component.scss',
})
export class PortfolioComponent implements OnInit, OnDestroy {

  // ── State ──────────────────────────────────────────────────────────────────
  positions  = signal<any[]>([]);
  historique = signal<any[]>([]);
  loading        = signal(false);
  analyzing      = signal(false);
  analyzingError = signal('');
  error          = signal('');
  toast          = signal('');

  private _analysisSub: Subscription | null = null;

  // ── Broker / Fiscal settings ───────────────────────────────────────────────
  brokerList    = Object.keys(BROKERS_INFO);
  brokersInfo   = BROKERS_INFO;
  regimes       = REGIMES;
  selectedBroker = 'Trade Republic';
  selectedRegime = 'pfu';
  tmi            = 30;
  modeRapide     = true;

  // ── Watchlist (shared) ────────────────────────────────────────────────────
  watchlist  = WATCHLIST;
  categories = WATCHLIST_CATEGORIES;
  tickerLabel = tickerLabel;
  tickerNames = TICKER_NAMES;

  // ── UI toggles ────────────────────────────────────────────────────────────
  showBroker  = false;
  showAchat   = false;
  expandedPos: Record<string, 'none' | 'objectifs' | 'vente' | 'transactions'> = {};
  posTransactions: Record<string, any[]> = {};

  // ── Achat form ────────────────────────────────────────────────────────────
  achat = { ticker: '', customTicker: '', prix: 0, quantite: 1, date: '', frais: 1, notes: '' };
  prixLoading = false;
  private _tickerChange$ = new Subject<string>();

  // ── Vente / Objectifs ─────────────────────────────────────────────────────
  vente: Record<string, { qty: number; prix: number; date: string; notes: string; frais: number }> = {};
  objectifs: Record<string, { stop: number; cible: number }> = {};

  // ── Modal historique analyses ─────────────────────────────────────────────
  histoModal = signal({
    show: false, ticker: '', loading: false,
    entries: [] as any[], selected: null as any,
  });

  readonly AGENT_LABELS: Record<string, string> = {
    technique: 'Technique', fondamental: 'Fondamental', sentiment: 'Sentiment',
    trends: 'Tendances', insider: 'Insider', macro: 'Macro',
    options_flow: 'Options Flow', sec_filings: 'SEC Filings',
    short_interest: 'Short Interest', earnings_surprise: 'Earnings',
    volume_delta: 'Volume Delta',
  };

  constructor(private api: ApiService, private route: ActivatedRoute, private router: Router) {}

  ngOnDestroy(): void { this._analysisSub?.unsubscribe(); }

  ngOnInit(): void {
    this.loadPositions();
    this.api.getHistorique().subscribe({ next: h => this.historique.set(h), error: () => {} });

    // Auto-fill prix actuel quand le ticker change (debounce 400 ms)
    this._tickerChange$.pipe(
      debounceTime(400),
      distinctUntilChanged(),
      switchMap(ticker => {
        if (!ticker) return of(null);
        this.prixLoading = true;
        return this.api.getPrix(ticker).pipe(catchError(() => of(null)));
      }),
    ).subscribe(res => {
      this.prixLoading = false;
      if (res?.prix) {
        this.achat.prix = res.prix;
        this._autoFrais();
      }
    });

    // Pré-remplissage depuis la page Analyse (query params)
    this.route.queryParams.subscribe(params => {
      if (params['achat'] === '1' && params['ticker']) {
        this.showAchat = true;
        this.achat.ticker = params['ticker'];
        const prixParam = parseFloat(params['prix']);
        if (!isNaN(prixParam)) {
          this.achat.prix = prixParam;
          this._autoFrais();
        } else {
          this._fetchPrix(params['ticker']);
        }
        setTimeout(() => document.querySelector('.expander')?.scrollIntoView({ behavior: 'smooth' }), 300);
      }
    });
  }

  /** Déclenche la récupération du prix pour un ticker donné. */
  private _fetchPrix(ticker: string): void {
    if (ticker) this._tickerChange$.next(ticker);
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
    this.analyzingError.set('');
    this.error.set('');
    this._analysisSub = this.api.evaluatePositions(!this.modeRapide).subscribe({
      next: p => { this.positions.set(p); this.analyzing.set(false); this._toast('Positions mises à jour.'); },
      error: e => {
        const status = e.status ? ` (${e.status})` : '';
        this.analyzingError.set((e.error?.detail ?? 'Erreur serveur') + status);
      },
    });
  }

  cancelAnalysis(): void {
    this._analysisSub?.unsubscribe();
    this._analysisSub = null;
    this.analyzing.set(false);
    this.analyzingError.set('');
  }

  // ── Frais broker auto ─────────────────────────────────────────────────────

  /** Ticker effectif (select ou custom) */
  get effectiveTicker(): string {
    return this.achat.customTicker?.trim().toUpperCase() || this.achat.ticker;
  }

  onAchatChange(): void {
    this._autoFrais();
    this._fetchPrix(this.effectiveTicker);
  }

  onTickerSelect(): void {
    this._fetchPrix(this.effectiveTicker);
  }

  private _autoFrais(): void {
    const montant = this.achat.prix * this.achat.quantite;
    const calc = BROKER_CALC[this.selectedBroker];
    if (calc && this.selectedBroker !== 'Autre / Manuel') {
      this.achat.frais = calc(montant);
    }
  }

  get fraisEstimes(): number {
    return BROKER_CALC[this.selectedBroker]?.(this.achat.prix * this.achat.quantite) ?? 0;
  }

  get brokerDescription(): string {
    return this.brokersInfo[this.selectedBroker] ?? '';
  }

  // ── Fiscalité ─────────────────────────────────────────────────────────────

  get currentRegimeTaux(): number {
    if (this.selectedRegime === 'pfu')    return 30;
    if (this.selectedRegime === 'pea')    return 17.2;
    return this.tmi + 17.2;
  }

  impotEstime(ticker: string, pos: any): number {
    const v = this.vente[ticker];
    if (!v?.prix || !v?.qty) return 0;
    const prixAchat = pos.prix_moyen ?? 0;
    const plusvalue = (v.prix - prixAchat) * v.qty - (v.frais ?? 0);
    if (plusvalue <= 0) return 0;
    return Math.round(plusvalue * (this.currentRegimeTaux / 100) * 100) / 100;
  }

  netApresImpot(ticker: string, pos: any): number {
    const v = this.vente[ticker];
    if (!v?.prix || !v?.qty) return 0;
    const brut = (v.prix - (pos.prix_moyen ?? 0)) * v.qty - (v.frais ?? 0);
    return Math.round((brut - this.impotEstime(ticker, pos)) * 100) / 100;
  }

  // ── Submit ────────────────────────────────────────────────────────────────

  submitAchat(): void {
    const ticker = this.effectiveTicker;
    if (!ticker) { this.error.set('Veuillez choisir ou saisir un ticker.'); return; }
    this.api.addAchat({ ...this.achat, ticker, broker_key: this.selectedBroker }).subscribe({
      next: () => {
        this.showAchat = false;
        this.achat = { ticker: '', customTicker: '', prix: 0, quantite: 1, date: '', frais: 1, notes: '' };
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
    if (!confirm(`Supprimer la position ${ticker} ?`)) return;
    this.api.deletePosition(ticker).subscribe({
      next: () => { this.loadPositions(); this._toast(`${ticker} supprimé.`); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  toggleExpand(ticker: string, mode: 'objectifs' | 'vente' | 'transactions', pos: any): void {
    if (this.expandedPos[ticker] === mode) { this.expandedPos[ticker] = 'none'; return; }
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

  // ── Stats ─────────────────────────────────────────────────────────────────
  get totalInvesti(): number  { return this.positions().reduce((s, p) => s + p.prix_moyen * p.quantite, 0); }
  get totalValeur(): number   { return this.positions().reduce((s, p) => s + (p.valeur ?? p.prix_moyen * p.quantite), 0); }
  get totalPnl(): number      { return this.totalValeur - this.totalInvesti; }
  get totalPnlPct(): number   { return this.totalInvesti ? (this.totalPnl / this.totalInvesti) * 100 : 0; }
  get nbVendre(): number      { return this.positions().filter(p => p.signal_sortie === 'VENDRE').length; }
  get nbSurveiller(): number  { return this.positions().filter(p => p.signal_sortie === 'SURVEILLER').length; }

  get hTrades(): number     { return this.historique().length; }
  get hWins(): number       { return this.historique().filter((h: any) => h.pnl_net > 0).length; }
  get hWinRate(): string    { return this.hTrades ? ((this.hWins / this.hTrades) * 100).toFixed(0) : '0'; }
  get hPnlTotal(): number   { return this.historique().reduce((s: number, h: any) => s + (h.pnl_net ?? 0), 0); }
  get hFraisTotal(): number { return this.historique().reduce((s: number, h: any) => s + (h.frais ?? 0), 0); }

  pnlClass(v: number | null): string {
    if (v == null) return '';
    return v > 0 ? 'pos' : v < 0 ? 'neg' : '';
  }

  signalIcon(s: string): string {
    if (!s) return '—';
    if (s === 'VENDRE') return '🔴';
    if (s === 'SURVEILLER') return '🟡';
    return '🟢';
  }

  // ── Modal ─────────────────────────────────────────────────────────────────

  openHistoModal(ticker: string): void {
    this.histoModal.set({ show: true, ticker, loading: true, entries: [], selected: null });
    this.api.getAnalyseHistory(ticker).pipe(
      timeout(12000),
      catchError(() => of([])),
      finalize(() => this.histoModal.update(m => ({ ...m, loading: false }))),
    ).subscribe(entries => {
      const list = Array.isArray(entries) ? entries : [];
      this.histoModal.update(m => ({ ...m, entries: list, selected: list[0] ?? null }));
    });
  }

  closeHistoModal(): void { this.histoModal.update(m => ({ ...m, show: false })); }

  selectEntry(entry: any): void { this.histoModal.update(m => ({ ...m, selected: entry })); }

  goToAnalyse(ticker: string): void {
    this.closeHistoModal();
    this.router.navigate(['/analyse'], { queryParams: { ticker } });
  }

  agentEntries(scores: Record<string, number>): { key: string; label: string; score: number }[] {
    return Object.entries(scores)
      .filter(([k]) => this.AGENT_LABELS[k])
      .map(([k, v]) => ({ key: k, label: this.AGENT_LABELS[k], score: v }))
      .sort((a, b) => Math.abs(b.score) - Math.abs(a.score));
  }

  agentBarPct(score: number): string {
    return Math.min(100, Math.abs(score) * 100).toFixed(1) + '%';
  }

  agentBarColor(score: number): string {
    if (score > 0.05)  return 'rgba(46,204,113,0.7)';
    if (score < -0.05) return 'rgba(231,76,60,0.7)';
    return 'rgba(241,196,15,0.5)';
  }

  decisionColor(d: string): string {
    if (d === 'ACHETER') return '#2ecc71';
    if (d === 'VENDRE')  return '#e74c3c';
    return '#f1c40f';
  }

  formatTs(ts: string): string {
    try {
      const d = new Date(ts);
      return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
           + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
  }

  private _toast(msg: string): void {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(''), 3500);
  }
}
