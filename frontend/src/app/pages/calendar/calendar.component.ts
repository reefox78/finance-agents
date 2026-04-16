import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-calendar',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './calendar.component.html',
  styleUrls: ['./calendar.component.scss'],
})
export class CalendarComponent implements OnInit {
  loading = signal(true);
  error   = signal('');
  events  = signal<any[]>([]);

  filterImpact  = 'all';
  filterCountry = 'all';

  // Statut / rafraîchissement
  status        = signal<any>(null);
  statusLoading = signal(false);
  refreshing    = signal(false);
  refreshResult = signal('');
  showStatus    = signal(false);

  today = new Date().toISOString().slice(0, 10);

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.getCalendarWeek().subscribe({
      next: data => { this.events.set(data); this.loading.set(false); },
      error: e   => { this.error.set(e.error?.detail ?? 'Impossible de charger le calendrier.'); this.loading.set(false); },
    });
  }

  checkStatus(): void {
    this.statusLoading.set(true);
    this.showStatus.set(true);
    this.status.set(null);
    this.api.getCalendarStatus().subscribe({
      next: s  => { this.status.set(s); this.statusLoading.set(false); },
      error: () => this.statusLoading.set(false),
    });
  }

  forceRefresh(): void {
    this.refreshing.set(true);
    this.refreshResult.set('');
    this.api.refreshCalendar().subscribe({
      next: r => {
        this.refreshing.set(false);
        this.refreshResult.set(`✅ ${r.events} événements depuis ${r.source}`);
        this.load();
      },
      error: e => {
        this.refreshing.set(false);
        this.refreshResult.set('❌ ' + (e.error?.detail ?? 'Erreur'));
      },
    });
  }

  // ── Computed ──────────────────────────────────────────────────────────────

  get filtered(): any[] {
    return this.events().filter(e => {
      const impactOk  = this.filterImpact  === 'all' || e.impact  === this.filterImpact;
      const countryOk = this.filterCountry === 'all' || e.country === this.filterCountry;
      return impactOk && countryOk;
    });
  }

  get groupedByDate(): { date: string; label: string; events: any[] }[] {
    const map = new Map<string, any[]>();
    for (const e of this.filtered) {
      if (!map.has(e.date)) map.set(e.date, []);
      map.get(e.date)!.push(e);
    }
    return Array.from(map.entries()).map(([date, evts]) => ({
      date,
      label: this._dateLabel(date),
      events: evts,
    }));
  }

  get availableCountries(): string[] {
    const set = new Set(this.events().map(e => e.country));
    return ['all', ...Array.from(set).sort()];
  }

  get highCount(): number { return this.events().filter(e => e.impact === 'High'   && e.date === this.today).length; }
  get medCount():  number { return this.events().filter(e => e.impact === 'Medium' && e.date === this.today).length; }

  impactClass(impact: string): string {
    return impact === 'High' ? 'imp-high' : impact === 'Medium' ? 'imp-med' : 'imp-low';
  }

  impactIcon(impact: string): string {
    return impact === 'High' ? '🔴' : impact === 'Medium' ? '🟡' : '⚪';
  }

  isToday(date: string): boolean { return date === this.today; }

  isFuture(time: string, date: string): boolean {
    if (date !== this.today || !time) return true;
    const now = new Date();
    const [h, m] = time.split(':').map(Number);
    return now.getHours() < h || (now.getHours() === h && now.getMinutes() < m);
  }

  private _dateLabel(dateStr: string): string {
    if (dateStr === this.today) return "Aujourd'hui";
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    if (dateStr === tomorrow.toISOString().slice(0, 10)) return 'Demain';
    return new Date(dateStr).toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long' });
  }
}
