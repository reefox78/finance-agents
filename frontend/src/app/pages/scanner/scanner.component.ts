import { Component, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Router } from '@angular/router';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';
import { WATCHLIST, TICKER_NAMES } from '../../core/constants/watchlist';

interface ScanResult {
  ticker:    string;
  score:     number;
  decision:  string;
  technique?: number;
  risque?:   number;
}

interface ScanError {
  ticker: string;
  error:  string;
}

@Component({
  selector: 'app-scanner',
  standalone: true,
  imports: [CommonModule, FormsModule, LoadingOverlayComponent],
  templateUrl: './scanner.component.html',
  styleUrl: './scanner.component.scss',
})
export class ScannerComponent implements OnDestroy {

  // ── Mode ──────────────────────────────────────────────────────────────────
  mode: 'watchlist' | 'custom' = 'watchlist';

  // ── Mode watchlist ────────────────────────────────────────────────────────
  categorie = 'us_stocks';
  minScore  = -1;   // défaut -1 = tout afficher

  // ── Mode custom — sélection ───────────────────────────────────────────────
  tickerSearch    = '';
  selectedTickers = new Set<string>();   // tickers cochés dans la checklist
  basket: string[] = [];                 // panier validé (ordre de la sélection)
  customInput     = '';                  // saisie ticker manuel

  /** Groupes de la watchlist pour la checklist */
  readonly watchlistGroups = Object.entries(WATCHLIST).map(([label, tickers]) => ({
    label,
    tickers,
  }));

  get filteredGroups() {
    const q = this.tickerSearch.trim().toLowerCase();
    if (!q) return this.watchlistGroups;
    return this.watchlistGroups.map(g => ({
      label: g.label,
      tickers: g.tickers.filter(t =>
        t.toLowerCase().includes(q) ||
        (TICKER_NAMES[t] ?? '').toLowerCase().includes(q)
      ),
    })).filter(g => g.tickers.length > 0);
  }

  tickerName(t: string): string {
    return TICKER_NAMES[t] ?? '';
  }

  toggleTicker(t: string): void {
    if (this.selectedTickers.has(t)) {
      this.selectedTickers.delete(t);
    } else {
      this.selectedTickers.add(t);
    }
  }

  selectAll(tickers: string[]): void {
    tickers.forEach(t => this.selectedTickers.add(t));
  }

  deselectAll(tickers: string[]): void {
    tickers.forEach(t => this.selectedTickers.delete(t));
  }

  allSelected(tickers: string[]): boolean {
    return tickers.length > 0 && tickers.every(t => this.selectedTickers.has(t));
  }

  addToBasket(): void {
    // Ajoute les tickers cochés qui ne sont pas déjà dans le panier
    for (const t of this.selectedTickers) {
      if (!this.basket.includes(t)) this.basket.push(t);
    }
    this.selectedTickers.clear();
  }

  addCustomTicker(): void {
    const t = this.customInput.trim().toUpperCase();
    if (!t) return;
    if (!this.basket.includes(t)) this.basket.push(t);
    this.customInput = '';
  }

  removeFromBasket(t: string): void {
    this.basket = this.basket.filter(x => x !== t);
  }

  clearBasket(): void { this.basket = []; }

  moveUp(i: number): void {
    if (i === 0) return;
    [this.basket[i - 1], this.basket[i]] = [this.basket[i], this.basket[i - 1]];
    this.basket = [...this.basket];
  }

  // ── Scan state ────────────────────────────────────────────────────────────
  loading      = signal(false);
  progress     = signal<{ current: number; total: number; ticker: string } | null>(null);
  results      = signal<ScanResult[]>([]);
  allResults   = signal<ScanResult[]>([]);
  scanErrors   = signal<ScanError[]>([]);
  error        = signal('');
  overlayError = signal('');
  scanDone     = signal(false);
  scanTotal    = signal(0);
  showErrors   = false;

  private es: EventSource | null = null;
  private _done = false;

  constructor(private api: ApiService, private auth: AuthService, private router: Router) {}

  goToAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  get canScan(): boolean {
    if (this.loading()) return false;
    if (this.mode === 'custom') return this.basket.length > 0;
    return true;
  }

  startScan(): void {
    if (!this.canScan) return;
    this.error.set('');
    this.overlayError.set('');
    this.results.set([]);
    this.allResults.set([]);
    this.scanErrors.set([]);
    this.loading.set(true);
    this.progress.set(null);
    this.scanDone.set(false);
    this.showErrors = false;
    this._done = false;

    const token = this.auth.token ?? '';
    let base: string;

    if (this.mode === 'custom') {
      // On passe la liste de tickers du panier via le paramètre tickers
      base = this.api.scannerStreamUrl(undefined, this.basket.join(','), -1);
    } else {
      base = this.api.scannerStreamUrl(this.categorie || undefined, undefined, -1);
    }

    const url = `${base}&token=${encodeURIComponent(token)}`;
    this.es?.close();
    this.es = new EventSource(url);

    this.es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'progress') {
          this.progress.set({ current: msg.current, total: msg.total, ticker: msg.ticker });
          this.scanTotal.set(msg.total);
        } else if (msg.type === 'done') {
          this._done = true;
          const all: ScanResult[] = msg.resultats ?? [];
          const errs: ScanError[] = msg.erreurs   ?? [];
          this.allResults.set(all);
          this.scanErrors.set(errs);
          this.results.set(all.filter(r => r.score >= this.minScore));
          this.loading.set(false);
          this.progress.set(null);
          this.scanDone.set(true);
          this.es?.close();
          this.es = null;
        }
      } catch (err) {
        console.error('SSE parse error', err);
      }
    };

    this.es.onerror = () => {
      if (this._done) return;
      this.overlayError.set('Connexion interrompue. Réessaie.');
      this.loading.set(false);
      this.es?.close();
      this.es = null;
    };
  }

  applyFilter(): void {
    this.results.set(this.allResults().filter(r => r.score >= this.minScore));
  }

  cancelScan(): void {
    this.es?.close();
    this.es = null;
    this.loading.set(false);
    this.overlayError.set('');
    this.scanDone.set(false);
  }

  scoreColor(score: number): string {
    if (score >= 0.1)  return '#00e676';
    if (score <= -0.1) return '#ff5252';
    return '#ffd740';
  }

  ngOnDestroy(): void { this.es?.close(); }
}
