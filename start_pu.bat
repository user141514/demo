@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Meitai Demo - Full Stack with Ngrok Public URL
echo ============================================================
echo.

:: ---- Terminal 1: Backend ----
echo [1/3] Starting backend (uvicorn on :8000)...
call "%~dp0scripts\back_start.bat"
timeout /t 3 /nobreak >nul
echo [OK] Backend: http://localhost:8000

:: ---- Terminal 2: Ngrok to frontend ----
echo.
echo [2/3] Starting ngrok tunnel to frontend :3001...

set "NGROK_EXE=%USERPROFILE%\ngrok\ngrok.exe"
if not exist "%NGROK_EXE%" set "NGROK_EXE=E:\ngrok-v3-stable-windows-amd64\ngrok.exe"
if not exist "%NGROK_EXE%" (
    echo [ERROR] ngrok not found
    pause && exit /b 1
)

taskkill /F /IM ngrok.exe >nul 2>&1
timeout /t 1 /nobreak >nul

start "Meitai Ngrok" cmd /k "%NGROK_EXE% http 3001 --log=stdout"

echo [3/3] Waiting for ngrok public URL...
set "PUBLIC_URL="
for /l %%i in (1,1,20) do (
    timeout /t 2 /nobreak >nul
    for /f "delims=" %%u in ('node "scripts\ngrok_url.js" 2^>nul') do set "PUBLIC_URL=%%u"
    if not "!PUBLIC_URL!"=="" goto :got_url
    echo        Waiting... (%%i/20)
)
echo [WARNING] Could not get ngrok URL - using localhost
set "PUBLIC_URL=http://localhost:3001"

:got_url
echo        Public URL: !PUBLIC_URL!

:: Write API base URL so browser fetch() goes through ngrok -> Next.js proxy -> backend
echo NEXT_PUBLIC_API_BASE_URL=!PUBLIC_URL!> frontend\.env.local
echo [OK] .env.local written

:: ---- Terminal 3: Frontend ----
echo.
echo [3/3] Starting frontend (Next.js on :3001)...
start "Meitai Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"
timeout /t 2 /nobreak >nul

:: ---- Done ----
echo.
echo ============================================================
echo   All services running!
echo.
echo   Backend:   http://localhost:8000
echo   Frontend:  http://localhost:3001
echo   Public:    !PUBLIC_URL!
echo.
echo   Share this URL: !PUBLIC_URL!
echo ============================================================
echo.
pause >nul
endlocal
