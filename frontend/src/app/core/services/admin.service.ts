import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AdminUser {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  nb_positions: number;
  nb_transactions: number;
}

@Injectable({ providedIn: 'root' })
export class AdminService {
  private base = `${environment.apiUrl}/admin`;

  constructor(private http: HttpClient) {}

  getUsers(): Observable<AdminUser[]> {
    return this.http.get<AdminUser[]>(`${this.base}/users`);
  }

  resetPassword(userId: string, newPassword: string): Observable<any> {
    return this.http.post(`${this.base}/users/${userId}/reset-password`, { new_password: newPassword });
  }

  toggleActive(userId: string): Observable<{ is_active: boolean }> {
    return this.http.post<{ is_active: boolean }>(`${this.base}/users/${userId}/toggle-active`, {});
  }

  toggleAdmin(userId: string): Observable<{ is_admin: boolean }> {
    return this.http.post<{ is_admin: boolean }>(`${this.base}/users/${userId}/toggle-admin`, {});
  }

  deleteUser(userId: string): Observable<any> {
    return this.http.delete(`${this.base}/users/${userId}`);
  }
}
