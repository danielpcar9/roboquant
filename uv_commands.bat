@echo off
echo.
echo 🛠️ Comandos útiles de uv
echo ======================
echo.
echo ✅ pyproject.toml actualizado: Se usa [dependency-groups] en lugar de [tool.uv]
echo.
echo 📜 SCRIPTS - Ejecutar scripts Python independientes
echo ================================================
echo   uv run [script.py]       - Ejecutar un script
echo   uv add --script [dep]    - Añadir dependencia a un script
echo   uv remove --script [dep] - Eliminar dependencia de un script
echo.

:: Verificar que uv esté disponible
uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ uv no está instalado
    echo Instala uv ejecutando en PowerShell:
    echo irm https://astral.sh/uv/install.ps1 ^| iex
    goto :eof
)

echo 📁 PROJECTS - Comandos para proyectos Python con pyproject.toml
echo ================================================================
echo   uv init          - Crear un nuevo proyecto Python
echo   uv add           - Añadir una dependencia al proyecto
echo   uv remove        - Eliminar una dependencia del proyecto
echo   uv sync          - Sincronizar dependencias con el entorno
echo   uv lock          - Crear lockfile de dependencias
echo   uv run           - Ejecutar comando en entorno del proyecto
echo   uv tree          - Ver árbol de dependencias del proyecto
echo   uv build         - Construir archivos de distribución
echo   uv publish       - Publicar proyecto en índice de paquetes
echo.
echo 🔧 TOOLS - Herramientas publicadas en índices Python
echo ====================================================
echo   uvx / uv tool run      - Ejecutar herramienta en entorno temporal
echo   uv tool install        - Instalar herramienta globalmente
echo   uv tool uninstall      - Desinstalar herramienta
echo   uv tool list           - Listar herramientas instaladas
echo   uv tool update-shell   - Actualizar shell con ejecutables
echo.
echo ⚙️  UTILITY - Gestión e inspección del estado de uv
echo ===================================================
echo   uv cache clean         - Eliminar entradas de caché
echo   uv cache prune         - Eliminar entradas de caché obsoletas
echo   uv cache dir           - Mostrar directorio de caché de uv
echo   uv tool dir            - Mostrar directorio de herramientas de uv
echo   uv python dir          - Mostrar directorio de versiones Python instaladas
echo   uv self update         - Actualizar uv a la última versión
echo.
echo 📦 Gestión de paquetes (compatibilidad pip):
echo ==============================================
echo   uv pip install [paquete]     - Instalar paquete
echo   uv pip uninstall [paquete]   - Desinstalar paquete
echo   uv pip list                  - Listar paquetes instalados
echo   uv pip freeze                - Exportar requirements.txt
echo.
echo 🐍 Entorno virtual:
echo ===================
echo   uv venv                      - Crear entorno virtual
echo   uv venv --remove             - Eliminar entorno virtual
echo   call .venv\Scripts\activate  - Activar entorno (en cmd)
echo.
echo 🔄 Actualización:
echo ===============
echo   uv pip install --upgrade [paquete]  - Actualizar paquete
echo   uv pip install --upgrade uv         - Actualizar uv mismo
echo.
echo 🔄 COMPATIBILIDAD CON PIP:
echo =========================
echo uv es un reemplazo directo para pip y pip-tools
echo • Usa "uv pip install" en lugar de "pip install"
echo • Funciona con requirements.txt existentes
echo • Lee variables de entorno UV_* (no PIP_*)
echo • Configuración en uv.toml o [tool.uv.pip] en pyproject.toml
echo.
echo ⚠️  Diferencias importantes:
echo • No lee pip.conf ni variables PIP_*
echo • Usa UV_INDEX_URL en lugar de PIP_INDEX_URL
echo • No es copia exacta de pip, pero compatible en la mayoría de casos
echo.
echo 💡 Consejos:
echo ===========
echo • Usa "uv run script.py" para ejecutar scripts en entorno aislado
echo • Usa "uv sync" después de cambiar pyproject.toml
echo • Usa "uv lock" para crear versiones fijas de dependencias
echo • Usa "uv cache clean" si tienes problemas de instalación
echo.
pause