import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ── Analyse ──────────────────────────────────────────────────────────────

  analyse(ticker: string, withLlm = true, modeRapide = false, period = '3mo'): Observable<any> {
    const params = new HttpParams()
      .set('with_llm', withLlm)
      .set('mode_rapide', modeRapide)
      .set('period', period)
      .set('with_chart', true);
    return this.http.get(`${this.base}/analyse/${ticker}`, { params });
  }

  // ── Scanner ───────────────────────────────────────────────────────────────

  getWatchlist(): Observable<Record<string, string[]>> {
    return this.http.get<Record<string, string[]>>(`${this.base}/scanner/watchlist`);
  }

  /** Returns an EventSource URL for SSE scanning. Caller must open EventSource manually. */
  scannerStreamUrl(categorie?: string, tickers?: string, minScore = 0): string {
    let url = `${this.base}/scanner/stream?min_score=${minScore}`;
    if (categorie) url += `&categorie=${categorie}`;
    if (tickers)   url += `&tickers=${encodeURIComponent(tickers)}`;
    return url;
  }

  // ── Portfolio ─────────────────────────────────────────────────────────────

  getPositions(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/portfolio/positions`);
  }

  evaluatePositions(withScores = false): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/portfolio/evaluate`, {
      params: new HttpParams().set('with_scores', withScores),
    });
  }

  getHistorique(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/portfolio/historique`);
  }

  getTransactions(ticker: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/portfolio/transactions/${ticker}`);
  }

  getAnalyseHistory(ticker: string): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/portfolio/analyse-history/${ticker}`);
  }

  getPrix(ticker: string): Observable<{ ticker: string; prix: number }> {
    return this.http.get<{ ticker: string; prix: number }>(`${this.base}/portfolio/price/${encodeURIComponent(ticker)}`);
  }

  addAchat(body: any): Observable<any> {
    return this.http.post(`${this.base}/portfolio/achat`, body);
  }

  addVente(body: any): Observable<any> {
    return this.http.post(`${this.base}/portfolio/vente`, body);
  }

  setObjectifs(body: any): Observable<any> {
    return this.http.put(`${this.base}/portfolio/objectifs`, body);
  }

  deletePosition(ticker: string): Observable<any> {
    return this.http.delete(`${this.base}/portfolio/positions/${ticker}`);
  }

  // ── Alerts ────────────────────────────────────────────────────────────────

  getAlerts(nonLuesSeulement = false): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/alerts/`, {
      params: new HttpParams().set('non_lues_seulement', nonLuesSeulement),
    });
  }

  getAlertsCount(): Observable<{ count: number }> {
    return this.http.get<{ count: number }>(`${this.base}/alerts/count`);
  }

  markAlertRead(id: string): Observable<any> {
    return this.http.put(`${this.base}/alerts/${id}/read`, {});
  }

  markAllRead(): Observable<any> {
    return this.http.put(`${this.base}/alerts/read-all`, {});
  }

  deleteAlert(id: string): Observable<any> {
    return this.http.delete(`${this.base}/alerts/${id}`);
  }

  getRules(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/alerts/rules`);
  }

  addRule(body: { ticker: string; condition: string; valeur: number; notif_email: boolean }): Observable<any> {
    return this.http.post(`${this.base}/alerts/rules`, body);
  }

  deleteRule(id: string): Observable<any> {
    return this.http.delete(`${this.base}/alerts/rules/${id}`);
  }

  toggleRule(id: string): Observable<any> {
    return this.http.put(`${this.base}/alerts/rules/${id}/toggle`, {});
  }

  checkRules(): Observable<{ triggered: any[]; count: number }> {
    return this.http.post<{ triggered: any[]; count: number }>(`${this.base}/alerts/check`, {});
  }

  // ── Calibration ───────────────────────────────────────────────────────────

  getCalibrationStatus(): Observable<any> {
    return this.http.get<any>(`${this.base}/calibration/status`);
  }

  getCalibrationDebug(): Observable<any> {
    return this.http.get<any>(`${this.base}/calibration/debug`);
  }

  runCalibration(): Observable<any> {
    return this.http.post<any>(`${this.base}/calibration/run`, {});
  }

  applyWeights(poids: Record<string, number>): Observable<any> {
    return this.http.post<any>(`${this.base}/calibration/apply`, { poids });
  }

  resetWeights(): Observable<any> {
    return this.http.delete<any>(`${this.base}/calibration/reset`);
  }

  // ── Backtest ──────────────────────────────────────────────────────────────

  runBacktest(body: { ticker: string; debut: string; fin: string; capital: number; mode: string }): Observable<any> {
    return this.http.post<any>(`${this.base}/backtest/run`, body);
  }

  // ── Calendar ─────────────────────────────────────────────────────────────

  getCalendarWeek(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/calendar/week`);
  }

  getCalendarToday(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/calendar/today`);
  }

  getCalendarStatus(): Observable<any> {
    return this.http.get<any>(`${this.base}/calendar/status`);
  }

  refreshCalendar(): Observable<any> {
    return this.http.post<any>(`${this.base}/calendar/refresh`, {});
  }

  getEarnings(ticker: string): Observable<{ ticker: string; date: string | null }> {
    return this.http.get<any>(`${this.base}/calendar/earnings`, {
      params: new HttpParams().set('ticker', ticker),
    });
  }

  // ── Logs ──────────────────────────────────────────────────────────────────

  getLogFiles(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/logs/files`);
  }

  getLogContent(filename: string): Observable<any> {
    return this.http.get<any>(`${this.base}/logs/content/${encodeURIComponent(filename)}`);
  }
}
