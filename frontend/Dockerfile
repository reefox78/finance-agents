# ── Stage 1 : Build Angular ────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Installer les dépendances en premier (layer cache)
COPY frontend/package*.json ./
RUN npm ci --prefer-offline

# Copier les sources et builder en production
COPY frontend/ .
RUN npm run build

# ── Stage 2 : Servir avec nginx ────────────────────────────────────────
FROM nginx:alpine

# Copier le build Angular (Angular 17+ : dist/{nom}/browser/)
COPY --from=builder /app/dist/frontend/browser /usr/share/nginx/html

# Config nginx custom (SPA + proxy API)
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
