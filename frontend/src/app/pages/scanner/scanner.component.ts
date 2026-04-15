import { Component, OnDestroy, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { Router } from '@angular/router';
import { LoadingOverlayComponent } from '../../shared/components/loading-overlay/loading-overlay.component';

interface ScanResult {
  ticker: string;
  score: number;
  decision: string;
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
  error        = signal('');
  overlayError = signal('');

  private es: EventSource | null = null;

  constructor(private api: ApiService, private auth: AuthService, private router: Router) {}

  goToAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  startScan(): void {
    this.error.set('');
    this.overlayError.set('');
    this.results.set([]);
    this.loading.set(true);
    this.progress.set(null);

    // SSE requires auth token in URL (EventSource doesn't support headers)
    const token = this.auth.token ?? '';
    const base  = this.api.scannerStreamUrl(this.categorie || undefined, undefined, this.minScore);
    const url   = `${base}&token=${encodeURIComponent(token)}`;

    this.es?.close();
    this.es = new EventSource(url);

    this.es.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'progress') {
        this.progress.set({ current: msg.current, total: msg.total, ticker: msg.ticker });
      } else if (msg.type === 'done') {
        this.results.set(msg.resultats);
        this.loading.set(false);
        this.progress.set(null);
        this.es?.close();
      } else if (msg.type === 'result' && !msg.ok) {
        // individual ticker error — continue
      }
    };

    this.es.onerror = () => {
      this.overlayError.set('Erreur de connexion SSE');
      this.es?.close();
    };
  }

  cancelScan(): void {
    this.es?.close();
    this.es = null;
    this.loading.set(false);
    this.overlayError.set('');
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
