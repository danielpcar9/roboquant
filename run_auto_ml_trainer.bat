@echo off
:: Script para iniciar el entrenamiento automático continuo

echo 🤖 Iniciando Auto ML Trainer - Aprendizaje Continuo
echo ===================================================
echo Este proceso entrenará el modelo ML automáticamente
echo con nueva información de mercado de forma periódica.
echo.
echo Para detener: Presione Ctrl+C
echo.

cd /d "%~dp0"
uv run python auto_ml_trainer.py

echo.
echo Entrenamiento automático detenido.
pause