import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

type Tab = 'received' | 'rules';

interface RuleForm {
  ticker: string;
  condition: string;
  valeur: number | null;
  notif_email: boolean;
}

@Component({
  selector: 'app-alerts',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './alerts.component.html',
  styleUrl: './alerts.component.scss',
})
export class AlertsComponent implements OnInit {
  // ── Tab state ─────────────────────────────────────────────────────────────
  activeTab = signal<Tab>('received');

  // ── Alertes reçues ────────────────────────────────────────────────────────
  alerts  = signal<any[]>([]);
  loading = signal(false);
  error   = signal('');

  // ── Règles ────────────────────────────────────────────────────────────────
  rules        = signal<any[]>([]);
  rulesLoading = signal(false);
  rulesError   = signal('');

  form: RuleForm = { ticker: '', condition: 'PRIX_DESSUS', valeur: null, notif_email: false };
  formError  = signal('');
  formSaving = signal(false);

  // ── Vérification immédiate ─────────────────────────────────────────────────
  checking       = signal(false);
  checkResult    = signal<any[] | null>(null);
  checkError     = signal('');

  readonly CONDITIONS = [
    { value: 'PRIX_DESSUS',  label: 'Prix au-dessus de' },
    { value: 'PRIX_DESSOUS', label: 'Prix en dessous de' },
    { value: 'RSI_DESSOUS',  label: 'RSI en dessous de' },
    { value: 'RSI_DESSUS',   label: 'RSI au-dessus de' },
    { value: 'SCORE_DESSUS', label: 'Score agents >' },
    { value: 'SCORE_DESSOUS', label: 'Score agents <' },
  ];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadAlerts();
    this.loadRules();
  }

  // ── Tab switching ─────────────────────────────────────────────────────────
  setTab(tab: Tab): void {
    this.activeTab.set(tab);
  }

  // ── Alertes reçues ────────────────────────────────────────────────────────
  loadAlerts(): void {
    this.loading.set(true);
    this.error.set('');
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

  deleteAlert(id: string): void {
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

  // ── Règles ────────────────────────────────────────────────────────────────
  loadRules(): void {
    this.rulesLoading.set(true);
    this.rulesError.set('');
    this.api.getRules().subscribe({
      next: r  => { this.rules.set(r); this.rulesLoading.set(false); },
      error: e => { this.rulesError.set(e.error?.detail ?? 'Erreur'); this.rulesLoading.set(false); },
    });
  }

  addRule(): void {
    this.formError.set('');
    if (!this.form.ticker.trim()) { this.formError.set('Ticker requis.'); return; }
    if (this.form.valeur === null || this.form.valeur === undefined) {
      this.formError.set('Valeur requise.'); return;
    }
    this.formSaving.set(true);
    this.api.addRule({
      ticker: this.form.ticker.trim().toUpperCase(),
      condition: this.form.condition,
      valeur: this.form.valeur,
      notif_email: this.form.notif_email,
    }).subscribe({
      next: rule => {
        this.rules.update(list => [rule, ...list]);
        this.form = { ticker: '', condition: 'PRIX_DESSUS', valeur: null, notif_email: false };
        this.formSaving.set(false);
      },
      error: e => {
        this.formError.set(e.error?.detail ?? 'Erreur');
        this.formSaving.set(false);
      },
    });
  }

  deleteRule(id: string): void {
    this.api.deleteRule(id).subscribe(() =>
      this.rules.update(list => list.filter(r => r.id !== id))
    );
  }

  toggleRule(id: string): void {
    this.api.toggleRule(id).subscribe({
      next: updated => this.rules.update(list => list.map(r => r.id === id ? updated : r)),
      error: e => this.rulesError.set(e.error?.detail ?? 'Erreur toggle'),
    });
  }

  conditionLabel(cond: string): string {
    return this.CONDITIONS.find(c => c.value === cond)?.label ?? cond;
  }

  // ── Vérification immédiate ─────────────────────────────────────────────────
  checkNow(): void {
    this.checking.set(true);
    this.checkResult.set(null);
    this.checkError.set('');
    this.api.checkRules().subscribe({
      next: res => {
        this.checkResult.set(res.triggered);
        this.checking.set(false);
        // Recharger les alertes si des alertes ont été déclenchées
        if (res.count > 0) { this.loadAlerts(); }
      },
      error: e => {
        this.checkError.set(e.error?.detail ?? 'Erreur lors de la vérification');
        this.checking.set(false);
      },
    });
  }
}
