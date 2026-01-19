@echo off
echo.
echo 🛠️ Comandos útiles de uv
echo ======================
echo.

:: Verificar que uv esté disponible
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv no está instalado
    echo Instala uv ejecutando en PowerShell:
    echo irm https://astral.sh/uv/install.ps1 ^| iex
    goto :eof
)

echo Comandos disponibles:
echo.
echo 📦 Gestión de paquetes:
echo   uv pip install [paquete]     - Instalar paquete
echo   uv pip uninstall [paquete]   - Desinstalar paquete
echo   uv pip list                  - Listar paquetes instalados
echo   uv pip freeze                - Exportar requirements.txt
echo.
echo 🐍 Entorno virtual:
echo   uv venv                      - Crear entorno virtual
echo   uv venv --remove             - Eliminar entorno virtual
echo   call .venv\Scripts\activate  - Activar entorno (en cmd)
echo.
echo 🔧 Desarrollo:
echo   uv run [comando]             - Ejecutar comando en entorno aislado
echo   uv sync                      - Sincronizar dependencias
echo   uv lock                      - Generar uv.lock
echo.
echo 🔄 Actualización:
echo   uv pip install --upgrade [paquete]  - Actualizar paquete
echo   uv pip install --upgrade uv         - Actualizar uv mismo
echo.

pause