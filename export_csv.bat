@echo off
rem Export research records (data\mycover.db) to CSV files in data\export
cd /d "%~dp0"
chcp 65001 >nul
py tools\export_csv.py
if exist data\export start "" explorer data\export
echo.
pause
