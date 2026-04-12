export const environment = {
  production: true,
  // URL relative → nginx proxie /api/ vers le backend (Docker ou tout reverse-proxy)
  // Pour Render / hébergement externe, configurer le reverse-proxy en conséquence.
  apiUrl: '/api',
};
