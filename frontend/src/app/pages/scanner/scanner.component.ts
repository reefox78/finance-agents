import { Component, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Router } from '@angular/router';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';

interface ScanResult {
  ticker:    string;
  score:     number;
  decision:  string;
  technique?: number;
  risque?:   number;
}

interface ScanError {
  ticker: string;
  error:  string;
}

@Component({
  selector: 'app-scanner',
  standalone: true,
  imports: [CommonModule, FormsModule, LoadingOverlayComponent],
  templateUrl: './scanner.component.html',
  styleUrl: './scanner.component.scss',
})
export class ScannerComponent implements OnDestroy {
  categorie = 'us_stocks';
  minScore  = 0;

  loading      = signal(false);
  progress     = signal<{ current: number; total: number; ticker: string } | null>(null);
  results      = signal<ScanResult[]>([]);
  allResults   = signal<ScanResult[]>([]);
  scanErrors   = signal<ScanError[]>([]);
  error        = signal('');
  overlayError = signal('');
  scanDone     = signal(false);
  scanTotal    = signal(0);
  showErrors   = false;

  private es: EventSource | null = null;
  private _done = false;

  constructor(private api: ApiService, private auth: AuthService, private router: Router) {}

  goToAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  startScan(): void {
    this.error.set('');
    this.overlayError.set('');
    this.results.set([]);
    this.allResults.set([]);
    this.scanErrors.set([]);
    this.loading.set(true);
    this.progress.set(null);
    this.scanDone.set(false);
    this.showErrors = false;
    this._done = false;

    const token = this.auth.token ?? '';
    // min_score=-1 → on récupère tout côté backend, le filtre se fait dans applyFilter()
    const base  = this.api.scannerStreamUrl(this.categorie || undefined, undefined, -1);
    const url   = `${base}&token=${encodeURIComponent(token)}`;

    this.es?.close();
    this.es = new EventSource(url);

    this.es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);

        if (msg.type === 'progress') {
          this.progress.set({ current: msg.current, total: msg.total, ticker: msg.ticker });
          this.scanTotal.set(msg.total);

        } else if (msg.type === 'done') {
          this._done = true;
          const all: ScanResult[]  = msg.resultats ?? [];
          const errs: ScanError[]  = msg.erreurs   ?? [];
          this.allResults.set(all);
          this.scanErrors.set(errs);
          this.results.set(all.filter(r => r.score >= this.minScore));
          this.loading.set(false);
          this.progress.set(null);
          this.scanDone.set(true);
          this.es?.close();
          this.es = null;
        }
      } catch (err) {
        console.error('SSE parse error', err);
      }
    };

    this.es.onerror = () => {
      // La fermeture normale du stream déclenche onerror → l'ignorer si done reçu
      if (this._done) return;
      this.overlayError.set('Connexion interrompue. Réessaie.');
      this.loading.set(false);
      this.es?.close();
      this.es = null;
    };
  }

  applyFilter(): void {
    this.results.set(this.allResults().filter(r => r.score >= this.minScore));
  }

  cancelScan(): void {
    this.es?.close();
    this.es = null;
    this.loading.set(false);
    this.overlayError.set('');
    this.scanDone.set(false);
  }

  scoreColor(score: number): string {
    if (score >= 0.1)  return '#00e676';
    if (score <= -0.1) return '#ff5252';
    return '#ffd740';
  }

  ngOnDestroy(): void {
    this.es?.close();
  }
}
