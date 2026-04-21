import { Component, signal, ViewChild, ElementRef, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { forkJoin, Subscription } from 'rxjs';
import { Chart, registerables } from 'chart.js';
import { ApiService } from '../../core/services/api.service';
import { WATCHLIST, WATCHLIST_CATEGORIES, TICKER_NAMES } from '../../core/constants/watchlist';

Chart.register(...registerables);

// Agents à afficher dans le tableau de comparaison
const COMPARE_AGENTS = [
  { key: 'technique',         label: 'Technique' },
  { key: 'fondamental',       label: 'Fondamental' },
  { key: 'sentiment',         label: 'Sentiment' },
  { key: 'macro',             label: 'Macro' },
  { key: 'trends',            label: 'Trends' },
  { key: 'insider',           label: 'Insider' },
  { key: 'options_flow',      label: 'Options Flow' },
  { key: 'short_interest',    label: 'Short Interest' },
  { key: 'earnings_surprise', label: 'Earnings' },
  { key: 'volume_delta',      label: 'Volume Delta' },
];

// Multiplicateurs affichés séparément
const COMPARE_MULTS = [
  { key: 'multiplicateur', label: '× Risque' },
  { key: 'mult_macro',     label: '× Macro' },
  { key: 'mult_secteur',   label: '× Secteur' },
  { key: 'mult_momentum',  label: '× Momentum' },
];

// Axes du radar (agents les plus universels)
const RADAR_AXES = [
  { key: 'technique',         label: 'Technique' },
  { key: 'fondamental',       label: 'Fondamental' },
  { key: 'sentiment',         label: 'Sentiment' },
  { key: 'macro',             label: 'Macro' },
  { key: 'earnings_surprise', label: 'Earnings' },
  { key: 'trends',            label: 'Trends' },
];

const TICKER_COLORS = [
  { border: 'rgba(0,200,255,0.9)',   bg: 'rgba(0,200,255,0.13)',  hex: '#00c8ff' },
  { border: 'rgba(46,204,113,0.9)',  bg: 'rgba(46,204,113,0.13)', hex: '#2ecc71' },
  { border: 'rgba(255,165,0,0.9)',   bg: 'rgba(255,165,0,0.13)',  hex: '#ffa500' },
];

@Component({
  selector: 'app-compare',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './compare.component.html',
  styleUrl: './compare.component.scss',
})
export class CompareComponent implements OnDestroy {
  @ViewChild('radarCanvas') radarCanvas!: ElementRef<HTMLCanvasElement>;

  readonly watchlist  = WATCHLIST;
  readonly categories = WATCHLIST_CATEGORIES;
  readonly agents     = COMPARE_AGENTS;
  readonly mults      = COMPARE_MULTS;
  readonly colors     = TICKER_COLORS;

  // Slots de sélection (2 par défaut, max 3)
  slots: string[] = ['AAPL', 'MSFT'];

  period   = '3mo';
  loading  = signal(false);
  results  = signal<any[]>([]);
  error    = signal('');

  private _radarChart: Chart | null = null;
  private _sub: Subscription | null = null;

  constructor(private api: ApiService, private router: Router) {}

  ngOnDestroy(): void {
    this._sub?.unsubscribe();
    this._radarChart?.destroy();
  }

  // ── Gestion des slots ─────────────────────────────────────────────────────

  get activeTickers(): string[] {
    return this.slots.map(t => t.trim().toUpperCase()).filter(Boolean);
  }

  get canCompare(): boolean {
    return this.activeTickers.length >= 2 && !this.loading();
  }

  addSlot(): void {
    if (this.slots.length < 3) this.slots.push('');
  }

  removeSlot(i: number): void {
    if (this.slots.length > 2) this.slots = this.slots.filter((_, idx) => idx !== i);
  }

  label(t: string): string {
    return TICKER_NAMES[t] ? `${t} (${TICKER_NAMES[t]})` : t;
  }

  // ── Lancement ─────────────────────────────────────────────────────────────

  compare(): void {
    const tickers = this.activeTickers;
    if (tickers.length < 2) return;

    this.error.set('');
    this.results.set([]);
    this._radarChart?.destroy();
    this._radarChart = null;
    this.loading.set(true);

    const requests = tickers.map(t =>
      this.api.analyse(t, false, false, this.period)
    );

    this._sub = forkJoin(requests).subscribe({
      next: (rs: any[]) => {
        this.results.set(rs);
        this.loading.set(false);
        setTimeout(() => this._buildRadar(rs), 60);
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur lors de la comparaison');
        this.loading.set(false);
      },
    });
  }

  // ── Helpers d'affichage ───────────────────────────────────────────────────

  scoreColor(s: number | null): string {
    if (s === null) return '#4a6a8a';
    return s >= 0.1 ? '#2ecc71' : s <= -0.1 ? '#e74c3c' : '#f1c40f';
  }

  decisionColor(d: string): string {
    if (d === 'ACHETER') return '#2ecc71';
    if (d === 'VENDRE')  return '#e74c3c';
    return '#f1c40f';
  }

  agentScore(r: any, key: string): number | null {
    const v = r?.scoring?.scores?.[key];
    return v !== undefined && v !== null ? v : null;
  }

  // Renvoie le meilleur score parmi les résultats pour cet agent (le plus élevé)
  bestForAgent(key: string): number | null {
    const vals = this.results()
      .map(r => this.agentScore(r, key))
      .filter((v): v is number => v !== null);
    return vals.length ? Math.max(...vals) : null;
  }

  isBest(r: any, key: string): boolean {
    const s    = this.agentScore(r, key);
    const best = this.bestForAgent(key);
    return s !== null && best !== null && s === best && this.results().length > 1;
  }

  // Multiplicateur : le plus proche de 1 n'est pas forcément le meilleur
  // Pour risque/macro/secteur/momentum, le plus grand = le meilleur
  isBestFinal(r: any): boolean {
    const scores = this.results().map(x => x?.scoring?.score_final ?? -99);
    return r?.scoring?.score_final === Math.max(...scores) && this.results().length > 1;
  }

  isBestMult(r: any, key: string): boolean {
    const v = r?.scoring?.scores?.[key];
    if (v === undefined || v === null) return false;
    const all = this.results()
      .map(res => res?.scoring?.scores?.[key])
      .filter(x => x !== undefined && x !== null) as number[];
    return Math.max(...all) === v && this.results().length > 1;
  }

  /** Score de la jauge (0-100) pour le bargraph horizontal */
  scoreBar(score: number): number {
    return Math.round(((score + 1) / 2) * 100);
  }

  /** Aiguille gauge SVG (mini) */
  needle(score: number): { x2: number; y2: number } {
    const c = Math.max(-1, Math.min(1, score));
    const angleDeg = 180 - ((c + 1) / 2) * 180;
    const rad = (angleDeg * Math.PI) / 180;
    return {
      x2: Math.round((65 + 45 * Math.cos(rad)) * 10) / 10,
      y2: Math.round((65 - 45 * Math.sin(rad)) * 10) / 10,
    };
  }

  goAnalyse(ticker: string): void {
    this.router.navigate(['/dashboard/analyse'], { queryParams: { ticker } });
  }

  // ── Radar Chart ───────────────────────────────────────────────────────────

  private _buildRadar(rs: any[]): void {
    const canvas = this.radarCanvas?.nativeElement;
    if (!canvas) return;

    const datasets = rs.map((r, i) => ({
      label: r.ticker,
      data: RADAR_AXES.map(a => {
        const s = r?.scoring?.scores?.[a.key] ?? 0;
        return Math.round(((s + 1) / 2) * 100);  // [-1,1] → [0,100]
      }),
      borderColor:      TICKER_COLORS[i % TICKER_COLORS.length].border,
      backgroundColor:  TICKER_COLORS[i % TICKER_COLORS.length].bg,
      borderWidth: 2,
      pointRadius: 4,
      pointBackgroundColor: TICKER_COLORS[i % TICKER_COLORS.length].border,
    }));

    this._radarChart = new Chart(canvas, {
      type: 'radar',
      data: { labels: RADAR_AXES.map(a => a.label), datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          r: {
            min: 0, max: 100,
            ticks: {
              stepSize: 25,
              color: '#4a6a8a',
              backdropColor: 'transparent',
              font: { size: 9 },
            },
            grid:        { color: 'rgba(255,255,255,0.06)' },
            angleLines:  { color: 'rgba(255,255,255,0.06)' },
            pointLabels: { color: '#7a9bbb', font: { size: 11, weight: 600 as any } },
          },
        },
        plugins: {
          legend: {
            labels: { color: '#9ab5cc', font: { size: 12 }, boxWidth: 14, padding: 16 },
          },
          tooltip: {
            backgroundColor: 'rgba(10,15,30,0.92)',
            borderColor: 'rgba(0,200,255,0.2)',
            borderWidth: 1,
            callbacks: {
              label: (ctx) => {
                const raw = ctx.raw as number;
                const score = (((raw / 100) * 2) - 1).toFixed(3);
                return ` ${ctx.dataset.label} : ${score}`;
              },
            },
          },
        },
      },
    });
  }
}
