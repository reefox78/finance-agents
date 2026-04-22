import { Component, signal, computed, ViewChild, ElementRef, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Chart, registerables } from 'chart.js';
import { ApiService } from '../../core/services/api.service';

Chart.register(...registerables);

const STRATEGIES = ['Swing', 'Day Trading', 'Momentum', 'Breakout', 'Valeur', 'Contrarian', 'Autre'];
const TODAY = new Date().toISOString().split('T')[0];

@Component({
  selector: 'app-journal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './journal.component.html',
  styleUrl:    './journal.component.scss',
})
export class JournalComponent implements OnInit, OnDestroy {
  @ViewChild('equityCanvas') equityCanvas!: ElementRef<HTMLCanvasElement>;

  readonly strategies = STRATEGIES;
  readonly today      = TODAY;

  // ── État ─────────────────────────────────────────────────────────────────
  trades      = signal<any[]>([]);
  stats       = signal<any>(null);
  loading     = signal(false);
  statsLoading= signal(false);
  error       = signal('');

  // Filtres
  filterStatus   = '';
  filterStrategy = '';
  filterTicker   = '';

  // Modals
  showAddModal    = false;
  showCloseModal  = false;
  showNotesModal  = false;
  activeTradeId   = '';
  activeTicker    = '';

  // Formulaire ajout
  form = {
    ticker:            '',
    direction:         'LONG',
    entry_price:       null as number | null,
    entry_date:        TODAY,
    quantity:          1,
    strategy:          '',
    notes:             '',
    score_at_entry:    null as number | null,
    decision_at_entry: '',
  };

  // Formulaire clôture
  closeForm = {
    exit_price: null as number | null,
    exit_date:  TODAY,
  };

  // Notes inline
  notesValue = '';

  // Onglet dashboard
  dashTab: 'curve' | 'strategy' = 'curve';

  private _chart: Chart | null = null;

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit(): void {
    this.loadAll();
  }

  ngOnDestroy(): void {
    this._chart?.destroy();
  }

  // ── Chargement ───────────────────────────────────────────────────────────

  loadAll(): void {
    this.loadTrades();
    this.loadStats();
  }

  loadTrades(): void {
    this.loading.set(true);
    this.error.set('');
    this.api.getJournalTrades(
      this.filterStatus   || undefined,
      this.filterStrategy || undefined,
      this.filterTicker   || undefined,
    ).subscribe({
      next: t => { this.trades.set(t); this.loading.set(false); },
      error: e => { this.error.set(e.error?.detail ?? 'Erreur chargement'); this.loading.set(false); },
    });
  }

  loadStats(): void {
    this.statsLoading.set(true);
    this.api.getJournalStats().subscribe({
      next: s => {
        this.stats.set(s);
        this.statsLoading.set(false);
        setTimeout(() => this._buildChart(s), 80);
      },
      error: () => this.statsLoading.set(false),
    });
  }

  // ── Filtres ──────────────────────────────────────────────────────────────

  applyFilters(): void { this.loadTrades(); }

  resetFilters(): void {
    this.filterStatus   = '';
    this.filterStrategy = '';
    this.filterTicker   = '';
    this.loadTrades();
  }

  // ── Ajout ────────────────────────────────────────────────────────────────

  openAdd(): void {
    this.form = {
      ticker: '', direction: 'LONG', entry_price: null,
      entry_date: TODAY, quantity: 1, strategy: '',
      notes: '', score_at_entry: null, decision_at_entry: '',
    };
    this.showAddModal = true;
  }

