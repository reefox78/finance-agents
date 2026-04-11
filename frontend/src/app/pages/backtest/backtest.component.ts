import {
  Component, signal, ViewChild, ElementRef,
  AfterViewChecked, OnDestroy,
} from '@angular/core';
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
export class BacktestComponent implements AfterViewChecked, OnDestroy {
  @ViewChild('priceCanvas')  priceCanvas!:  ElementRef<HTMLCanvasElement>;
  @ViewChild('equityCanvas') equityCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('pnlCanvas')    pnlCanvas!:    ElementRef<HTMLCanvasElement>;

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

  private _chartsBuilt = false;
  private _priceChart?: Chart;
  private _equityChart?: Chart;
  private _pnlChart?: Chart;

  constructor(private api: ApiService) {}

  ngAfterViewChecked(): void {
    if (this.result() && !this._chartsBuilt) {
      this._chartsBuilt = true;
      // microtask to ensure canvas is in DOM
      setTimeout(() => this._buildCharts(), 0);
    }
  }

  ngOnDestroy(): void {
    this._destroyCharts();
  }

  label(t: string): string {
    return NAMES[t] ? `${t} — ${NAMES[t]}` : t;
  }

  run(): void {
    this.error.set('');
    this.result.set(null);
    this._chartsBuilt = false;
    this._destroyCharts();
    this.loading.set(true);
    this.api.runBacktest({
      ticker: this.ticker, debut: this.debut,
      fin: this.fin, capital: this.capital, mode: this.mode,
    }).subscribe({
      next:  r => { this.result.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur serveur'); this.loading.set(false); },
    });
  }

  pnlClass(v: number): string { return v > 0 ? 'pos' : v < 0 ? 'neg' : ''; }
  rendClass():    string { return this.pnlClass(this.result()?.rendement ?? 0); }
  winRateClass(): string { return (this.result()?.win_rate ?? 50) >= 50 ? 'pos' : 'neg'; }

  // ─── Chart building ────────────────────────────────────────────────────────

  private _destroyCharts(): void {
    this._priceChart?.destroy();
    this._equityChart?.destroy();
    this._pnlChart?.destroy();
    this._priceChart = this._equityChart = this._pnlChart = undefined;
  }

  private _buildCharts(): void {
    const r = this.result();
    if (!r) return;

    const trades: any[] = r.trades ?? [];
    const equity: any[] = r.equity ?? [];
    const prices: any[] = r.prices ?? [];

    this._buildPriceChart(prices, trades);
    this._buildEquityChart(equity, trades);
    this._buildPnlChart(trades);
  }

  // Chart 1 : Prix de clôture + signaux ACHAT / VENTE
  private _buildPriceChart(prices: any[], trades: any[]): void {
    if (!this.priceCanvas || prices.length === 0) return;
    this._priceChart?.destroy();

    const labels = prices.map(p => p.date);
    const closes = prices.map(p => p.close);

    // Map trades to price dates
    const buyPoints  = trades.map(t => ({ x: t.date_achat, y: t.prix_achat }));
    const sellPoints = trades.map(t => ({ x: t.date,       y: t.prix_vente }));

    const color = (this.result()?.rendement ?? 0) >= 0 ? '#2ecc71' : '#e74c3c';

    this._priceChart = new Chart(this.priceCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Prix clôture',
            data: closes,
            borderColor: 'rgba(0,200,255,0.8)',
            backgroundColor: 'rgba(0,200,255,0.06)',
            fill: true,
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.2,
            order: 3,
          },
          {
            label: 'Achat',
            data: buyPoints,
            type: 'scatter' as any,
            backgroundColor: '#2ecc71',
            borderColor: '#27ae60',
            borderWidth: 1.5,
            pointStyle: 'triangle',
            pointRadius: 9,
            order: 1,
          },
          {
            label: 'Vente',
            data: sellPoints,
            type: 'scatter' as any,
            backgroundColor: '#e74c3c',
            borderColor: '#c0392b',
            borderWidth: 1.5,
            pointStyle: 'triangle',
            rotation: 180,
            pointRadius: 9,
            order: 2,
          },
        ],
      },
      options: this._chartOptions('Prix & signaux', true),
    });
  }

  // Chart 2 : Courbe de capital + marqueurs achat/vente
  private _buildEquityChart(equity: any[], trades: any[]): void {
    if (!this.equityCanvas || equity.length === 0) return;
    this._equityChart?.destroy();

    const labels = equity.map(p => p.date);
    const values = equity.map(p => p.valeur);

    // Buy point i → equity value at index i (capital before trade i)
    const buyPts  = trades.map((t, i) => ({ x: t.date_achat, y: equity[i]?.valeur ?? 0 }));
    // Sell point i → equity value at index i+1 (after trade i closes)
    const sellPts = trades.map((t, i) => ({ x: t.date, y: equity[i + 1]?.valeur ?? equity[equity.length - 1]?.valeur ?? 0 }));

    const positive = (this.result()?.rendement ?? 0) >= 0;

    this._equityChart = new Chart(this.equityCanvas.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Capital (€)',
            data: values,
            borderColor: positive ? '#2ecc71' : '#e74c3c',
            backgroundColor: positive ? 'rgba(46,204,113,0.10)' : 'rgba(231,76,60,0.10)',
            fill: true,
            borderWidth: 2,
            pointRadius: 3,
            pointBackgroundColor: positive ? '#2ecc71' : '#e74c3c',
            tension: 0.3,
            order: 3,
          },
          {
            label: 'Achat',
            data: buyPts,
            type: 'scatter' as any,
            backgroundColor: '#2ecc71',
            borderColor: '#27ae60',
            borderWidth: 2,
            pointStyle: 'triangle',
            pointRadius: 10,
            order: 1,
          },
          {
            label: 'Vente',
            data: sellPts,
            type: 'scatter' as any,
            backgroundColor: '#e74c3c',
            borderColor: '#c0392b',
            borderWidth: 2,
            pointStyle: 'triangle',
            rotation: 180,
            pointRadius: 10,
            order: 2,
          },
        ],
      },
      options: this._chartOptions('Courbe de capital (€)', false),
    });
  }

  // Chart 3 : P&L par trade (barres)
  private _buildPnlChart(trades: any[]): void {
    if (!this.pnlCanvas || trades.length === 0) return;
    this._pnlChart?.destroy();

    const labels = trades.map((t, i) => `#${i + 1} ${t.date_achat}`);
    const values = trades.map(t => t.pnlnet);
    const colors = values.map(v => v >= 0 ? 'rgba(46,204,113,0.75)' : 'rgba(231,76,60,0.75)');
    const borders= values.map(v => v >= 0 ? '#2ecc71' : '#e74c3c');

    this._pnlChart = new Chart(this.pnlCanvas.nativeElement, {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: 'P&L net (€)',
          data: values,
          backgroundColor: colors,
          borderColor: borders,
          borderWidth: 1.5,
          borderRadius: 4,
        }],
      },
      options: {
        ...this._chartOptions('P&L net par trade (€)', false),
        plugins: {
          ...this._chartOptions('', false).plugins,
          tooltip: {
            callbacks: {
              label: (ctx: any) => {
                const t = trades[ctx.dataIndex];
                const sign = t.pnlnet >= 0 ? '+' : '';
                return [
                  ` P&L net : ${sign}${t.pnlnet.toFixed(2)} €`,
                  ` Achat   : ${t.date_achat} @ ${t.prix_achat}`,
                  ` Vente   : ${t.date} @ ${t.prix_vente}`,
                ];
              },
            },
          },
        },
      },
    });
  }

  private _chartOptions(title: string, yLog = false): any {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: { color: '#7a9bbb', font: { size: 11 }, boxWidth: 12 },
        },
        title: {
          display: !!title,
          text: title,
          color: '#9ab5cc',
          font: { size: 12, weight: '600' },
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
