@echo off
cd /d "C:\Users\edgar\roboquant"
echo.
echo 🚀 Exporting MT5 Historical Data...
echo (Make sure MT5 is running and logged in)
echo.
"C:\Users\edgar\roboquant\venv\Scripts\python.exe" export_mt5_data.py
echo.
pause