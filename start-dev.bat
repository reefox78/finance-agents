@echo off
echo Lancement de Finance Agents (backend + frontend)...

:: Backend FastAPI dans un nouveau terminal
start "Backend FastAPI :8000" cmd /k "cd /d %~dp0 && call venv\Scripts\activate && pip install -r backend/requirements-backend.txt -q && uvicorn backend.main:app --reload"

:: Attendre 2s que le backend démarre
timeout /t 2 /nobreak >nul

:: Frontend Angular dans un nouveau terminal
start "Frontend Angular :4200" cmd /k "cd /d %~dp0frontend && npx ng serve --open"

echo.
echo Backend  → http://localhost:8000/docs
echo Frontend → http://localhost:4200
