@echo off
cd /d "C:\Users\edgar\roboquant"
echo.
echo 🚀 Starting Webhook Receiver...
echo (Make sure MT5 is running and logged in)
echo.
"C:\Users\edgar\roboquant\venv\Scripts\python.exe" webhook_receiver.py
echo.
pause