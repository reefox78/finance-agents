import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface AuthUser {
  user_id: string;
  username: string;
  email: string;
  is_admin?: boolean;
}

interface TokenResponse extends AuthUser {
  access_token: string;
  token_type: string;
  is_admin: boolean;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'fa_token';
  private readonly USER_KEY  = 'fa_user';

  currentUser = signal<AuthUser | null>(this._loadUser());

  constructor(private http: HttpClient, private router: Router) {}

  get token(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  get isLoggedIn(): boolean {
    return !!this.token;
  }

  login(email: string, password: string) {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/login`, { email, password })
      .pipe(tap(res => this._saveSession(res)));
  }

  register(username: string, email: string, password: string) {
    return this.http
      .post<TokenResponse>(`${environment.apiUrl}/auth/register`, { username, email, password })
      .pipe(tap(res => this._saveSession(res)));
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    this.router.navigate(['/auth']);
  }

  get isAdmin(): boolean {
    return !!this.currentUser()?.is_admin;
  }

  private _saveSession(res: TokenResponse): void {
    localStorage.setItem(this.TOKEN_KEY, res.access_token);
    const user: AuthUser = {
      user_id:  res.user_id,
      username: res.username,
      email:    res.email,
      is_admin: res.is_admin ?? false,
    };
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    this.currentUser.set(user);
  }

  private _loadUser(): AuthUser | null {
    try {
      const raw = localStorage.getItem(this.USER_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }
}
