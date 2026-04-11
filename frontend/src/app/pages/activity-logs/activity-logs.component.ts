import { Component, OnInit, signal, computed, ElementRef, ViewChild, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../core/services/api.service';

type Level = 'all' | 'error' | 'warning' | 'success' | 'info';

@Component({
  selector: 'app-activity-logs',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './activity-logs.component.html',
  styleUrls: ['./activity-logs.component.scss'],
})
export class ActivityLogsComponent implements OnInit, AfterViewChecked {
  @ViewChild('logViewer') logViewer?: ElementRef<HTMLDivElement>;

  files        = signal<any[]>([]);
  selected     = signal<any | null>(null);
  lines        = signal<any[]>([]);
  loading      = signal(false);
  loadingFiles = signal(false);
  error        = signal('');
  filter       = signal<Level>('all');
  autoScroll   = true;
  private _shouldScroll = false;

  filteredLines = computed(() => {
    const lvl = this.filter();
    const all = this.lines();
    if (lvl === 'all') return all;
    return all.filter(l => l.level === lvl);
  });

  errorCount   = computed(() => this.lines().filter(l => l.level === 'error').length);
  warningCount = computed(() => this.lines().filter(l => l.level === 'warning').length);
  successCount = computed(() => this.lines().filter(l => l.level === 'success').length);

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.loadFiles();
  }

  ngAfterViewChecked(): void {
    if (this._shouldScroll && this.autoScroll && this.logViewer) {
      const el = this.logViewer.nativeElement;
      el.scrollTop = el.scrollHeight;
      this._shouldScroll = false;
    }
  }

  loadFiles(): void {
    this.loadingFiles.set(true);
    this.error.set('');
    this.api.getLogFiles().subscribe({
      next: files => { this.files.set(files); this.loadingFiles.set(false); },
      error: e => {
        this.error.set(e.error?.detail ?? 'Impossible de charger les fichiers de log.');
        this.loadingFiles.set(false);
      },
    });
  }

  selectFile(file: any): void {
    if (this.selected()?.name === file.name) return;
    this.selected.set(file);
    this.lines.set([]);
    this.filter.set('all');
    this.loading.set(true);
    this.api.getLogContent(file.name).subscribe({
      next: data => {
        this.lines.set(data.lines ?? []);
        this.loading.set(false);
        this._shouldScroll = true;
      },
      error: e => {
        this.error.set(e.error?.detail ?? 'Erreur de lecture du fichier.');
        this.loading.set(false);
      },
    });
  }

  setFilter(lvl: Level): void {
    this.filter.set(lvl);
    this._shouldScroll = true;
  }

  componentIcon(comp: string): string {
    const icons: Record<string, string> = {
      dashboard: '🖥️',
      scheduler: '⏱️',
    };
    return icons[comp] ?? '📄';
  }
}
