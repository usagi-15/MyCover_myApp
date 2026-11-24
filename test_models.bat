@echo off
rem Compare image models. Generated images are saved in data\test. API usage is charged.
cd /d "%~dp0"
chcp 65001 >nul
py -m pip install -q -r requirements.txt
py tools\test_generate.py --compare
if exist data\test start "" explorer data\test
echo.
pause
