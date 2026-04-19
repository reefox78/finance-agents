import { Component, signal, ViewChild, ElementRef, OnDestroy, OnInit } from '@angular/core';
import { Subscription } from 'rxjs';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute, RouterModule } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import 'chartjs-adapter-date-fns';
import zoomPlugin from 'chartjs-plugin-zoom';
import { catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { ApiService } from '../../core/services/api.service';
import { AnalyseStateService } from '../../core/services/analyse-state.service';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';
import { TICKER_NAMES, WATCHLIST, WATCHLIST_CATEGORIES, tickerLabel } from '../../core/constants/watchlist';
import { BROKER_CALC, BROKERS_INFO } from '../../core/constants/watchlist';

Chart.register(...registerables, zoomPlugin);

const NAMES = TICKER_NAMES;

@Component({
  selector: 'app-analyse',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, LoadingOverlayComponent],
  templateUrl: './analyse.component.html',
  styleUrl: './analyse.component.scss',
})
export class AnalyseComponent implements OnInit, OnDestroy {
  @ViewChild('priceCanvas',  { static: true }) priceCanvas!:  ElementRef<HTMLCanvasElement>;
  @ViewChild('volumeCanvas', { static: true }) volumeCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('rsiCanvas',    { static: true }) rsiCanvas!:    ElementRef<HTMLCanvasElement>;
  @ViewChild('macdCanvas',   { static: true }) macdCanvas!:   ElementRef<HTMLCanvasElement>;

  watchlist    = WATCHLIST;
  categories   = WATCHLIST_CATEGORIES;
  quickTickers = ['AAPL', 'MC.PA', 'BTC-USD', 'EURUSD=X'];

  ticker       = '';
  customTicker = '';
  period       = '3mo';
  withLlm      = true;
  loading      = signal(false);
  result       = signal<any>(null);
  error        = signal('');
  overlayError = signal('');

  // Bannière calendrier économique
  todayEvents  = signal<any[]>([]);

  private _sub: Subscription | null = null;

  private _charts: Chart<any, any, any>[] = [];
  private _syncing = false;

  constructor(
    private api: ApiService,
    private router: Router,
    private route: ActivatedRoute,
    private state: AnalyseStateService,
  ) {}

  ngOnInit(): void {
    // Charge les événements macro du jour pour la bannière d'alerte
    this.api.getCalendarToday().subscribe({
      next: data => this.todayEvents.set(data),
      error: () => {},   // silencieux si indisponible
    });

    // Restaure l'état précédent s'il existe
    if (this.state.result) {
      this.ticker       = this.state.ticker;
      this.customTicker = this.state.customTicker;
      this.period       = this.state.period;
      this.withLlm      = this.state.withLlm;
      this.result.set(this.state.result);
      this.error.set(this.state.error);
      // Redessine les graphiques après restauration
      setTimeout(() => this._buildCharts(this.state.result?.chart), 50);
    }

    this.route.queryParams.subscribe(params => {
      if (params['ticker']) {
        // Mettre le ticker dans customTicker pour l'afficher dans le champ texte
        // (il peut ne pas être dans le dropdown watchlist)
        this.customTicker = params['ticker'].trim().toUpperCase();
        this.ticker = this.customTicker;   // synchronise pour run()
        this.run();
      }
    });
  }

  ngOnDestroy(): void {
    // Sauvegarde l'état avant de quitter
    this.state.ticker       = this.ticker;
    this.state.customTicker = this.customTicker;
    this.state.period       = this.period;
    this.state.withLlm      = this.withLlm;
    this.state.result       = this.result();
    this.state.error        = this.error();
    this._destroyCharts();
  }

  label(t: string): string { return NAMES[t] ? `${t} (${NAMES[t]})` : t; }

  // ── Modal achat ──────────────────────────────────────────────────────────
  showAchatModal = false;
  achatSubmitting = false;
  achatToast = '';
  achatError = '';
  brokerList    = Object.keys(BROKERS_INFO);
  selectedBroker = 'Trade Republic';
  achatForm     = { prix: 0, quantite: 1, frais: 0, notes: '' };
  achatMontant  = 0;   // "Montant investi" — pas envoyé à l'API

  ouvrirAchat(): void {
    const r = this.result();
    const prix = r?.tech?.prix_actuel ?? 0;
    this.achatForm   = { prix: Number(prix) || 0, quantite: 1, frais: 0, notes: '' };
    this.achatMontant = Math.round((this.achatForm.prix * this.achatForm.quantite) * 100) / 100;
    this._recalcFrais();
    this.achatError = '';
    this.showAchatModal = true;
  }

