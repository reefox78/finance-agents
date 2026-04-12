import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './alerts.component.html',
  styleUrl: './alerts.component.scss',
})
export class AlertsComponent implements OnInit {
  alerts  = signal<any[]>([]);
  loading = signal(false);
  error   = signal('');

  constructor(private api: ApiService) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.getAlerts().subscribe({
      next: r  => { this.alerts.set(r); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur'); this.loading.set(false); },
    });
  }

  markRead(id: string): void {
    this.api.markAlertRead(id).subscribe(() =>
      this.alerts.update(list => list.map(a => a.id === id ? { ...a, lue: true } : a))
    );
  }

  markAll(): void {
    this.api.markAllRead().subscribe(() =>
      this.alerts.update(list => list.map(a => ({ ...a, lue: true })))
    );
  }

  delete(id: string): void {
    this.api.deleteAlert(id).subscribe(() =>
      this.alerts.update(list => list.filter(a => a.id !== id))
    );
  }

  niveauClass(niveau: string): string {
    const map: Record<string, string> = {
      CRITIQUE: 'crit', VENDRE: 'sell', SURVEILLER: 'warn', INFO: 'info',
    };
    return map[niveau] ?? 'info';
  }
}
