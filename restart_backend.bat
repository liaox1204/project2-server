@echo off
setlocal

echo ============================================
echo  Restart Silver AI Voice Assistant Backend
echo ============================================
echo.

REM Clear proxy settings: a system proxy in the shell will make the
REM ASR endpoint return 403 and the LLM call time out.
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set ALL_PROXY=
set all_proxy=
echo       Proxy env cleared.

REM Pick an interpreter that actually has the deps installed.
set "PY=D:\python1\FastAPIProject\FastAPIpymysql\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=%~dp0.venv\Scripts\python.exe"

echo [1/3] Checking interpreter ...
echo       %PY%
if not exist "%PY%" (
    echo       ERROR: python not found. Edit PY= in this file.
    pause
    exit /b 1
)
"%PY%" -c "import fastapi,uvicorn,openai,langchain_openai" >nul 2>&1
if errorlevel 1 (
    echo       ERROR: deps missing in this interpreter.
    echo       Run:  "%PY%" -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo       OK
echo.

echo [2/3] Stopping process on port 8000 ...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
    echo       Killing PID %%a
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 >nul
echo.

echo [3/3] Starting backend (--reload) ...
cd /d "%~dp0"
echo       Working dir: %CD%
echo       Docs:  http://127.0.0.1:8000/docs
echo       Logs:  %CD%\logs\backend.log
echo.

"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload

echo.
echo Backend exited. Press any key to close.
pause >nul
