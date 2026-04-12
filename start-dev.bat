@echo off
chcp 65001 > nul
title Finance Agents — Dev
cd /d "%~dp0"

:: ── Trouver Python (venv en priorité) ─────────────────────────────────────
if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
) else (
    set PYTHON=python
)

cls
echo.
echo  ============================================================
echo    Finance Agents ^|^| Dev Server
echo  ============================================================
echo.


:: ══════════════════════════════════════════════════════════════
::  ETAPE 1/4  Tests Python (pytest)
:: ══════════════════════════════════════════════════════════════
echo  [1/4]  Tests Python
echo  ------------------------------------------------------------
echo.
%PYTHON% -m pytest tests/ -v --tb=short --color=yes
echo.

if %ERRORLEVEL% NEQ 0 (
    echo  ============================================================
    echo    ERREUR  ^|^|  Tests Python KO
    echo    Corriger les erreurs ci-dessus puis relancer start-dev.bat
    echo  ============================================================
    echo.
    pause
    exit /b 1
)

echo  [OK] Tests Python : tous passes
echo.


:: ══════════════════════════════════════════════════════════════
::  ETAPE 2/4  Tests Angular (vitest / jsdom)
:: ══════════════════════════════════════════════════════════════
echo  [2/4]  Tests Angular
echo  ------------------------------------------------------------
echo.
cd frontend
call npm run test:ci
cd ..
echo.

if %ERRORLEVEL% NEQ 0 (
    echo  ============================================================
    echo    ERREUR  ^|^|  Tests Angular KO
    echo    Corriger les erreurs ci-dessus puis relancer start-dev.bat
    echo  ============================================================
    echo.
    pause
    exit /b 1
)

echo  [OK] Tests Angular : tous passes
echo.


:: ══════════════════════════════════════════════════════════════
::  ETAPE 3/4  Lancement Backend  (tests deja valides)
:: ══════════════════════════════════════════════════════════════
echo  [3/4]  Demarrage Backend  http://localhost:8000
echo  ------------------------------------------------------------
start "Backend :8000" cmd /k "%PYTHON% backend\start.py --skip-tests"
echo  OK - fenetre "Backend :8000" ouverte
echo.


:: ══════════════════════════════════════════════════════════════
::  ETAPE 4/4  Lancement Frontend (ng serve direct, tests deja faits)
:: ══════════════════════════════════════════════════════════════
echo  [4/4]  Demarrage Frontend  http://localhost:4200
echo  ------------------------------------------------------------
start "Frontend :4200" cmd /k "cd /d %~dp0frontend && npm run serve"
echo  OK - fenetre "Frontend :4200" ouverte
echo.


:: ══════════════════════════════════════════════════════════════
::  Recap
:: ══════════════════════════════════════════════════════════════
echo  ============================================================
echo    Tous les tests sont passes  --  serveurs demarres !
echo.
echo    Frontend  -^>  http://localhost:4200
echo    Backend   -^>  http://localhost:8000
echo    API Docs  -^>  http://localhost:8000/docs
echo.
echo    Fermer les fenetres "Backend" et "Frontend" pour arreter
echo  ============================================================
echo.
pause