  fermerAchat(): void {
    this.showAchatModal = false;
    this.achatMontant = 0;
  }

  /** Prix changé → si montant renseigné, recalcule la quantité */
  onPrixChange(): void {
    if (this.achatForm.prix > 0) {
      if (this.achatMontant > 0) {
        this.achatForm.quantite = Math.round((this.achatMontant / this.achatForm.prix) * 10000) / 10000;
      } else {
        this.achatMontant = Math.round(this.achatForm.prix * this.achatForm.quantite * 100) / 100;
      }
    }
    this._recalcFrais();
  }

  /** Montant investi changé → recalcule la quantité */
  onMontantChange(): void {
    if (this.achatForm.prix > 0 && this.achatMontant > 0) {
      this.achatForm.quantite = Math.round((this.achatMontant / this.achatForm.prix) * 10000) / 10000;
    }
    this._recalcFrais();
  }

  /** Quantité changée manuellement → met à jour le montant */
  onQuantiteChange(): void {
    if (this.achatForm.prix > 0 && this.achatForm.quantite > 0) {
      this.achatMontant = Math.round(this.achatForm.prix * this.achatForm.quantite * 100) / 100;
    }
    this._recalcFrais();
  }

  onAchatFormChange(): void { this._recalcFrais(); }

  private _recalcFrais(): void {
    const calc = BROKER_CALC[this.selectedBroker];
    if (calc && this.selectedBroker !== 'Autre / Manuel') {
      this.achatForm.frais = calc(this.achatForm.prix * this.achatForm.quantite);
    }
  }

  confirmerAchat(): void {
    if (!this.ticker || !this.achatForm.prix || !this.achatForm.quantite) return;
    this.achatSubmitting = true;
    this.achatError = '';
    this.api.addAchat({
      ticker: this.ticker,
      prix: this.achatForm.prix,
      quantite: this.achatForm.quantite,
      frais: this.achatForm.frais,
      notes: this.achatForm.notes,
      broker_key: this.selectedBroker,
    }).pipe(catchError(e => {
      this.achatError = e.error?.detail ?? 'Erreur lors de l\'enregistrement';
      this.achatSubmitting = false;
      return of(null);
    })).subscribe(res => {
      if (!res) return;
      this.achatSubmitting = false;
      this.showAchatModal = false;
      this.achatToast = `✅ Achat ${this.ticker} enregistré !`;
      setTimeout(() => this.achatToast = '', 3500);
    });
  }
  onCustomInput(): void { this.ticker = this.customTicker.trim().toUpperCase(); }

  selectQuick(t: string): void {
    this.ticker = t;
    this.customTicker = '';
    this.run();
  }

  run(): void {
    const t = this.ticker.trim().toUpperCase();
    if (!t) return;
    this.error.set('');
    this.overlayError.set('');
    this.result.set(null);
    this._destroyCharts();
    this.loading.set(true);
    this._sub = this.api.analyse(t, this.withLlm, false, this.period).subscribe({
      next: r => {
        this.result.set(r);
        this.loading.set(false);
        if (r.chart?.dates?.length > 1) {
          setTimeout(() => this._buildCharts(r.chart), 0);
        }
      },
      error: e => {
        const status = e.status ? ` (${e.status})` : '';
        const detail = e.error?.detail ?? 'Erreur serveur';
        this.overlayError.set(`${detail}${status}`);
      },
    });
  }

  cancelLoading(): void {
    this._sub?.unsubscribe();
    this._sub = null;
    this.loading.set(false);
    this.overlayError.set('');
  }

  resetZoom(): void {
    this._charts.forEach(c => {
      if (c.options.scales?.['x']) {
        (c.options.scales['x'] as any).min = undefined;
        (c.options.scales['x'] as any).max = undefined;
      }
      c.update('none');
    });
  }

  scoreColor(s: number): string {
    return s >= 0.1 ? '#2ecc71' : s <= -0.1 ? '#e74c3c' : '#f1c40f';
  }

