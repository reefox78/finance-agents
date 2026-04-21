import { Component, OnInit, signal, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
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
export class DashboardComponent implements OnInit, AfterViewInit {
  @ViewChild('bottomNav') bottomNavRef!: ElementRef<HTMLElement>;

  alertCount  = signal(0);
  canScrollL  = signal(false);
  canScrollR  = signal(false);

  tabs = [
    { label: 'Accueil',      path: 'home',        icon: '🏠' },
    { label: 'Analyse',      path: 'analyse',     icon: '🔍' },
    { label: 'Comparer',     path: 'compare',     icon: '⚖️' },
    { label: 'Scanner',      path: 'scanner',     icon: '📡' },
    { label: 'Portefeuille', path: 'portfolio',   icon: '💼' },
    { label: 'Calendrier',   path: 'calendar',    icon: '📅' },
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

  ngAfterViewInit(): void {
    this.updateArrows();
  }

  onNavScroll(): void {
    this.updateArrows();
  }

  private updateArrows(): void {
    const el = this.bottomNavRef?.nativeElement;
    if (!el) return;
    this.canScrollL.set(el.scrollLeft > 4);
    this.canScrollR.set(el.scrollLeft + el.clientWidth < el.scrollWidth - 4);
  }

  scrollNav(dir: 'left' | 'right'): void {
    const el = this.bottomNavRef?.nativeElement;
    if (!el) return;
    el.scrollBy({ left: dir === 'left' ? -120 : 120, behavior: 'smooth' });
    setTimeout(() => this.updateArrows(), 300);
  }
}
