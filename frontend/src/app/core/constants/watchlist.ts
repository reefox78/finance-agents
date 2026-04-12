export const TICKER_NAMES: Record<string, string> = {
  'AAPL':'Apple','MSFT':'Microsoft','NVDA':'Nvidia','GOOGL':'Alphabet','META':'Meta',
  'AMZN':'Amazon','TSLA':'Tesla','JPM':'JPMorgan Chase','XOM':'ExxonMobil','SPY':'S&P 500 ETF',
  'V':'Visa','MA':'Mastercard','UNH':'UnitedHealth','JNJ':'Johnson & Johnson','WMT':'Walmart',
  'HD':'Home Depot','BAC':'Bank of America','PG':'Procter & Gamble','COST':'Costco','NFLX':'Netflix',
  'MC.PA':'LVMH','TTE.PA':'TotalEnergies','SAN.PA':'Sanofi','BNP.PA':'BNP Paribas','OR.PA':"L'Oréal",
  'AI.PA':'Air Liquide','SAF.PA':'Safran','ASML.AS':'ASML','SAP.DE':'SAP','SIE.DE':'Siemens',
  'SHELL.AS':'Shell','NOVN.SW':'Novartis','ROG.SW':'Roche','AZN.L':'AstraZeneca','HSBA.L':'HSBC',
  'RMS.PA':'Hermès','CS.PA':'AXA','AIR.PA':'Airbus','DTE.DE':'Deutsche Telekom','ALV.DE':'Allianz',
  'BTC-USD':'Bitcoin','ETH-USD':'Ethereum','SOL-USD':'Solana','BNB-USD':'BNB','XRP-USD':'XRP',
  'ADA-USD':'Cardano','DOGE-USD':'Dogecoin','DOT-USD':'Polkadot','AVAX-USD':'Avalanche','LINK-USD':'Chainlink',
  'MATIC-USD':'Polygon','UNI-USD':'Uniswap','ATOM-USD':'Cosmos','LTC-USD':'Litecoin','TON-USD':'Toncoin',
  'NEAR-USD':'NEAR Protocol','ICP-USD':'Internet Computer','FIL-USD':'Filecoin','APT-USD':'Aptos','ARB-USD':'Arbitrum',
  'EURUSD=X':'Euro / Dollar','GBPUSD=X':'Livre / Dollar','USDJPY=X':'Dollar / Yen',
  'USDCHF=X':'Dollar / Franc suisse','AUDUSD=X':'AUD / Dollar','USDCAD=X':'Dollar / CAD',
  'NZDUSD=X':'NZD / Dollar','EURGBP=X':'Euro / Livre','EURJPY=X':'Euro / Yen','GBPJPY=X':'Livre / Yen',
  'USDCNY=X':'Dollar / Yuan','USDINR=X':'Dollar / Roupie','USDMXN=X':'Dollar / Peso',
  'USDBRL=X':'Dollar / Réal','USDKRW=X':'Dollar / Won','USDSGD=X':'Dollar / SGD',
  'USDHKD=X':'Dollar / HKD','EURCHF=X':'Euro / CHF','AUDCAD=X':'AUD / CAD','CADJPY=X':'CAD / Yen',
};

export const WATCHLIST: Record<string, string[]> = {
  'Actions US': ['AAPL','MSFT','NVDA','GOOGL','META','AMZN','TSLA','JPM','XOM','SPY','V','MA','UNH','JNJ','WMT','HD','BAC','PG','COST','NFLX'],
  'Actions EU': ['MC.PA','TTE.PA','SAN.PA','BNP.PA','OR.PA','AI.PA','SAF.PA','ASML.AS','SAP.DE','SIE.DE','SHELL.AS','NOVN.SW','ROG.SW','AZN.L','HSBA.L','RMS.PA','CS.PA','AIR.PA','DTE.DE','ALV.DE'],
  'Crypto':     ['BTC-USD','ETH-USD','SOL-USD','BNB-USD','XRP-USD','ADA-USD','DOGE-USD','DOT-USD','AVAX-USD','LINK-USD','MATIC-USD','UNI-USD','ATOM-USD','LTC-USD','TON-USD','NEAR-USD','ICP-USD','FIL-USD','APT-USD','ARB-USD'],
  'Forex':      ['EURUSD=X','GBPUSD=X','USDJPY=X','USDCHF=X','AUDUSD=X','USDCAD=X','NZDUSD=X','EURGBP=X','EURJPY=X','GBPJPY=X','USDCNY=X','USDINR=X','USDMXN=X','USDBRL=X','USDKRW=X','USDSGD=X','USDHKD=X','EURCHF=X','AUDCAD=X','CADJPY=X'],
};

export const WATCHLIST_CATEGORIES = Object.keys(WATCHLIST);

export function tickerLabel(t: string): string {
  return TICKER_NAMES[t] ? `${t} — ${TICKER_NAMES[t]}` : t;
}

/** Frais broker selon montant total en € */
export const BROKER_CALC: Record<string, (montant: number) => number> = {
  'Trade Republic':      (_) => 1.00,
  'Degiro':              (m) => Math.round(Math.max(2.00, m * 0.00038) * 100) / 100,
  'Boursorama':          (m) => Math.round(Math.max(1.99, m * 0.00099) * 100) / 100,
  'Fortuneo':            (m) => Math.round(Math.max(7.50, m * 0.002)   * 100) / 100,
  'Interactive Brokers': (m) => Math.round(Math.max(0.35, m * 0.0035)  * 100) / 100,
  'Autre / Manuel':      (_) => 0,
};

export const BROKERS_INFO: Record<string, string> = {
  'Trade Republic':      '1 € fixe par ordre',
  'Degiro':              '2 € min + 0.038% du montant',
  'Boursorama':          '1.99 € min + 0.099% du montant',
  'Fortuneo':            '7.50 € min + 0.2% du montant',
  'Interactive Brokers': '0.35 € min + 0.35% du montant',
  'Autre / Manuel':      'Frais à saisir manuellement',
};
