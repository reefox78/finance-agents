import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

const WATCHLIST: Record<string, string[]> = {
  'US Stocks': [
    'AAPL','MSFT','NVDA','GOOGL','META',
    'AMZN','TSLA','JPM','XOM','SPY',
    'V','MA','UNH','JNJ','WMT',
    'HD','BAC','PG','COST','NFLX',
  ],
  'EU Stocks': [
    'MC.PA','TTE.PA','SAN.PA','BNP.PA','OR.PA',
    'AI.PA','SAF.PA','ASML.AS','SAP.DE','SIE.DE',
    'SHELL.AS','NOVN.SW','ROG.SW','AZN.L','HSBA.L',
    'RMS.PA','CS.PA','AIR.PA','DTE.DE','ALV.DE',
  ],
  'Crypto': [
    'BTC-USD','ETH-USD','SOL-USD','BNB-USD','XRP-USD',
    'ADA-USD','DOGE-USD','DOT-USD','AVAX-USD','LINK-USD',
    'MATIC-USD','UNI-USD','ATOM-USD','LTC-USD','TON-USD',
    'NEAR-USD','ICP-USD','FIL-USD','APT-USD','ARB-USD',
  ],
  'Forex': [
    'EURUSD=X','GBPUSD=X','USDJPY=X','USDCHF=X','AUDUSD=X',
    'USDCAD=X','NZDUSD=X','EURGBP=X','EURJPY=X','GBPJPY=X',
    'USDCNY=X','USDINR=X','USDMXN=X','USDBRL=X','USDKRW=X',
    'USDSGD=X','USDHKD=X','EURCHF=X','AUDCAD=X','CADJPY=X',
  ],
};

@Component({
  selector: 'app-analyse',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analyse.component.html',
  styleUrl: './analyse.component.scss',
})
export class AnalyseComponent {
  watchlist = WATCHLIST;
  categories = Object.keys(WATCHLIST);

  ticker       = '';
  customTicker = '';
  withLlm      = true;
  loading  = signal(false);
  result   = signal<any>(null);
  error    = signal('');

  constructor(private api: ApiService) {}

  selectTicker(t: string): void {
    this.ticker       = t;
    this.customTicker = '';
  }

  onCustomInput(): void {
    this.ticker = this.customTicker.trim().toUpperCase();
  }

  run(): void {
    const t = this.ticker.trim().toUpperCase();
    if (!t) return;
    this.error.set('');
    this.result.set(null);
    this.loading.set(true);

    this.api.analyse(t, this.withLlm).subscribe({
      next: r => { this.result.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur serveur'); this.loading.set(false); },
    });
  }

  scoreColor(score: number): string {
    if (score >= 0.1)  return '#00e676';
    if (score <= -0.1) return '#ff5252';
    return '#ffd740';
  }
}
