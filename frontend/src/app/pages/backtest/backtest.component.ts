import { Component, signal, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import {
  Chart, registerables,
  TimeScale, LinearScale, PointElement, LineElement,
  BarElement, ScatterController, LineController, BarController,
  Filler, Tooltip, Legend, Title,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import zoomPlugin from 'chartjs-plugin-zoom';
import { ApiService } from '../../core/services/api.service';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';

Chart.register(...registerables, zoomPlugin);

const NAMES: Record<string, string> = {
  'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','GOOGL':'Alphabet','META':'Meta',
  'AMZN':'Amazon','TSLA':'Tesla','JPM':'JPMorgan Chase','XOM':'ExxonMobil','SPY':'S&P 500 ETF',
  'V':'Visa','MA':'Mastercard','UNH':'UnitedHealth','JNJ':'Johnson & Johnson','WMT':'Walmart',
  'HD':'Home Depot','BAC':'Bank of America','PG':'Procter & Gamble','COST':'Costco','NFLX':'Netflix',
  'MC.PA':'LVMH','TTE.PA':'TotalEnergies','SAN.PA':'Sanofi','BNP.PA':'BNP Paribas','OR.PA':"L'Oréal",
  'AI.PA':'Air Liquide','SAF.PA':'Safran','ASML.AS':'ASML','SAP.DE':'SAP','SIE.DE':'Siemens',
  'SHELL.AS':'Shell','NOVN.SW':'Novartis','ROG.SW':'Roche','AZN.L':'AstraZeneca','HSBA.L':'HSBC',
  'RMS.PA':'Hermès','CS.PA':'AXA','AIR.PA':'Airbus','DTE.DE':'Deutsche Telekom','ALV.DE':'Allianz',
  'BTC-USD':'Bitcoin','ETH-USD':'Ethereum','SOL-USD':'Solana','BNB-USD':'BNB','XRP-USD':'XRP',
  'EURUSD=X':'Euro / Dollar','GBPUSD=X':'Livre / Dollar','USDJPY=X':'Dollar / Yen',
  'USDCHF=X':'Dollar / CHF','AUDUSD=X':'AUD / Dollar','USDCAD=X':'Dollar / CAD',
};

const WATCHLIST: Record<string, string[]> = {
  'Actions US':  ['AAPL','MSFT','NVDA','GOOGL','META','AMZN','TSLA','JPM','XOM','SPY','V','MA','UNH','JNJ','WMT','HD','BAC','PG','COST','NFLX'],
  'Actions EU':  ['MC.PA','TTE.PA','SAN.PA','BNP.PA','OR.PA','AI.PA','SAF.PA','ASML.AS','SAP.DE','SIE.DE','SHELL.AS','NOVN.SW','ROG.SW','AZN.L','HSBA.L','RMS.PA','CS.PA','AIR.PA','DTE.DE','ALV.DE'],
  'Crypto':      ['BTC-USD','ETH-USD','SOL-USD','BNB-USD','XRP-USD'],
  'Forex':       ['EURUSD=X','GBPUSD=X','USDJPY=X','USDCHF=X','AUDUSD=X','USDCAD=X'],
};

@Component({
  selector: 'app-backtest',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe, LoadingOverlayComponent],
  templateUrl: './backtest.component.html',
  styleUrls: ['./backtest.component.scss'],
})
export class BacktestComponent implements OnDestroy {
  @ViewChild('priceCanvas',  { static: true }) priceCanvas!:  ElementRef<HTMLCanvasElement>;
  @ViewChild('equityCanvas', { static: true }) equityCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('pnlCanvas',    { static: true }) pnlCanvas!:    ElementRef<HTMLCanvasElement>;

  watchlist  = WATCHLIST;
  categories = Object.keys(WATCHLIST);

  ticker  = 'AAPL';
  debut   = '2023-01-01';
  fin     = '2024-12-31';
  capital = 10000;
  mode    = 'agents';

  readonly modes = [
    { value: 'agents',    label: '🤖 Agents complets',           desc: 'Technique + Macro FRED + Risque + Momentum 5j + Secteur + Earnings Surprise' },
    { value: 'multi',     label: '📊 Multi-agents (basique)',     desc: 'Technique + Macro FRED + Risque rolling' },
    { value: 'technique', label: '📈 Technique seul',             desc: 'RSI + MACD + Bollinger + SMA uniquement' },
  ];

  loading      = signal(false);
  result       = signal<any>(null);
  error        = signal('');
  overlayError = signal('');

  private _charts: Chart[] = [];
  private _sub: Subscription | null = null;

  constructor(private api: ApiService) {}
  ngOnDestroy(): void { this._sub?.unsubscribe(); this._destroyCharts(); }

  label(t: string): string { return NAMES[t] ? `${t} — ${NAMES[t]}` : t; }

  run(): void {
    this.error.set('');
    this.overlayError.set('');
    this.result.set(null);
    this._destroyCharts();
    this.loading.set(true);
    this._sub = this.api.runBacktest({ ticker: this.ticker, debut: this.debut, fin: this.fin, capital: this.capital, mode: this.mode }).subscribe({
      next: r => { this.result.set(r); this.loading.set(false); setTimeout(() => this._buildCharts(r), 0); },
      error: e => {
        const status = e.status ? ` (${e.status})` : '';
        this.overlayError.set((e.error?.detail ?? 'Erreur serveur') + status);
      },
    });
  }

  cancelBacktest(): void {
    this._sub?.unsubscribe();
    this._sub = null;
    this.loading.set(false);
    this.overlayError.set('');
  }

  resetZoom(): void { this._charts.forEach(c => (c as any).resetZoom?.()); }

  pnlClass(v: number)  { return v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }
  rendClass()          { return this.pnlClass(this.result()?.rendement ?? 0); }
  winRateClass()       { return (this.result()?.win_rate ?? 50) >= 50 ? 'pos' : 'neg'; }

  // ── Charts ────────────────────────────────────────────────────────────────

  private _destroyCharts(): void {
    this._charts.forEach(c => c.destroy());
    this._charts = [];
  }

  private _zoomOpts() {
    return {
      zoom:  { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' as const },
      pan:   { enabled: true, mode: 'x' as const },
    };
  }

  private _buildCharts(r: any): void {
    const trades: any[] = r.trades  ?? [];
    const equity: any[] = r.equity  ?? [];
    const prices: any[] = r.prices  ?? [];
    const positive = r.rendement >= 0;
    const lineColor = positive ? '#2ecc71' : '#e74c3c';

    // ── Chart 1 : Prix + signaux de trading ──────────────────────────────
    if (prices.length > 1) {
      const priceData = prices.map((p: any) => ({ x: p.date, y: p.close }));

      // Trouver la date de prix la plus proche pour chaque trade
      const priceDates = prices.map((p: any) => p.date);
      const nearestDate = (d: string) => priceDates.reduce((best: string, curr: string) =>
        Math.abs(Date.parse(curr) - Date.parse(d)) < Math.abs(Date.parse(best) - Date.parse(d)) ? curr : best
      );
      const closePriceAt = (d: string) => {
        const nearest = nearestDate(d);
        return prices.find((p: any) => p.date === nearest)?.close ?? 0;
      };

      const buyPts  = trades.map((t: any) => ({ x: nearestDate(t.date_achat), y: t.prix_achat }));
      const sellPts = trades.map((t: any) => ({ x: nearestDate(t.date),       y: t.prix_vente }));

      const c1 = new Chart(this.priceCanvas.nativeElement, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Prix clôture',
              data: priceData,
              borderColor: 'rgba(0,200,255,0.85)',
              backgroundColor: 'rgba(0,200,255,0.06)',
              fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.1, order: 3,
            },
            {
              label: 'Achat ▲',
              data: buyPts,
              type: 'scatter' as any,
              backgroundColor: '#2ecc71', borderColor: '#27ae60', borderWidth: 2,
              pointStyle: 'triangle', pointRadius: 11, order: 1,
            },
            {
              label: 'Vente ▼',
              data: sellPts,
              type: 'scatter' as any,
              backgroundColor: '#e74c3c', borderColor: '#c0392b', borderWidth: 2,
              pointStyle: 'triangle', rotation: 180, pointRadius: 11, order: 2,
            },
          ],
        },
        options: {
          ...this._opts('Prix & signaux'),
          scales: {
            x: { type: 'time', time: { unit: 'month' }, adapters: { date: {} },
                 ticks: { color: '#4a6a8a', maxRotation: 0, font: { size: 10 } },
                 grid: { color: 'rgba(255,255,255,0.04)' } },
            y: { ticks: { color: '#4a6a8a', font: { size: 10 } },
                 grid: { color: 'rgba(255,255,255,0.06)' } },
          },
          plugins: { ...this._opts('Prix & signaux').plugins, zoom: this._zoomOpts() },
        },
      });
      this._charts.push(c1);
    }

    // ── Chart 2 : Courbe de capital + benchmark Buy & Hold ──────────────
    if (equity.length > 1) {
      const eValues   = equity.map((p: any)     => ({ x: p.date, y: p.valeur }));
      const benchmark: any[] = r.benchmark ?? [];
      const bhValues  = benchmark.map((p: any)  => ({ x: p.date, y: p.valeur }));

      const buyEq  = trades.map((t: any, i: number) => ({
        x: t.date_achat,
        y: equity[i]?.valeur ?? equity[0].valeur,
      }));
      const sellEq = trades.map((t: any, i: number) => ({
        x: t.date,
        y: equity[i + 1]?.valeur ?? equity[equity.length - 1]?.valeur,
      }));

      const c2 = new Chart(this.equityCanvas.nativeElement, {
        type: 'line',
        data: {
          datasets: [
            {
              label: 'Stratégie',
              data: eValues,
              borderColor: lineColor,
              backgroundColor: positive ? 'rgba(46,204,113,0.08)' : 'rgba(231,76,60,0.08)',
              fill: true, borderWidth: 2,
              pointRadius: 5, pointBackgroundColor: lineColor,
              tension: 0.3, order: 3,
            },
            ...(bhValues.length > 1 ? [{
              label: 'Buy & Hold',
              data: bhValues,
              borderColor: 'rgba(150,150,200,0.55)',
              backgroundColor: 'transparent',
              borderWidth: 1.5,
              borderDash: [5, 4],
              pointRadius: 0,
              tension: 0.1,
              order: 4,
            }] : []),
            {
              label: 'Achat ▲',
              data: buyEq,
              type: 'scatter' as any,
              backgroundColor: '#2ecc71', borderColor: '#27ae60', borderWidth: 2,
              pointStyle: 'triangle', pointRadius: 11, order: 1,
            },
            {
              label: 'Vente ▼',
              data: sellEq,
              type: 'scatter' as any,
              backgroundColor: '#e74c3c', borderColor: '#c0392b', borderWidth: 2,
              pointStyle: 'triangle', rotation: 180, pointRadius: 11, order: 2,
            },
          ],
        },
        options: {
          ...this._opts('Courbe de capital (€)'),
          scales: {
            x: { type: 'time', time: { unit: 'month' }, adapters: { date: {} },
                 ticks: { color: '#4a6a8a', maxRotation: 0, font: { size: 10 } },
                 grid: { color: 'rgba(255,255,255,0.04)' } },
            y: { ticks: { color: '#4a6a8a', font: { size: 10 } },
                 grid: { color: 'rgba(255,255,255,0.06)' } },
          },
          plugins: { ...this._opts('Courbe de capital (€)').plugins, zoom: this._zoomOpts() },
        },
      });
      this._charts.push(c2);
    }

    // ── Chart 3 : P&L par trade ───────────────────────────────────────────
    if (trades.length > 0) {
      const pLabels = trades.map((_: any, i: number) => `#${i + 1}`);
      const pValues = trades.map((t: any) => t.pnlnet);
      const colors  = pValues.map((v: number) => v >= 0 ? 'rgba(46,204,113,0.75)' : 'rgba(231,76,60,0.75)');
      const borders = pValues.map((v: number) => v >= 0 ? '#2ecc71' : '#e74c3c');

      const c3 = new Chart(this.pnlCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels: pLabels,
          datasets: [{ label: 'P&L net (€)', data: pValues,
            backgroundColor: colors, borderColor: borders, borderWidth: 1.5, borderRadius: 4 }],
        },
        options: {
          ...this._opts('P&L net par trade (€)'),
          plugins: {
            ...this._opts('P&L net par trade (€)').plugins,
            zoom: this._zoomOpts(),
            tooltip: {
              ...this._opts('').plugins.tooltip,
              callbacks: {
                label: (ctx: any) => {
                  const t = trades[ctx.dataIndex];
                  const s = t.pnlnet >= 0 ? '+' : '';
                  return [` P&L : ${s}${t.pnlnet.toFixed(2)} €`, ` ${t.date_achat} → ${t.date}`];
                },
              },
            },
          },
        },
      });
      this._charts.push(c3);
    }
  }

  private _opts(title: string): any {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as any, intersect: false },
      plugins: {
        legend:  { labels: { color: '#7a9bbb', font: { size: 11 }, boxWidth: 12 } },
        title:   { display: !!title, text: title, color: '#9ab5cc', font: { size: 12, weight: '600' as any }, padding: { bottom: 8 } },
        tooltip: { backgroundColor: 'rgba(10,15,30,0.92)', borderColor: 'rgba(0,200,255,0.25)', borderWidth: 1, titleColor: '#c8d6f0', bodyColor: '#7a9bbb', padding: 10 },
      },
    };
  }
}
