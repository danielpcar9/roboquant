# Guía de Migración a uv

Esta guía explica cómo el proyecto ha sido migrado al ecosistema de `uv` y cómo utilizarlo.

## ¿Qué es uv?

`uv` es un gestor de paquetes y entornos virtuales extremadamente rápido para Python, desarrollado por Astral. Ofrece ventajas significativas sobre pip tradicional:

- ⚡ **Velocidad**: 10-100x más rápido que pip
- 🎯 **Resolución determinística**: Dependencias consistentes
- 📦 **Gestión integrada**: Entornos virtuales + paquetes en una herramienta
- 🛠️ **Herramientas de desarrollo**: Built-in linters, formatters, etc.

## Archivos nuevos creados

### pyproject.toml
Archivo de configuración moderno que reemplaza:
- `setup.py`
- `requirements.txt` 
- Parte de `.env` (configuración del proyecto)

Contiene:
- Metadatos del proyecto
- Dependencias de producción y desarrollo
- Configuración de herramientas (black, pytest, mypy)
- Entry points para scripts CLI

### Scripts .bat para uv
- `setup_uv_env.bat` - Configuración inicial del entorno
- `run_donchian_uv.bat` - Ejecución de estrategia con uv
- `run_backtest_uv.bat` - Backtesting con uv
- `uv_commands.bat` - Ayuda con comandos de uv

## Comandos básicos de uv

### Gestión de entorno
```cmd
# Crear entorno virtual
uv venv

# Activar entorno (Windows)
.venv\Scripts\activate.bat

# Eliminar entorno
uv venv --remove
```

### Gestión de paquetes
```cmd
# Instalar dependencias del proyecto
uv pip install -e .

# Instalar paquete específico
uv pip install pandas

# Actualizar paquete
uv pip install --upgrade pandas

# Listar paquetes instalados
uv pip list

# Exportar requirements.txt
uv pip freeze > requirements.txt
```

### Desarrollo
```cmd
# Ejecutar comando en entorno aislado
uv run python script.py

# Sincronizar dependencias
uv sync

# Generar lock file
uv lock
```

## Ventajas de la migración

### 1. Velocidad mejorada
- Instalación de dependencias ~50x más rápida
- Resolución de conflictos optimizada
- Cache inteligente de paquetes

### 2. Reproducibilidad
- `pyproject.toml` define dependencias exactas
- Lock files para versiones fijas
- Entornos consistentes entre desarrolladores

### 3. Mantenimiento simplificado
- Un solo archivo de configuración
- Herramientas de desarrollo integradas
- Menos archivos de configuración dispersos

## Problemas conocidos y soluciones

### ta-lib compilation error
**Problema**: Error al compilar `ta-lib==0.4.28`
**Solución**: Usar versión más reciente con wheels precompiladas:
```cmd
uv pip install TA-Lib  # Versión 0.6.8+
```

### Entorno virtual corrupto
**Problema**: `pyvenv.cfg` faltante o corrupto
**Solución**: 
```cmd
# Eliminar entorno existente
Remove-Item -Recurse -Force .venv

# Crear nuevo entorno
uv venv
uv pip install -e .
```

## Migración desde pip/venv tradicional

Si tienes un entorno existente con pip/venv:

1. **Backup** de tu entorno actual
2. **Eliminar** el entorno viejo: `Remove-Item -Recurse -Force .venv`
3. **Instalar uv** si no lo tienes
4. **Crear nuevo entorno**: `uv venv`
5. **Instalar dependencias**: `uv pip install -e .`

## Recomendaciones

1. **Usa siempre los scripts `.bat`** proporcionados para operaciones comunes
2. **Mantén uv actualizado**: `uv pip install --upgrade uv`
3. **Documenta cambios** en `pyproject.toml` cuando agregues dependencias
4. **Prueba con `uv run`** antes de instalar globalmente

## Soporte

Para problemas específicos de uv:
- Documentación oficial: https://docs.astral.sh/uv/
- GitHub: https://github.com/astral-sh/uv
- Discord: https://discord.gg/astral-sh

Para problemas del proyecto:
- Issues en GitHub del proyecto
- Contactar al equipo de desarrollo