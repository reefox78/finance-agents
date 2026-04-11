import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-analyse',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './analyse.component.html',
  styleUrl: './analyse.component.scss',
})
export class AnalyseComponent {
  ticker   = '';
  withLlm  = true;
  loading  = signal(false);
  result   = signal<any>(null);
  error    = signal('');

  constructor(private api: ApiService) {}

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
