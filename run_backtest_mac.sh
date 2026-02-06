#!/bin/bash
# =============================================================================
# RoboQuant - Scripts de desarrollo para macOS
# =============================================================================
# Este script configura el entorno y ejecuta backtesting en Mac
# =============================================================================

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       🤖 RoboQuant - Backtesting en macOS${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "pyproject.toml" ]; then
    echo -e "${YELLOW}⚠️  Ejecuta este script desde el directorio roboquant${NC}"
    exit 1
fi

# Activar entorno virtual
if [ -d ".venv" ]; then
    echo -e "${GREEN}✅ Activando entorno virtual...${NC}"
    source .venv/bin/activate
else
    echo -e "${YELLOW}⚠️  No se encontró .venv - ejecuta 'uv sync' primero${NC}"
    exit 1
fi

echo -e "${GREEN}🚀 Ejecutando backtesting...${NC}"
echo ""

# Ejecutar backtesting
python -m scripts.backtest_apex_vectorbt "$@"

echo ""
echo -e "${GREEN}✅ Backtesting completado!${NC}"
