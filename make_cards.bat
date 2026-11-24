@echo off
cd /d "%~dp0"
chcp 65001 >nul
py -m pip install -q -r requirements.txt
py tools\make_cards.py
if exist data\cards start "" explorer data\cards
echo.
pause
