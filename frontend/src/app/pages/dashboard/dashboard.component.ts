import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterModule, RouterOutlet],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.scss',
})
export class DashboardComponent implements OnInit {
  alertCount = signal(0);

  tabs = [
    { label: 'Analyse',      path: 'analyse',     icon: '🔍' },
    { label: 'Scanner',      path: 'scanner',     icon: '📋' },
    { label: 'Portefeuille', path: 'portfolio',   icon: '💼' },
    { label: 'Backtest',     path: 'backtest',    icon: '📊' },
    { label: 'Calibration',  path: 'calibration', icon: '⚙️' },
    { label: 'Logs',         path: 'logs',        icon: '🪵' },
  ];

  constructor(public auth: AuthService, private api: ApiService) {}

  ngOnInit(): void {
    this.api.getAlertsCount().subscribe({
      next: r => this.alertCount.set(r.count),
      error: () => {},
    });
  }
}
