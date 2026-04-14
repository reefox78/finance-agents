import { Injectable, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

/**
 * Ping le backend toutes les 10 minutes pour éviter le cold start Render.
 * (Le tier gratuit endort le service après 15 min d'inactivité.)
 */
@Injectable({ providedIn: 'root' })
export class KeepaliveService implements OnDestroy {
  private _interval: any = null;
  private readonly _url = `${environment.apiUrl}/health`;

  constructor(private http: HttpClient) {}

  start(): void {
    if (this._interval) return;
    // Ping immédiat au démarrage pour réveiller le serveur si endormi
    this._ping();
    // Puis toutes les 10 minutes
    this._interval = setInterval(() => this._ping(), 10 * 60 * 1000);
  }

  ngOnDestroy(): void {
    if (this._interval) { clearInterval(this._interval); this._interval = null; }
  }

  private _ping(): void {
    this.http.get(this._url).subscribe({ error: () => {} });
  }
}
