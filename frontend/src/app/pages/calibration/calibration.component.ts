import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

@Component({
  selector: 'app-calibration',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './calibration.component.html',
  styleUrl: './calibration.component.scss',
})
export class CalibrationComponent implements OnInit {

  // ── State ──────────────────────────────────────────────────────────────────
  status      = signal<any>(null);       // GET /status response
  calibResult = signal<any>(null);       // POST /run response
  loading     = signal<'' | 'status' | 'running' | 'saving' | 'resetting'>('');
  error       = signal('');
  saved       = signal(false);

  /** Poids en cours d'édition (slider + input) */
  editedWeights: Record<string, number> = {};

  constructor(private api: ApiService) {}

  ngOnInit(): void { this._loadStatus(); }

  // ── Helpers ────────────────────────────────────────────────────────────────

  get agents(): string[] {
    return this.status() ? Object.keys(this.status().poids_actifs) : [];
  }

  label(agent: string): string {
    return this.status()?.labels?.[agent] ?? agent;
  }

  /** Somme totale des poids édités */
  get totalPoids(): number {
    return Object.values(this.editedWeights).reduce((a, b) => a + b, 0);
  }

  totalColor(): string {
    const t = this.totalPoids;
    return t > 1.3 || t < 0.5 ? '#e74c3c' : t > 1.1 ? '#f1c40f' : '#2ecc71';
  }

  accuracyColor(exactitude: number | null): string {
    if (exactitude === null) return '#4a6a8a';
    if (exactitude >= 0.65) return '#2ecc71';
    if (exactitude >= 0.55) return '#f1c40f';
    return '#e74c3c';
  }

  accuracyLabel(exactitude: number | null): string {
    if (exactitude === null) return 'Données insuffisantes';
    return (exactitude * 100).toFixed(1) + '%';
  }

  delta(agent: string): number {
    const actuel   = this.status()?.poids_actifs?.[agent] ?? 0;
    const suggere  = this.calibResult()?.poids_suggeres?.[agent];
    return suggere !== undefined ? Math.round((suggere - actuel) * 1000) / 1000 : 0;
  }

  deltaClass(agent: string): string {
    const d = this.delta(agent);
    return d > 0 ? 'delta-up' : d < 0 ? 'delta-down' : '';
  }

  barWidth(poids: number, max = 0.4): string {
    return Math.min(100, (poids / max) * 100).toFixed(1) + '%';
  }

  // ── Actions ────────────────────────────────────────────────────────────────

  private _loadStatus(): void {
    this.loading.set('status');
    this.error.set('');
    this.api.getCalibrationStatus().subscribe({
      next: s => {
        this.status.set(s);
        this._resetEditedWeights(s.poids_actifs);
        this.loading.set('');
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur chargement');
        this.loading.set('');
      },
    });
  }

  runCalibration(): void {
    this.loading.set('running');
    this.error.set('');
    this.calibResult.set(null);
    this.api.runCalibration().subscribe({
      next: r => {
        this.calibResult.set(r);
        this.loading.set('');
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur calibration');
        this.loading.set('');
      },
    });
  }

  applySuggested(): void {
    const poids = this.calibResult()?.poids_suggeres;
    if (!poids) return;
    this._resetEditedWeights(poids);
  }

  saveWeights(): void {
    this.loading.set('saving');
    this.saved.set(false);
    this.error.set('');
    this.api.applyWeights(this.editedWeights).subscribe({
      next: () => {
        this.saved.set(true);
        this._loadStatus();
        setTimeout(() => this.saved.set(false), 3000);
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur sauvegarde');
        this.loading.set('');
      },
    });
  }

  resetToDefault(): void {
    if (!confirm('Remettre les poids par défaut ?')) return;
    this.loading.set('resetting');
    this.api.resetWeights().subscribe({
      next: () => {
        this.calibResult.set(null);
        this._loadStatus();
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur reset');
        this.loading.set('');
      },
    });
  }

  private _resetEditedWeights(source: Record<string, number>): void {
    this.editedWeights = {};
    for (const [k, v] of Object.entries(source)) {
      this.editedWeights[k] = Math.round(v * 10000) / 10000;
    }
  }
}