  gaugeNeedle(score: number): { x2: number; y2: number } {
    const clamped = Math.max(-1, Math.min(1, score));
    const angleDeg = 180 - ((clamped + 1) / 2) * 180;
    const angleRad = (angleDeg * Math.PI) / 180;
    // Centre SVG : (130, 130), rayon aiguille : 90
    return {
      x2: Math.round((130 + 90 * Math.cos(angleRad)) * 10) / 10,
      y2: Math.round((130 - 90 * Math.sin(angleRad)) * 10) / 10,
    };
  }
  decisionColor(d: string): string {
    if (d === 'ACHETER') return '#2ecc71';
    if (d === 'VENDRE')  return '#e74c3c';
    return '#f1c40f';
  }
  signalClass(sig: string): string {
    if (!sig) return '';
    const s = sig.toUpperCase();
    if (s.includes('ACHE') || s === 'HAUSSIER' || s === 'FAIBLE' || s === 'POSITIF' || s === 'CONFIRME') return 'sig-buy';
    if (s.includes('VEND') || s === 'BAISSIER' || s === 'ÉLEVÉ'  || s === 'NEGATIF' || s === 'INVALIDE') return 'sig-sell';
    return 'sig-neutral';
  }
  assetLabel(t: string): string {
    return ({ us_stock:'Action US', eu_stock:'Action EU', crypto:'Crypto', forex:'Forex' } as any)[t] ?? t;
  }

  // ── Charts ─────────────────────────────────────────────────────────────────

  private _destroyCharts(): void {
    this._charts.forEach(c => c.destroy());
    this._charts = [];
  }

  /** Appelé sur zoom/pan — synchronise les bornes X de tous les autres charts */
  private _syncFrom(source: any): void {
    if (this._syncing) return;
    this._syncing = true;
    const { min, max } = source.scales['x'];
    for (const c of this._charts) {
      if (c === source) continue;
      if (c.options.scales?.['x']) {
        (c.options.scales['x'] as any).min = min;
        (c.options.scales['x'] as any).max = max;
        c.update('none');
      }
    }
    this._syncing = false;
  }

  private _zoomOpts(): any {
    return {
      zoom: {
        wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' as const,
        onZoomComplete: ({ chart }: any) => this._syncFrom(chart),
      },
      pan: {
        enabled: true, mode: 'x' as const,
        onPanComplete: ({ chart }: any) => this._syncFrom(chart),
      },
    };
  }

