@echo off
chcp 65001 >nul
set "ROOT=%~dp0"

echo ============================================================
echo  J280 Showcase Upper Computer
echo  NOTE: Keep the proven V5.12 tuner running in the background.
echo ============================================================
echo.

if not exist "%ROOT%backend\main.py" (
  echo [ERROR] backend\main.py not found.
  pause
  exit /b 1
)

if not exist "%ROOT%frontend\package.json" (
  echo [ERROR] frontend\package.json not found.
  pause
  exit /b 1
)

start "J280 Showcase Backend" /D "%ROOT%backend" cmd /k "python -m uvicorn main:app --host 127.0.0.1 --port 8000"
start "J280 Showcase Frontend" /D "%ROOT%frontend" cmd /k "npm run dev"

timeout /t 3 /nobreak >nul
start "" "http://localhost:5173"
exit /b 0
