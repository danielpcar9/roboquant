@echo off
echo.
echo 🚀 Running Donchian Breakout Strategy with uv...
echo (Make sure MT5 is running and logged in)
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

:: Ejecutar la estrategia
python -m core.donchian_strategy

echo.
pause