import { Component, OnInit } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { KeepaliveService } from './core/services/keepalive.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: '<router-outlet />',
})
export class App implements OnInit {
  constructor(private keepalive: KeepaliveService) {}

  ngOnInit(): void {
    this.keepalive.start();
  }
}
