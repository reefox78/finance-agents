Diagnostique les erreurs du projet finance-agents.

1. Lis les fichiers de logs récents dans `logs/` (les plus récents en premier)
2. Cherche les patterns d'erreur :
   - `ERROR`, `CRITICAL`, `Exception`, `Traceback` dans les logs backend
   - Erreurs TypeScript/Angular dans les fichiers du frontend si mentionnées
3. Vérifie les fichiers de config critiques :
   - `backend/.env` existe-t-il ? (sans afficher son contenu)
   - `config/watchlist.json` est-il valide JSON ?
4. Résume les erreurs trouvées par ordre de gravité
5. Propose un fix pour chaque erreur identifiée
