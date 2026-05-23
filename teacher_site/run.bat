@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
title Teacher Saydullayev Site

echo ==========================================
echo   Teacher Saydullayev Flask Site
echo ==========================================
echo.

set "PYTHON_CMD="
where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=python"
    )
)

if "%PYTHON_CMD%"=="" (
    echo Python topilmadi. Python 3.11+ o'rnating:
    echo https://www.python.org/downloads/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment yaratilmoqda...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Virtual environment yaratilmadi.
        pause
        exit /b 1
    )
)

echo Kutubxonalar tekshirilmoqda...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Kutubxonalar o'rnatilmadi.
    pause
    exit /b 1
)

if "%~1"=="--check" (
    echo Flask import tekshirilmoqda...
    ".venv\Scripts\python.exe" -c "from app import app; print('OK: Flask app tayyor')"
    if errorlevel 1 (
        echo App importida xato bor.
        pause
        exit /b 1
    )
    echo run.bat tayyor.
    pause
    exit /b 0
)

for /f "delims=" %%P in ('".venv\Scripts\python.exe" -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1]); s.close()"') do set "PORT=%%P"

if "%PORT%"=="" (
    set "PORT=5000"
)

echo Eski Flask app.py processlari tozalanmoqda...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -like '*app.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>nul

echo.
echo Sayt ishga tushmoqda...
echo Browser: http://127.0.0.1:%PORT%
echo To'xtatish uchun shu oynada Ctrl+C bosing.
echo.

start "" "http://127.0.0.1:%PORT%"
set "PORT=%PORT%"
".venv\Scripts\python.exe" app.py

echo.
echo Server to'xtadi.
pause
