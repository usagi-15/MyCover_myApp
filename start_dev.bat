@echo off
rem My Cover - development launcher (Phase 1)
rem Double-click this file. It installs libraries, starts the server, and opens /desk and /display in Chrome.
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python launcher "py" not found. Install Python 3 from python.org
  echo         and check "Add python.exe to PATH" during installation.
  pause
  exit /b 1
)

echo Installing libraries (Flask, Pillow, qrcode, openai)...
py -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install failed. See the message above.
  pause
  exit /b 1
)

echo Starting server... (close the "MyCover server" window to stop)
start "MyCover server" cmd /k py app.py

rem wait for the server to start
timeout /t 4 /nobreak >nul

set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% (
  echo Chrome not found. Open these URLs manually:
  echo   http://127.0.0.1:5000/desk
  echo   http://127.0.0.1:5000/display
  pause
  exit /b 0
)

start "" %CHROME% --user-data-dir="%TEMP%\mycover-chrome" --autoplay-policy=no-user-gesture-required --new-window http://127.0.0.1:5000/desk
start "" %CHROME% --user-data-dir="%TEMP%\mycover-chrome" --autoplay-policy=no-user-gesture-required --new-window http://127.0.0.1:5000/display
