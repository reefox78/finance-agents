@echo off
title Finance Agents - Dev
cd /d "%~dp0"

:: Stocker le chemin racine dans une variable (avec backslash final)
set "ROOT=%~dp0"

:: Trouver Python (venv en priorite)
if exist "%ROOT%venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%venv\Scripts\python.exe"
) else if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

cls
echo.
echo  ============================================================
echo    Finance Agents - Dev Server
echo  ============================================================
echo.
echo  Python : %PYTHON%
echo  Racine : %ROOT%
echo.


:: ============================================================
::  1/4  Tests Python
:: ============================================================
echo  [1/4]  Tests Python (pytest)
echo  ------------------------------------------------------------
echo.

"%PYTHON%" -m pytest "%ROOT%tests" -v --tb=short
set "PYTEST_CODE=%ERRORLEVEL%"
echo.

if %PYTEST_CODE% NEQ 0 (
    echo  ============================================================
    echo    ERREUR - Tests Python KO
    echo    Corriger les erreurs puis relancer start-dev.bat
    echo  ============================================================
    echo.
    pause
    exit /b 1
)

echo  [OK] Tests Python : tous passes
echo.


:: ============================================================
::  2/4  Tests Angular
:: ============================================================
echo  [2/4]  Tests Angular (vitest / jsdom)
echo  ------------------------------------------------------------
echo.

cd "%ROOT%frontend"
call npm run test:ci
set "NPM_CODE=%ERRORLEVEL%"
cd "%ROOT%"
echo.

if %NPM_CODE% NEQ 0 (
    echo  ============================================================
    echo    ERREUR - Tests Angular KO
    echo    Corriger les erreurs puis relancer start-dev.bat
    echo  ============================================================
    echo.
    pause
    exit /b 1
)

echo  [OK] Tests Angular : tous passes
echo.


:: ============================================================
::  3/4  Lancement Backend
:: ============================================================
echo  [3/4]  Demarrage Backend  http://localhost:8000
echo  ------------------------------------------------------------

start "Backend :8000" cmd /k ""%PYTHON%" "%ROOT%backend\start.py" --skip-tests"

echo  Fenetre Backend :8000 ouverte.
echo.


:: ============================================================
::  4/4  Lancement Frontend
:: ============================================================
echo  [4/4]  Demarrage Frontend  http://localhost:4200
echo  ------------------------------------------------------------

start "Frontend :4200" /d "%ROOT%frontend" cmd /k "npm run serve"

echo  Fenetre Frontend :4200 ouverte.
echo.


:: ============================================================
::  Recap final
:: ============================================================
echo  ============================================================
echo    Tous les tests passes - serveurs demarres !
echo.
echo    Frontend  ->  http://localhost:4200
echo    Backend   ->  http://localhost:8000
echo    API Docs  ->  http://localhost:8000/docs
echo.
echo    Fermer les fenetres Backend et Frontend pour arreter.
echo  ============================================================
echo.
pause
