@echo off
rem Security Copilot: start the whole live demo with one double-click (Windows).
rem   1. tunnel to the GPU server's Qwen 14B (live LLM text), if reachable
rem   2. backend  (FastAPI, http://localhost:8000) with B's model loaded
rem   3. frontend (Next.js, http://localhost:3000) on the live API
rem   4. reset the demo and open Alice's mailbox and the admin console
rem Stop everything with stop_demo.bat.

setlocal
cd /d "%~dp0"
set "ROOT=%CD%"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [X] No Python venv at .venv. See CLAUDE.md: python -m venv .venv, then install backend\requirements.txt and requirements-ml.txt
  goto :fail
)
if not exist "%ROOT%\frontend\node_modules" (
  echo [..] Installing frontend packages once...
  pushd "%ROOT%\frontend" && call npm install --no-audit --no-fund && popd
)
if not exist "%ROOT%\frontend\.env.local" (
  echo NEXT_PUBLIC_API_URL=http://localhost:8000> "%ROOT%\frontend\.env.local"
  echo [ok] Created frontend\.env.local (live mode)
)

rem ---- 1. GPU server LLM (optional: everything works without it) -------------
echo [..] Checking the GPU server (Qwen 14B)...
ssh -o BatchMode=yes -o ConnectTimeout=10 lambda-gpu "curl -s -m 5 localhost:8001/health || (cd ~/hackyeah/work && nohup env HF_HOME=$HOME/hackyeah/hf HF_HUB_OFFLINE=1 ../.venv/bin/python serve_openai.py --port 8001 > ../logs/serve.log 2>&1 < /dev/null & sleep 60; curl -s -m 5 localhost:8001/health)" > "%TEMP%\copilot_gpu.txt" 2>nul
findstr /c:"true" "%TEMP%\copilot_gpu.txt" >nul
if errorlevel 1 (
  echo [!] GPU server not reachable: live text falls back to Ollama on this laptop, then templates. Demo emails still use the cached LLM text.
) else (
  start "Copilot - GPU tunnel" /min ssh -N -o ServerAliveInterval=30 -L 8001:localhost:8001 lambda-gpu
  echo [ok] GPU server up: tunnel to Qwen 14B on localhost:8001
)
powershell -NoProfile -Command "try { Invoke-RestMethod http://127.0.0.1:11434/api/version -TimeoutSec 3 | Out-Null; 'ok' } catch { 'no' }" | findstr ok >nul
if errorlevel 1 (echo [!] Ollama not running: no local LLM fallback) else (echo [ok] Ollama running: local qwen2.5:3b fallback)

rem ---- 2. backend ------------------------------------------------------------
start "Copilot - backend :8000" cmd /k "cd /d "%ROOT%\backend" && set DATABASE_URL=sqlite:///./demo.db&& "%ROOT%\.venv\Scripts\python.exe" -m uvicorn app.main:app --port 8000"

rem ---- 3. frontend -----------------------------------------------------------
start "Copilot - frontend :3000" cmd /k "cd /d "%ROOT%\frontend" && npm run dev -- --port 3000"

rem ---- 4. wait, reset, open ----------------------------------------------------
rem Checks use 127.0.0.1: Windows PowerShell tries IPv6 ::1 first for "localhost" and
rem only falls back after ~2 s, while uvicorn listens on IPv4 only.
echo [..] Waiting for backend and frontend (the model loads in ~10-30 s)...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 90;$i++){ try { Invoke-RestMethod http://127.0.0.1:8000/api/sim/attack/status -TimeoutSec 5 | Out-Null; Invoke-WebRequest http://127.0.0.1:3000/ -UseBasicParsing -TimeoutSec 30 | Out-Null; $ok=$true; break } catch { Start-Sleep 2 } }; if(-not $ok){ exit 1 }"
if errorlevel 1 (
  echo [X] Backend or frontend did not start. Check the two new windows for errors.
  goto :fail
)
powershell -NoProfile -Command "Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/sim/reset | Out-Null"
echo [ok] Demo reset
start "" "http://localhost:3000/user"
start "" "http://localhost:3000/admin"
echo.
echo Ready. Alice: http://localhost:3000/user   Admin: http://localhost:3000/admin (press D for demo controls)
echo Check the whole demo: .venv\Scripts\python scripts\ui_demo_test.py
endlocal
exit /b 0

:fail
endlocal
pause
exit /b 1
