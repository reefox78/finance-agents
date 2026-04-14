import {
  Component, Input, Output, EventEmitter,
  OnChanges, OnDestroy, SimpleChanges,
  signal, computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-loading-overlay',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './loading-overlay.component.html',
  styleUrl: './loading-overlay.component.scss',
})
export class LoadingOverlayComponent implements OnChanges, OnDestroy {
  /** Affiche ou cache l'overlay */
  @Input() active = false;
  /** Texte en majuscules affiché sous la barre segmentée */
  @Input() label = 'CHARGEMENT…';
  /** Message d'erreur venant du parent (vide = pas d'erreur) */
  @Input() errorMsg = '';

  /** Émis quand l'utilisateur clique sur ✕ */
  @Output() cancelled = new EventEmitter<void>();

  readonly segs = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16];

  elapsedSeconds = signal(0);
  /** Croix visible après 60 s ou si une erreur est présente */
  showCloseBtn   = computed(() => this.elapsedSeconds() >= 60 || this.errorMsg !== '');

  private _timer: any = null;

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['active']) {
      if (this.active) {
        this.elapsedSeconds.set(0);
        this._startTimer();
      } else {
        this._stopTimer();
      }
    }
  }

  ngOnDestroy(): void { this._stopTimer(); }

  cancel(): void {
    this._stopTimer();
    this.cancelled.emit();
  }

  private _startTimer(): void {
    this._stopTimer();
    this._timer = setInterval(() => this.elapsedSeconds.update(s => s + 1), 1000);
  }

  private _stopTimer(): void {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  }
}
