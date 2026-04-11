import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-portfolio',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './portfolio.component.html',
  styleUrl: './portfolio.component.scss',
})
export class PortfolioComponent implements OnInit {
  tab = signal<'positions' | 'historique' | 'achat'>('positions');
  positions  = signal<any[]>([]);
  historique = signal<any[]>([]);
  loading    = signal(false);
  error      = signal('');

  // Achat form
  achat = { ticker: '', prix: null as number | null, quantite: null as number | null, date: '', frais: 0, notes: '' };

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.loadPositions(); }

  loadPositions(): void {
    this.loading.set(true);
    this.api.evaluatePositions(false).subscribe({
      next: r => { this.positions.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur'); this.loading.set(false); },
    });
  }

  loadHistorique(): void {
    this.loading.set(true);
    this.api.getHistorique().subscribe({
      next: r => { this.historique.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur'); this.loading.set(false); },
    });
  }

  switchTab(t: 'positions' | 'historique' | 'achat'): void {
    this.tab.set(t);
    if (t === 'historique' && this.historique().length === 0) this.loadHistorique();
  }

  submitAchat(): void {
    this.error.set('');
    this.api.addAchat(this.achat).subscribe({
      next: () => { this.tab.set('positions'); this.loadPositions(); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  pnlColor(pnl: number | null): string {
    if (pnl === null) return '#cde';
    return pnl >= 0 ? '#00e676' : '#ff5252';
  }
}
