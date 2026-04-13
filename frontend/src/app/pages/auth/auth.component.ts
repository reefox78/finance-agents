import { Component, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './auth.component.html',
  styleUrl: './auth.component.scss',
})
export class AuthComponent {
  mode: 'login' | 'register' = 'login';
  loading = signal(false);
  error   = signal('');

  // Login fields
  email    = '';
  password = '';

  // Register extra fields
  username = '';

  constructor(private auth: AuthService, private router: Router) {
    if (auth.isLoggedIn) this.router.navigate(['/dashboard']);
  }

  submit(): void {
    this.error.set('');
    this.loading.set(true);

    const obs = this.mode === 'login'
      ? this.auth.login(this.email, this.password)
      : this.auth.register(this.username, this.email, this.password);

    obs.subscribe({
      next: () => this.router.navigate(['/dashboard']),
      error: (err) => {
        const detail = err.error?.detail;
        const status = err.status ? ` (${err.status})` : '';
        this.error.set(detail ?? `Erreur réseau${status}`);
        this.loading.set(false);
      },
    });
  }

  toggle(): void {
    this.mode = this.mode === 'login' ? 'register' : 'login';
    this.error.set('');
  }
}
