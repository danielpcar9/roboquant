@echo off
:: Script para entrenar el modelo ML
:: Uso: run_ml_training.bat [dias] [simbolo]

set DAYS=60
set SYMBOL=XAUUSD

if not "%1"=="" set DAYS=%1
if not "%2"=="" set SYMBOL=%2

echo 🤖 Entrenando modelo ML para %SYMBOL%
echo 📊 Usando %DAYS% días de datos históricos
echo.

cd /d "%~dp0"
uv run python train_ml_validator.py --days %DAYS% --symbol %SYMBOL%

echo.
echo Presione cualquier tecla para continuar...
pause >nul