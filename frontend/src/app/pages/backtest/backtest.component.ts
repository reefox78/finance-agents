import { Component, signal, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Chart, registerables } from 'chart.js';
import { ApiService } from '../../core/services/api.service';

Chart.register(...registerables);

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
  'Actions US': ['AAPL','MSFT','NVDA','GOOGL','META','AMZN','TSLA','JPM','XOM','SPY','V','MA','UNH','JNJ','WMT','HD','BAC','PG','COST','NFLX'],
  'Actions EU': ['MC.PA','TTE.PA','SAN.PA','BNP.PA','OR.PA','AI.PA','SAF.PA','ASML.AS','SAP.DE','SIE.DE','SHELL.AS','NOVN.SW','ROG.SW','AZN.L','HSBA.L','RMS.PA','CS.PA','AIR.PA','DTE.DE','ALV.DE'],
  'Crypto':     ['BTC-USD','ETH-USD','SOL-USD','BNB-USD','XRP-USD'],
  'Forex':      ['EURUSD=X','GBPUSD=X','USDJPY=X','USDCHF=X','AUDUSD=X','USDCAD=X'],
};

@Component({
  selector: 'app-backtest',
  standalone: true,
  imports: [CommonModule, FormsModule, DecimalPipe],
  templateUrl: './backtest.component.html',
  styleUrls: ['./backtest.component.scss'],
})
export class BacktestComponent implements OnDestroy {
  // Canvas toujours présents dans le DOM (pas dans un @if) → ViewChild fonctionne
  @ViewChild('priceCanvas',  { static: true }) priceCanvas!:  ElementRef<HTMLCanvasElement>;
  @ViewChild('equityCanvas', { static: true }) equityCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('pnlCanvas',    { static: true }) pnlCanvas!:    ElementRef<HTMLCanvasElement>;

  watchlist  = WATCHLIST;
  categories = Object.keys(WATCHLIST);

  ticker  = 'AAPL';
  debut   = '2023-01-01';
  fin     = '2024-12-31';
  capital = 10000;
  mode    = 'multi';

  loading = signal(false);
  result  = signal<any>(null);
  error   = signal('');

  private _priceChart?: Chart;
  private _equityChart?: Chart;
  private _pnlChart?: Chart;

  constructor(private api: ApiService) {}

  ngOnDestroy(): void { this._destroyCharts(); }

  label(t: string): string { return NAMES[t] ? `${t} — ${NAMES[t]}` : t; }

  run(): void {
    this.error.set('');
    this.result.set(null);
    this._destroyCharts();
    this.loading.set(true);

    this.api.runBacktest({
      ticker: this.ticker, debut: this.debut,
      fin: this.fin, capital: this.capital, mode: this.mode,
    }).subscribe({
      next: r => {
        this.result.set(r);
        this.loading.set(false);
        // Canvas déjà dans le DOM → on peut construire immédiatement
        setTimeout(() => this._buildCharts(r), 0);
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur serveur');
        this.loading.set(false);
      },
    });
  }

  pnlClass(v: number): string { return v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }
  rendClass():    string { return this.pnlClass(this.result()?.rendement ?? 0); }
  winRateClass(): string { return (this.result()?.win_rate ?? 50) >= 50 ? 'pos' : 'neg'; }

  // ── Charts ────────────────────────────────────────────────────────────────

  private _destroyCharts(): void {
    this._priceChart?.destroy();  this._priceChart  = undefined;
    this._equityChart?.destroy(); this._equityChart = undefined;
    this._pnlChart?.destroy();    this._pnlChart    = undefined;
  }