  private _baseOpts(title: string): any {
    return {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: 'index' as const, intersect: false },
      plugins: {
        legend:  { labels: { color: '#7a9bbb', font: { size: 10 }, boxWidth: 10 } },
        title:   { display: !!title, text: title, color: '#9ab5cc', font: { size: 11, weight: '600' as const }, padding: { bottom: 6 } },
        tooltip: { backgroundColor: 'rgba(10,15,30,0.92)', borderColor: 'rgba(0,200,255,0.25)', borderWidth: 1, titleColor: '#c8d6f0', bodyColor: '#7a9bbb', padding: 8 },
        zoom: this._zoomOpts(),
      },
    };
  }

  private _xScale(display = true): any {
    return {
      type: 'time' as const,
      time: { unit: 'week' as const },
      adapters: { date: {} },
      display,
      ticks: { color: '#4a6a8a', maxRotation: 0, font: { size: 9 } },
      grid: { color: 'rgba(255,255,255,0.04)' },
    };
  }

  private _yScale(extra: any = {}): any {
    return {
      ticks: { color: '#4a6a8a', font: { size: 9 } },
      grid: { color: 'rgba(255,255,255,0.06)' },
      ...extra,
    };
  }

  private _buildCharts(c: any): void {
    this._destroyCharts();   // always destroy before recreating to avoid canvas reuse errors
    const dates = c.dates as string[];
    const xy = (arr: (number | null)[]) =>
      arr.map((y, i) => ({ x: dates[i], y: y ?? undefined }));

    // ── Chart 1 : Prix + SMA + Bollinger ────────────────────────────────────
    const c1 = new Chart(this.priceCanvas.nativeElement, {
      type: 'line',
      data: {
        datasets: [
          {
            label: 'Bollinger +2σ',
            data: xy(c.bb_upper),
            borderColor: 'rgba(0,200,255,0.3)', backgroundColor: 'rgba(0,200,255,0.07)',
            borderWidth: 1, borderDash: [4, 3], pointRadius: 0, fill: '+1', tension: 0.2, order: 5,
          },
          {
            label: 'Bollinger −2σ',
            data: xy(c.bb_lower),
            borderColor: 'rgba(0,200,255,0.3)', backgroundColor: 'rgba(0,200,255,0.07)',
            borderWidth: 1, borderDash: [4, 3], pointRadius: 0, fill: false as any, tension: 0.2, order: 5,
          },
          {
            label: 'Moy. 20j',
            data: xy(c.sma20),
            borderColor: 'rgba(52,152,219,0.9)', borderWidth: 1.5, pointRadius: 0, tension: 0.2, order: 3,
          },
          {
            label: 'Moy. 50j',
            data: xy(c.sma50),
            borderColor: 'rgba(230,126,34,0.9)', borderWidth: 1.5, pointRadius: 0, tension: 0.2, order: 3,
          },
          {
            label: 'Prix',
            data: xy(c.close),
            borderColor: '#00c8ff', backgroundColor: 'rgba(0,200,255,0.07)',
            fill: false as any, borderWidth: 2, pointRadius: 0, tension: 0.1, order: 1,
          },
        ],
      },
      options: {
        ...this._baseOpts('Prix · Moyennes mobiles · Bollinger Bands'),
        scales: { x: this._xScale(), y: this._yScale() },
      },
    });
    this._charts.push(c1);

    // ── Chart 2 : Volume ─────────────────────────────────────────────────────
    const c2 = new Chart(this.volumeCanvas.nativeElement, {
      type: 'bar',
      data: {
        datasets: [{
          label: 'Volume',
          data: dates.map((d, i) => ({ x: d, y: c.volume[i] ?? 0 })),
          backgroundColor: c.vol_colors,
          borderWidth: 0, barPercentage: 0.9, categoryPercentage: 1.0,
        }],
      },
      options: {
        ...this._baseOpts('Volume échangé'),
        scales: {
          x: this._xScale(false),
          y: this._yScale({
            ticks: {
              color: '#4a6a8a', font: { size: 9 },
              callback: (v: any) => v >= 1e9 ? (v/1e9).toFixed(1)+'G' : v >= 1e6 ? (v/1e6).toFixed(0)+'M' : String(v),
            },
          }),
        },
      },
    });
    this._charts.push(c2);

    // ── Chart 3 : RSI ────────────────────────────────────────────────────────
    const c3 = new Chart(this.rsiCanvas.nativeElement, {
      type: 'line',
      data: {
        datasets: [
          {
            label: 'RSI 14',
            data: xy(c.rsi),
            borderColor: '#e67e22', backgroundColor: 'transparent',
            borderWidth: 1.5, pointRadius: 0, tension: 0.2,
          },
          // Zones visuelles 70 / 30 via deux lignes constantes
          {
            label: 'Suracheté (70)',
            data: dates.map(d => ({ x: d, y: 70 })),
            borderColor: 'rgba(231,76,60,0.5)', backgroundColor: 'transparent',
            borderWidth: 1, borderDash: [4, 3], pointRadius: 0, order: 5,
          },
          {
            label: 'Survendu (30)',
            data: dates.map(d => ({ x: d, y: 30 })),
            borderColor: 'rgba(46,204,113,0.5)', backgroundColor: 'transparent',
            borderWidth: 1, borderDash: [4, 3], pointRadius: 0, order: 5,
          },
        ],
      },
      options: {
        ...this._baseOpts('RSI (14)'),
        scales: { x: this._xScale(false), y: this._yScale({ min: 0, max: 100 }) },
      },
    });
    this._charts.push(c3);

    // ── Chart 4 : MACD ───────────────────────────────────────────────────────
    const histColors = (c.macd_hist as (number|null)[]).map(v =>
      (v ?? 0) >= 0 ? 'rgba(46,204,113,0.65)' : 'rgba(231,76,60,0.65)'
    );
    const c4 = new Chart(this.macdCanvas.nativeElement, {
      type: 'bar',
      data: {
        datasets: [
          {
            type: 'bar' as any,
            label: 'Histogramme MACD',
            data: xy(c.macd_hist),
            backgroundColor: histColors, borderWidth: 0, barPercentage: 0.8, order: 3,
          },
          {
            type: 'line' as any,
            label: 'MACD (12−26)',
            data: xy(c.macd),
            borderColor: '#3498db', backgroundColor: 'transparent',
            borderWidth: 1.5, pointRadius: 0, tension: 0.2, order: 1,
          },
          {
            type: 'line' as any,
            label: 'Signal (9)',
            data: xy(c.macd_signal),
            borderColor: '#e74c3c', backgroundColor: 'transparent',
            borderWidth: 1.5, pointRadius: 0, tension: 0.2, order: 2,
          },
        ],
      },
      options: {
        ...this._baseOpts('MACD (12, 26, 9)'),
        scales: { x: this._xScale(), y: this._yScale() },
      },
    });
    this._charts.push(c4);
  }
}
