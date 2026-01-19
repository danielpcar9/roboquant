@echo off
echo.
echo 🧪 Running Backtest with uv...
echo.

:: Verificar que el entorno virtual exista
if not exist ".venv\Scripts\activate.bat" (
    echo ⚠️  Entorno virtual no encontrado
    echo Ejecutando setup_uv_env.bat primero...
    call setup_uv_env.bat
    if %errorlevel% neq 0 (
        echo ❌ Error configurando el entorno
        pause
        exit /b 1
    )
)

:: Activar entorno virtual
call .venv\Scripts\activate.bat

:: Ejecutar backtest
python scripts\backtest_apex_vectorbt.py

echo.
pause