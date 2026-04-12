import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { AdminService, AdminUser } from '../../core/services/admin.service';
import { AuthService } from '../../core/services/auth.service';

interface ResetModal {
  user: AdminUser;
  password: string;
  confirm: string;
  error: string;
}

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.scss',
})
export class AdminComponent implements OnInit {
  users    = signal<AdminUser[]>([]);
  loading  = signal(false);
  error    = signal('');
  toast    = signal('');

  resetModal = signal<ResetModal | null>(null);
  confirmDelete = signal<AdminUser | null>(null);

  constructor(
    private adminService: AdminService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.adminService.getUsers().subscribe({
      next:  u  => { this.users.set(u); this.loading.set(false); },
      error: e  => { this.error.set(e.error?.detail ?? 'Erreur réseau'); this.loading.set(false); },
    });
  }

  openReset(user: AdminUser): void {
    this.resetModal.set({ user, password: '', confirm: '', error: '' });
  }

  submitReset(): void {
    const m = this.resetModal();
    if (!m) return;
    if (m.password.length < 8) {
      this.resetModal.set({ ...m, error: 'Minimum 8 caractères.' });
      return;
    }
    if (m.password !== m.confirm) {
      this.resetModal.set({ ...m, error: 'Les mots de passe ne correspondent pas.' });
      return;
    }
    this.adminService.resetPassword(m.user.id, m.password).subscribe({
      next: () => {
        this.resetModal.set(null);
        this._toast(`Mot de passe de ${m.user.username} réinitialisé.`);
      },
      error: e => this.resetModal.set({ ...m, error: e.error?.detail ?? 'Erreur' }),
    });
  }

  toggleActive(user: AdminUser): void {
    this.adminService.toggleActive(user.id).subscribe({
      next: r => {
        this.users.update(list =>
          list.map(u => u.id === user.id ? { ...u, is_active: r.is_active } : u)
        );
        this._toast(`${user.username} : ${r.is_active ? 'activé' : 'désactivé'}`);
      },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  toggleAdmin(user: AdminUser): void {
    this.adminService.toggleAdmin(user.id).subscribe({
      next: r => {
        this.users.update(list =>
          list.map(u => u.id === user.id ? { ...u, is_admin: r.is_admin } : u)
        );
        this._toast(`${user.username} : rôle ${r.is_admin ? 'admin' : 'utilisateur'}`);
      },
      error: e => this.error.set(e.error?.detail ?? 'Erreur'),
    });
  }

  confirmDel(user: AdminUser): void { this.confirmDelete.set(user); }

  deleteUser(): void {
    const user = this.confirmDelete();
    if (!user) return;
    this.adminService.deleteUser(user.id).subscribe({
      next: () => {
        this.users.update(list => list.filter(u => u.id !== user.id));
        this.confirmDelete.set(null);
        this._toast(`${user.username} supprimé.`);
      },
      error: e => { this.confirmDelete.set(null); this.error.set(e.error?.detail ?? 'Erreur'); },
    });
  }

  isSelf(user: AdminUser): boolean {
    return user.id === this.auth.currentUser()?.user_id;
  }

  countActive():   number { return this.users().filter(u => u.is_active).length; }
  countAdmins():   number { return this.users().filter(u => u.is_admin).length; }
  sumPositions():  number { return this.users().reduce((s, u) => s + u.nb_positions, 0); }

  private _toast(msg: string): void {
    this.toast.set(msg);
    setTimeout(() => this.toast.set(''), 3500);
  }
}
