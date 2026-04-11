import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // ── Analyse ──────────────────────────────────────────────────────────────

  analyse(ticker: string, withLlm = true, modeRapide = false): Observable<any> {
    const params = new HttpParams()
      .set('with_llm', withLlm)
      .set('mode_rapide', modeRapide);
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

  // ── Logs ──────────────────────────────────────────────────────────────────

  getLogFiles(): Observable<any[]> {
    return this.http.get<any[]>(`${this.base}/logs/files`);
  }

  getLogContent(filename: string): Observable<any> {
    return this.http.get<any>(`${this.base}/logs/content/${encodeURIComponent(filename)}`);
  }
}
