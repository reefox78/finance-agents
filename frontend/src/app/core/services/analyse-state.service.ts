import { Injectable } from '@angular/core';

/**
 * Persiste l'état de la page Analyse entre les navigations.
 * Singleton (providedIn: root) → survit aux changements de route.
 */
@Injectable({ providedIn: 'root' })
export class AnalyseStateService {
  ticker       = '';
  customTicker = '';
  period       = '3mo';
  withLlm      = true;
  result: any  = null;
  error        = '';
}
