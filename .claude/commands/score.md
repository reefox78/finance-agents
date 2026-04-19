Explique en détail comment le score est calculé pour un ticker donné : $ARGUMENTS

1. Lis `orchestrator/scoring.py` — logique du score composite
2. Lis `orchestrator/orchestrator.py` — pipeline complet
3. Lis `agents/sector_risk.py` — multiplicateur sectoriel
4. Lis `data/asset_type.py` — config par type d'actif

Explique étape par étape :
- Quels agents sont appelés pour ce type d'actif
- Comment les scores partiels sont combinés (poids)
- Comment mult_macro et mult_secteur modifient le score final
- Donne un exemple chiffré avec des valeurs typiques

Si un ticker spécifique est donné, précise quel secteur serait détecté et quel driver sectoriel s'appliquerait.
