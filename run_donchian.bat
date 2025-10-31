@echo off
cd /d "C:\Users\edgar\roboquant"
echo.
echo 🚀 Running Donchian Breakout Strategy...
echo (Make sure MT5 is running and logged in)
echo.
"C:\Users\edgar\roboquant\venv\Scripts\python.exe" donchian_strategy.py
echo.
pause