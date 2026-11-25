@echo off
rem ==========================================================================
rem  My Cover - exhibition launcher (double-click after the PC starts)
rem  1. Starts the server (app.py) in a minimized window
rem  2. Opens Chrome in kiosk mode: /desk on the desk monitor, /display on the large monitor
rem  To close a kiosk window: click it and press Alt+F4
rem ==========================================================================

rem ---- Window positions (top-left corner of each monitor, in pixels) -------
rem  Check in Windows Settings > System > Display. If the large monitor is to the
rem  right of the desk monitor at 1920x1080, it starts at X=1920.
set DESK_X=0
set DESK_Y=0
set DISPLAY_X=1920
set DISPLAY_Y=0
set PORT=5000
rem --------------------------------------------------------------------------

cd /d "%~dp0"

set CHROME="C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% set CHROME="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not exist %CHROME% (
  echo [ERROR] Chrome not found.
  pause
  exit /b 1
)

rem ---- Start the server (skip if it is already running) --------------------
curl -s -o nul http://127.0.0.1:%PORT%/ && goto ready
echo Starting server...
start "MyCover server" /min cmd /k py app.py

set /a TRIES=0
:wait
timeout /t 1 /nobreak >nul
curl -s -o nul http://127.0.0.1:%PORT%/ && goto ready
set /a TRIES+=1
if %TRIES% lss 60 goto wait
echo [ERROR] The server did not start. Open the "MyCover server" window and check the message.
pause
exit /b 1

:ready
echo Server is running.

rem ---- Open two kiosk windows (separate profiles so each keeps its own position)
set FLAGS=--kiosk --no-first-run --no-default-browser-check --autoplay-policy=no-user-gesture-required --disable-features=Translate --overscroll-history-navigation=0 --disable-pinch

start "" %CHROME% %FLAGS% --user-data-dir="%LOCALAPPDATA%\MyCover\chrome-desk" --window-position=%DESK_X%,%DESK_Y% http://127.0.0.1:%PORT%/desk
timeout /t 2 /nobreak >nul
start "" %CHROME% %FLAGS% --user-data-dir="%LOCALAPPDATA%\MyCover\chrome-display" --window-position=%DISPLAY_X%,%DISPLAY_Y% http://127.0.0.1:%PORT%/display

exit /b 0
