@echo off
echo.
echo 🛠️ Configurando entorno con uv...
echo.

:: Verificar que uv esté instalado
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Error: uv no está instalado
    echo Por favor ejecuta: irm https://astral.sh/uv/install.ps1 | iex
    pause
    exit /b 1
)

:: Crear entorno virtual con uv
echo 📦 Creando entorno virtual...
uv venv

:: Activar entorno virtual
echo 🔧 Activando entorno virtual...
call .venv\Scripts\activate.bat

:: Instalar dependencias
echo ⬇️ Instalando dependencias...
uv pip install -e .

echo.
echo ✅ Entorno configurado exitosamente!
echo Para activar el entorno en el futuro, ejecuta:
echo    call .venv\Scripts\activate.bat
echo.

pause