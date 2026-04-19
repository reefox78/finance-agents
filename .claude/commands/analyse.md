Analyse le ticker boursier fourni en argument : $ARGUMENTS

1. Appelle l'API locale ou Render :
   - Local : `curl -s "http://localhost:8000/api/analyse/$ARGUMENTS?with_llm=false&period=3mo" -H "Authorization: Bearer $SKILL_API_KEY"`
   - Ou lis directement les fichiers de code concernés si l'API n'est pas dispo

2. Si l'API ne répond pas, analyse le code de scoring pour expliquer comment le ticker serait scoré :
   - Lis `orchestrator/scoring.py` pour la logique de score
   - Lis `agents/sector_risk.py` pour le risque sectoriel
   - Lis `data/asset_type.py` pour le type d'actif

3. Présente le résultat :
   - 🟢 ACHETER si score > 0.1
   - 🟡 NEUTRE si score entre -0.1 et 0.1
   - 🔴 VENDRE si score < -0.1
   - Détails : RSI, MACD, tendance, risque sectoriel, risque macro
