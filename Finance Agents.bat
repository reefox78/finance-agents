@echo off
title Finance Agents
cd /d "%~dp0"

:: Recherche du Python disponible (venv en priorité, sinon PATH)
if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else (
    set PYTHON=python
)

echo.
echo  ============================================
echo    Finance Agents -- Demarrage
echo  ============================================
echo.
echo  Dashboard  ->  http://localhost:8501
echo  Alertes    ->  surveillance automatique
echo.
echo  Fermer cette fenetre pour tout arreter.
echo.

%PYTHON% start.py

pause
