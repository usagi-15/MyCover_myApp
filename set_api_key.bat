@echo off
rem Save the OpenAI API key to config\secrets.json (not uploaded to GitHub)
cd /d "%~dp0"
chcp 65001 >nul
py tools\set_api_key.py
echo.
pause
