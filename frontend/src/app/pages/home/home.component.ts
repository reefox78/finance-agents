import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterModule } from '@angular/router';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.scss',
})
export class HomeComponent implements OnInit {

  summary  = signal<any>(null);
  calendar = signal<any[]>([]);
  loading  = signal(true);
  error    = signal('');

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.api.getDashboardSummary().subscribe({
      next: d => { this.summary.set(d); this.loading.set(false); },
      error: () => { this.error.set('Erreur chargement dashboard'); this.loading.set(false); },
    });
    this.api.getCalendarToday().subscribe({
      next: events => this.calendar.set(events),
      error: () => {},
    });
  }

  goAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  goScanner(): void { this.router.navigate(['/dashboard/scanner']); }
  goPortfolio(): void { this.router.navigate(['/dashboard/portfolio']); }

  scoreColor(s: number): string {
    return s >= 0.1 ? '#2ecc71' : s <= -0.1 ? '#e74c3c' : '#f1c40f';
  }

  decisionClass(d: string): string {
    if (d === 'ACHETER') return 'buy';
    if (d === 'VENDRE')  return 'sell';
    return 'neutral';
  }

  impactClass(impact: string): string {
    const i = (impact || '').toLowerCase();
    if (i === 'high')   return 'high';
    if (i === 'medium') return 'medium';
    return 'low';
  }

  timeAgo(ts: string): string {
    if (!ts) return '';
    const diff = Date.now() - new Date(ts).getTime();
    const h = Math.floor(diff / 3600000);
    const m = Math.floor(diff / 60000);
    if (h >= 24) return `${Math.floor(h / 24)}j`;
    if (h >= 1)  return `${h}h`;
    return `${m}min`;
  }

  get hasData(): boolean {
    const s = this.summary();
    return s && (
      s.opportunites.acheter.length > 0 ||
      s.opportunites.vendre.length  > 0 ||
      s.portfolio.length > 0
    );
  }
}