  private _buildCharts(r: any): void {
    const trades: any[] = r.trades  ?? [];
    const equity: any[] = r.equity  ?? [];
    const prices: any[] = r.prices  ?? [];
    const positive = r.rendement >= 0;

    // ── Chart 1 : Prix de clôture + signaux ──────────────────────────────
    if (prices.length > 1) {
      const labels    = prices.map((p: any) => p.date);
      const closes    = prices.map((p: any) => p.close);
      const buyPts    = trades.map((t: any) => ({ x: t.date_achat, y: t.prix_achat  }));
      const sellPts   = trades.map((t: any) => ({ x: t.date,       y: t.prix_vente  }));

      this._priceChart = new Chart(this.priceCanvas.nativeElement, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Prix clôture',
              data: closes,
              borderColor: 'rgba(0,200,255,0.85)',
              backgroundColor: 'rgba(0,200,255,0.07)',
              fill: true, borderWidth: 1.5, pointRadius: 0, tension: 0.2, order: 3,
            },
            {
              label: 'Achat ▲',
              data: buyPts,
              type: 'scatter' as any,
              backgroundColor: '#2ecc71', borderColor: '#27ae60', borderWidth: 2,
              pointStyle: 'triangle', pointRadius: 10, order: 1,
            },
            {
              label: 'Vente ▼',
              data: sellPts,
              type: 'scatter' as any,
              backgroundColor: '#e74c3c', borderColor: '#c0392b', borderWidth: 2,
              pointStyle: 'triangle', rotation: 180, pointRadius: 10, order: 2,
            },
          ],
        },
        options: this._opts('Prix & signaux'),
      });
    }

    // ── Chart 2 : Courbe de capital ───────────────────────────────────────
    if (equity.length > 1) {
      const eLabels = equity.map((p: any) => p.date);
      const eValues = equity.map((p: any) => p.valeur);
      const buyEq   = trades.map((t: any, i: number) => ({ x: t.date_achat, y: equity[i]?.valeur ?? 0 }));
      const sellEq  = trades.map((t: any, i: number) => ({ x: t.date, y: equity[i + 1]?.valeur ?? equity[equity.length - 1]?.valeur ?? 0 }));

      this._equityChart = new Chart(this.equityCanvas.nativeElement, {
        type: 'line',
        data: {
          labels: eLabels,
          datasets: [
            {
              label: 'Capital (€)',
              data: eValues,
              borderColor: positive ? '#2ecc71' : '#e74c3c',
              backgroundColor: positive ? 'rgba(46,204,113,0.10)' : 'rgba(231,76,60,0.10)',
              fill: true, borderWidth: 2,
              pointRadius: 4, pointBackgroundColor: positive ? '#2ecc71' : '#e74c3c',
              tension: 0.3, order: 3,
            },
            {
              label: 'Achat ▲',
              data: buyEq,
              type: 'scatter' as any,
              backgroundColor: '#2ecc71', borderColor: '#27ae60', borderWidth: 2,
              pointStyle: 'triangle', pointRadius: 10, order: 1,
            },
            {
              label: 'Vente ▼',
              data: sellEq,
              type: 'scatter' as any,
              backgroundColor: '#e74c3c', borderColor: '#c0392b', borderWidth: 2,
              pointStyle: 'triangle', rotation: 180, pointRadius: 10, order: 2,
            },
          ],
        },
        options: this._opts('Courbe de capital (€)'),
      });
    }

    // ── Chart 3 : P&L par trade ───────────────────────────────────────────
    if (trades.length > 0) {
      const pLabels = trades.map((_: any, i: number) => `#${i + 1}`);
      const pValues = trades.map((t: any) => t.pnlnet);
      const colors  = pValues.map((v: number) => v >= 0 ? 'rgba(46,204,113,0.75)' : 'rgba(231,76,60,0.75)');
      const borders = pValues.map((v: number) => v >= 0 ? '#2ecc71' : '#e74c3c');

      this._pnlChart = new Chart(this.pnlCanvas.nativeElement, {
        type: 'bar',
        data: {
          labels: pLabels,
          datasets: [{
            label: 'P&L net (€)',
            data: pValues,
            backgroundColor: colors,
            borderColor: borders,
            borderWidth: 1.5,
            borderRadius: 4,
          }],
        },
        options: {
          ...this._opts('P&L net par trade (€)'),
          plugins: {
            ...this._opts('').plugins,
            tooltip: {
              ...this._opts('').plugins?.tooltip,
              callbacks: {
                label: (ctx: any) => {
                  const t = trades[ctx.dataIndex];
                  const s = t.pnlnet >= 0 ? '+' : '';
                  return [
                    ` P&L net : ${s}${t.pnlnet.toFixed(2)} €`,
                    ` Achat : ${t.date_achat} @ ${t.prix_achat}`,
                    ` Vente : ${t.date} @ ${t.prix_vente}`,
                  ];
                },
              },
            },
          },
        },
      });
    }
  }

  private _opts(title: string): any {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index' as any, intersect: false },
      plugins: {
        legend: { labels: { color: '#7a9bbb', font: { size: 11 }, boxWidth: 12 } },
        title: {
          display: !!title,
          text: title,
          color: '#9ab5cc',
          font: { size: 12, weight: '600' as any },
          padding: { bottom: 10 },
        },
        tooltip: {
          backgroundColor: 'rgba(10,15,30,0.92)',
          borderColor: 'rgba(0,200,255,0.25)',
          borderWidth: 1,
          titleColor: '#c8d6f0',
          bodyColor: '#7a9bbb',
          padding: 10,
        },
      },
      scales: {
        x: {
          ticks: { color: '#4a6a8a', maxTicksLimit: 10, maxRotation: 0, font: { size: 10 } },
          grid:  { color: 'rgba(255,255,255,0.04)' },
        },
        y: {
          ticks: { color: '#4a6a8a', font: { size: 10 } },
          grid:  { color: 'rgba(255,255,255,0.06)' },
        },
      },
    };
  }
}