  submitAdd(): void {
    if (!this.form.ticker || !this.form.entry_price || !this.form.entry_date) return;
    const body: any = { ...this.form };
    if (!body.strategy)          delete body.strategy;
    if (!body.notes)             delete body.notes;
    if (!body.score_at_entry)    delete body.score_at_entry;
    if (!body.decision_at_entry) delete body.decision_at_entry;

    this.api.addJournalTrade(body).subscribe({
      next: () => { this.showAddModal = false; this.loadAll(); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur création'),
    });
  }

  // ── Clôture ──────────────────────────────────────────────────────────────

  openClose(trade: any): void {
    this.activeTradeId = trade.id;
    this.activeTicker  = trade.ticker;
    this.closeForm     = { exit_price: null, exit_date: TODAY };
    this.showCloseModal = true;
  }

  submitClose(): void {
    if (!this.closeForm.exit_price || !this.closeForm.exit_date) return;
    this.api.closeJournalTrade(this.activeTradeId, {
      exit_price: this.closeForm.exit_price!,
      exit_date:  this.closeForm.exit_date,
    }).subscribe({
      next: () => { this.showCloseModal = false; this.loadAll(); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur clôture'),
    });
  }

  // ── Notes ────────────────────────────────────────────────────────────────

  openNotes(trade: any): void {
    this.activeTradeId = trade.id;
    this.activeTicker  = trade.ticker;
    this.notesValue    = trade.notes || '';
    this.showNotesModal = true;
  }

  submitNotes(): void {
    this.api.patchJournalNotes(this.activeTradeId, this.notesValue).subscribe({
      next: () => { this.showNotesModal = false; this.loadTrades(); },
      error: e => this.error.set(e.error?.detail ?? 'Erreur notes'),
    });
  }

  // ── Suppression ──────────────────────────────────────────────────────────

  deleteTrade(trade: any): void {
    if (!confirm(`Supprimer le trade ${trade.ticker} ?`)) return;
    this.api.deleteJournalTrade(trade.id).subscribe({
      next: () => this.loadAll(),
      error: e => this.error.set(e.error?.detail ?? 'Erreur suppression'),
    });
  }

  // ── Helpers affichage ────────────────────────────────────────────────────

  pnlColor(pnl: number | null): string {
    if (pnl === null) return '#7a9bbb';
    return pnl > 0 ? '#2ecc71' : pnl < 0 ? '#e74c3c' : '#f1c40f';
  }

  directionColor(d: string): string {
    return d === 'LONG' ? '#2ecc71' : '#e74c3c';
  }

  strategyColor(s: string): string {
    const colors: Record<string, string> = {
      'Swing':      '#00c8ff',
      'Day Trading':'#ffa500',
      'Momentum':   '#2ecc71',
      'Breakout':   '#9b59b6',
      'Valeur':     '#f1c40f',
      'Contrarian': '#e74c3c',
      'Autre':      '#7a9bbb',
    };
    return colors[s] || '#7a9bbb';
  }

  winRateColor(wr: number): string {
    return wr >= 55 ? '#2ecc71' : wr >= 40 ? '#f1c40f' : '#e74c3c';
  }

  streakLabel(s: any): string {
    if (!s || !s.type) return '—';
    return s.type === 'win'
      ? `🔥 ${s.count} victoire${s.count > 1 ? 's' : ''} d'affilée`
      : `❄️ ${s.count} perte${s.count > 1 ? 's' : ''} d'affilée`;
  }

  goAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  // ── Equity Chart ─────────────────────────────────────────────────────────

  private _buildChart(stats: any): void {
    this._chart?.destroy();
    const canvas = this.equityCanvas?.nativeElement;
    if (!canvas || !stats?.equity_curve?.length) return;

    const curve  = stats.equity_curve as { date: string; cumul: number; pnl: number }[];
    const labels = curve.map(p => p.date);
    const data   = curve.map(p => p.cumul);
    const last   = data[data.length - 1];

    this._chart = new Chart(canvas, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label:           'P&L cumulé (€)',
          data,
          borderColor:     last >= 0 ? 'rgba(46,204,113,0.9)' : 'rgba(231,76,60,0.9)',
          backgroundColor: last >= 0 ? 'rgba(46,204,113,0.08)' : 'rgba(231,76,60,0.08)',
          borderWidth:     2,
          pointRadius:     curve.length <= 30 ? 4 : 0,
          pointHoverRadius:5,
          fill:            true,
          tension:         0.3,
        }, {
          label:       'Neutre',
          data:        labels.map(() => 0),
          borderColor: 'rgba(255,255,255,0.12)',
          borderWidth: 1,
          borderDash:  [4, 4],
          pointRadius: 0,
          fill:        false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: {
            ticks: { color: '#4a6a8a', maxTicksLimit: 8, font: { size: 10 } },
            grid:  { color: 'rgba(255,255,255,0.04)' },
          },
          y: {
            ticks: {
              color: '#4a6a8a',
              font:  { size: 10 },
              callback: v => `${v}€`,
            },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: 'rgba(10,15,30,0.92)',
            borderColor:     'rgba(0,200,255,0.2)',
            borderWidth: 1,
            callbacks: {
              label: ctx => {
                const p = curve[ctx.dataIndex];
                if (!p) return '';
                const sign = p.pnl >= 0 ? '+' : '';
                const y = ctx.parsed.y ?? 0;
                return [
                  ` Cumul : ${y.toFixed(2)}€`,
                  ` Trade : ${sign}${p.pnl.toFixed(2)}€`,
                ];
              },
            },
          },
        },
      },
    });
  }
}
