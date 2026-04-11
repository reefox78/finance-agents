import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-calibration',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="page">
      <div class="section-header"><span>⚙️ Calibration</span></div>
      <div class="coming-soon">
        <div class="cs-icon">🚧</div>
        <div class="cs-title">Bientôt disponible</div>
        <div class="cs-desc">La calibration des poids des agents est en cours de développement.</div>
      </div>
    </div>
  `,
  styles: [`
    .coming-soon {
      display: flex; flex-direction: column; align-items: center;
      gap: 0.75rem; padding: 4rem 0; color: var(--text-muted);
    }
    .cs-icon  { font-size: 3rem; }
    .cs-title { font-size: 1.2rem; font-weight: 700; color: var(--text-secondary); }
    .cs-desc  { font-size: 14px; }
  `],
})
export class CalibrationComponent {}
