import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

const NAMES: Record<string, string> = {
  // US Stocks
  'AAPL':    'Apple',
  'MSFT':    'Microsoft',
  'NVDA':    'Nvidia',
  'GOOGL':   'Alphabet',
  'META':    'Meta',
  'AMZN':    'Amazon',
  'TSLA':    'Tesla',
  'JPM':     'JPMorgan Chase',
  'XOM':     'ExxonMobil',
  'SPY':     'S&P 500 ETF',
  'V':       'Visa',
  'MA':      'Mastercard',
  'UNH':     'UnitedHealth',
  'JNJ':     'Johnson & Johnson',
  'WMT':     'Walmart',
  'HD':      'Home Depot',
  'BAC':     'Bank of America',
  'PG':      'Procter & Gamble',
  'COST':    'Costco',
  'NFLX':    'Netflix',
  // EU Stocks
  'MC.PA':   'LVMH',
  'TTE.PA':  'TotalEnergies',
  'SAN.PA':  'Sanofi',
  'BNP.PA':  'BNP Paribas',
  'OR.PA':   "L'Oréal",
  'AI.PA':   'Air Liquide',
  'SAF.PA':  'Safran',
  'ASML.AS': 'ASML',
  'SAP.DE':  'SAP',
  'SIE.DE':  'Siemens',
  'SHELL.AS':'Shell',
  'NOVN.SW': 'Novartis',
  'ROG.SW':  'Roche',
  'AZN.L':   'AstraZeneca',
  'HSBA.L':  'HSBC',
  'RMS.PA':  'Hermès',
  'CS.PA':   'AXA',
  'AIR.PA':  'Airbus',
  'DTE.DE':  'Deutsche Telekom',
  'ALV.DE':  'Allianz',
  // Crypto
  'BTC-USD':   'Bitcoin',
  'ETH-USD':   'Ethereum',
  'SOL-USD':   'Solana',
  'BNB-USD':   'BNB',
  'XRP-USD':   'XRP',
  'ADA-USD':   'Cardano',
  'DOGE-USD':  'Dogecoin',
  'DOT-USD':   'Polkadot',
  'AVAX-USD':  'Avalanche',
  'LINK-USD':  'Chainlink',
  'MATIC-USD': 'Polygon',
  'UNI-USD':   'Uniswap',
  'ATOM-USD':  'Cosmos',
  'LTC-USD':   'Litecoin',
  'TON-USD':   'Toncoin',
  'NEAR-USD':  'NEAR Protocol',
  'ICP-USD':   'Internet Computer',
  'FIL-USD':   'Filecoin',
  'APT-USD':   'Aptos',
  'ARB-USD':   'Arbitrum',
  // Forex
  'EURUSD=X': 'Euro / Dollar',
  'GBPUSD=X': 'Livre / Dollar',
  'USDJPY=X': 'Dollar / Yen',
  'USDCHF=X': 'Dollar / Franc suisse',
  'AUDUSD=X': 'Dollar australien / Dollar',
  'USDCAD=X': 'Dollar / Dollar canadien',
  'NZDUSD=X': 'Dollar NZ / Dollar',
  'EURGBP=X': 'Euro / Livre',
  'EURJPY=X': 'Euro / Yen',
  'GBPJPY=X': 'Livre / Yen',
  'USDCNY=X': 'Dollar / Yuan',
  'USDINR=X': 'Dollar / Roupie',
  'USDMXN=X': 'Dollar / Peso mexicain',
  'USDBRL=X': 'Dollar / Réal brésilien',
  'USDKRW=X': 'Dollar / Won coréen',
  'USDSGD=X': 'Dollar / Dollar singapourien',
  'USDHKD=X': 'Dollar / Dollar de HK',
  'EURCHF=X': 'Euro / Franc suisse',
  'AUDCAD=X': 'Dollar australien / Dollar canadien',
  'CADJPY=X': 'Dollar canadien / Yen',
};

const WATCHLIST: Record<string, string[]> = {
  'US Stocks': ['AAPL','MSFT','NVDA','GOOGL','META','AMZN','TSLA','JPM','XOM','SPY','V','MA','UNH','JNJ','WMT','HD','BAC','PG','COST','NFLX'],
  'EU Stocks': ['MC.PA','TTE.PA','SAN.PA','BNP.PA','OR.PA','AI.PA','SAF.PA','ASML.AS','SAP.DE','SIE.DE','SHELL.AS','NOVN.SW','ROG.SW','AZN.L','HSBA.L','RMS.PA','CS.PA','AIR.PA','DTE.DE','ALV.DE'],
  'Crypto':    ['BTC-USD','ETH-USD','SOL-USD','BNB-USD','XRP-USD','ADA-USD','DOGE-USD','DOT-USD','AVAX-USD','LINK-USD','MATIC-USD','UNI-USD','ATOM-USD','LTC-USD','TON-USD','NEAR-USD','ICP-USD','FIL-USD','APT-USD','ARB-USD'],
  'Forex':     ['EURUSD=X','GBPUSD=X','USDJPY=X','USDCHF=X','AUDUSD=X','USDCAD=X','NZDUSD=X','EURGBP=X','EURJPY=X','GBPJPY=X','USDCNY=X','USDINR=X','USDMXN=X','USDBRL=X','USDKRW=X','USDSGD=X','USDHKD=X','EURCHF=X','AUDCAD=X','CADJPY=X'],
};

@Component({
  selector: 'app-analyse',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analyse.component.html',
  styleUrl: './analyse.component.scss',
})
export class AnalyseComponent {
  watchlist  = WATCHLIST;
  categories = Object.keys(WATCHLIST);

  ticker       = '';
  customTicker = '';
  withLlm      = true;
  loading = signal(false);
  result  = signal<any>(null);
  error   = signal('');

  constructor(private api: ApiService) {}

  label(t: string): string {
    return NAMES[t] ? `${t} (${NAMES[t]})` : t;
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

  scoreColor(s: number): string {
    return s >= 0.1 ? '#00e676' : s <= -0.1 ? '#ff5252' : '#ffd740';
  }
}
