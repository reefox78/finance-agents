import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-logs',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="page">
      <div class="section-header"><span>🪵 Logs</span></div>
      <div class="coming-soon">
        <div class="cs-icon">🚧</div>
        <div class="cs-title">Bientôt disponible</div>
        <div class="cs-desc">Le journal des décisions agents sera visible ici.</div>
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
export class ActivityLogsComponent {}
