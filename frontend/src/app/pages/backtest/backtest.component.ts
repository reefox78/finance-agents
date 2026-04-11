import { Component, signal, computed } from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

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
export class BacktestComponent {
  watchlist  = WATCHLIST;
  categories = Object.keys(WATCHLIST);

  // Form state
  ticker   = 'AAPL';
  debut    = '2023-01-01';
  fin      = '2024-12-31';
  capital  = 10000;
  mode     = 'multi';

  // Results
  loading  = signal(false);
  result   = signal<any>(null);
  error    = signal('');

  constructor(private api: ApiService) {}

  label(t: string): string {
    return NAMES[t] ? `${t} — ${NAMES[t]}` : t;
  }

  run(): void {
    this.error.set('');
    this.result.set(null);
    this.loading.set(true);
    this.api.runBacktest({ ticker: this.ticker, debut: this.debut, fin: this.fin, capital: this.capital, mode: this.mode }).subscribe({
      next:  r => { this.result.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur serveur'); this.loading.set(false); },
    });
  }

  // ── Equity curve SVG helpers ──────────────────────────────────────────────

  readonly SVG_W = 800;
  readonly SVG_H = 200;
  readonly PAD   = 12;

  equitySvgPoints(): string {
    const pts = this.result()?.equity as Array<{date: string; valeur: number}>;
    if (!pts || pts.length < 2) return '';
    const vals  = pts.map(p => p.valeur);
    const min   = Math.min(...vals);
    const max   = Math.max(...vals);
    const range = max - min || 1;
    const w = this.SVG_W - this.PAD * 2;
    const h = this.SVG_H - this.PAD * 2;
    return pts.map((p, i) => {
      const x = this.PAD + (i / (pts.length - 1)) * w;
      const y = this.PAD + h - ((p.valeur - min) / range) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }

  equityColor(): string {
    const r = this.result();
    return r && r.rendement >= 0 ? '#2ecc71' : '#e74c3c';
  }

  // ── Rendement display ─────────────────────────────────────────────────────

  pnlClass(v: number): string {
    return v > 0 ? 'pos' : v < 0 ? 'neg' : '';
  }

  rendClass(): string {
    return this.pnlClass(this.result()?.rendement ?? 0);
  }

  winRateClass(): string {
    const wr = this.result()?.win_rate ?? 50;
    return wr >= 50 ? 'pos' : 'neg';
  }
}
