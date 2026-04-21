import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { adminGuard } from './core/guards/admin.guard';

export const routes: Routes = [
  {
    path: 'auth',
    loadComponent: () => import('./pages/auth/auth.component').then(m => m.AuthComponent),
  },
  {
    path: 'dashboard',
    loadComponent: () => import('./pages/dashboard/dashboard.component').then(m => m.DashboardComponent),
    canActivate: [authGuard],
    children: [
      { path: '', redirectTo: 'home', pathMatch: 'full' },
      {
        path: 'home',
        loadComponent: () => import('./pages/home/home.component').then(m => m.HomeComponent),
      },
      {
        path: 'analyse',
        loadComponent: () => import('./pages/analyse/analyse.component').then(m => m.AnalyseComponent),
      },
      {
        path: 'scanner',
        loadComponent: () => import('./pages/scanner/scanner.component').then(m => m.ScannerComponent),
      },
      {
        path: 'portfolio',
        loadComponent: () => import('./pages/portfolio/portfolio.component').then(m => m.PortfolioComponent),
      },
      {
        path: 'alerts',
        loadComponent: () => import('./pages/alerts/alerts.component').then(m => m.AlertsComponent),
      },
      {
        path: 'backtest',
        loadComponent: () => import('./pages/backtest/backtest.component').then(m => m.BacktestComponent),
      },

      {
        path: 'calendar',
        loadComponent: () => import('./pages/calendar/calendar.component').then(m => m.CalendarComponent),
      },
      {
        path: 'calibration',
        loadComponent: () => import('./pages/calibration/calibration.component').then(m => m.CalibrationComponent),
      },
      {
        path: 'logs',
        loadComponent: () => import('./pages/activity-logs/activity-logs.component').then(m => m.ActivityLogsComponent),
      },
    ],
  },
  {
    path: 'admin',
    loadComponent: () => import('./pages/admin/admin.component').then(m => m.AdminComponent),
    canActivate: [adminGuard],
  },
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' },
  { path: '**', redirectTo: '/dashboard' },
];
