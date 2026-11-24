@echo off
cd /d "%~dp0"
chcp 65001 >nul
py -m pip install -q -r requirements.txt
py tools\set_supabase_key.py
echo.
pause
