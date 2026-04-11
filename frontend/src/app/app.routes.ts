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
      { path: '', redirectTo: 'analyse', pathMatch: 'full' },
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
