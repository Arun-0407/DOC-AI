@echo off
title DOC AI - Starting...
echo.
echo ============================================================
echo   DOC AI - Starting all services
echo ============================================================
echo.

REM ── 1. Start SAP RFC Bridge (Node.js) in background ─────────────────────────
echo [1/2] Starting SAP RFC Bridge on port 5001...
start "SAP RFC Bridge" /MIN cmd /c "cd /d "%~dp0backend" && node sap_rfc_bridge.js"
timeout /t 3 /nobreak >nul

REM ── 2. Start Python FastAPI backend ─────────────────────────────────────────
echo [2/2] Starting Python backend on port 8000...
start "DOC AI Backend" cmd /c "cd /d "%~dp0backend" && call venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo ============================================================
echo   Services starting:
echo     SAP RFC Bridge : http://127.0.0.1:5001
echo     Python Backend : http://127.0.0.1:8000
echo     Frontend       : http://localhost:3000
echo.
echo   Open your browser at: http://localhost:3000/sap-search
echo ============================================================
echo.
echo Press any key to exit this window (services keep running)...
pause >nul
