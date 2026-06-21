@echo off
echo ============================================
echo  Investment Strategy - 一键启动
echo ============================================
echo.

cd /d "%~dp0backend"
start "Backend" cmd /k "python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
echo [OK] Backend  starting on http://localhost:8000

timeout /t 3 >nul

cd /d "%~dp0frontend"
start "Frontend" cmd /k "npm run dev -- --host 127.0.0.1 --port 5173"
echo [OK] Frontend starting on http://localhost:5173

echo.
echo Waiting for services to be ready...
timeout /t 5 >nul
echo.
echo Opening http://localhost:5173 in browser...
start http://localhost:5173
pause
