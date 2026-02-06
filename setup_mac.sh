#!/bin/bash
# =============================================================================
# RoboQuant - Setup para macOS
# =============================================================================
# Este script configura el proyecto para desarrollo en Mac
# =============================================================================

set -e

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}       🤖 RoboQuant - Setup para macOS${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Ejecuta este script desde el directorio roboquant${NC}"
    exit 1
fi

# Verificar uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}📦 Instalando uv...${NC}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source "$HOME/.local/bin/env"
fi

echo -e "${GREEN}✅ uv disponible: $(uv --version)${NC}"

# Sincronizar dependencias
echo ""
echo -e "${BLUE}📦 Sincronizando dependencias...${NC}"
uv sync

# Verificar instalación
echo ""
echo -e "${BLUE}🔍 Verificando instalación...${NC}"

source .venv/bin/activate

python -c "
import sys
try:
    import pandas
    import numpy  
    import vectorbt
    import xgboost
    from core.mt5_compat import mt5, MT5_AVAILABLE
    
    print('✅ pandas:', pandas.__version__)
    print('✅ numpy:', numpy.__version__)
    print('✅ vectorbt:', vectorbt.__version__)
    print('✅ xgboost:', xgboost.__version__)
    print()
    if MT5_AVAILABLE:
        print('✅ MetaTrader5 disponible - modo trading real')
    else:
        print('⚠️  MetaTrader5: modo desarrollo (sin trading real)')
        print('   Para trading real, ejecuta este proyecto en Windows')
except ImportError as e:
    print(f'❌ Error de importación: {e}')
    sys.exit(1)
"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Setup completado exitosamente!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Comandos disponibles:"
echo -e "  ${BLUE}./run_backtest_mac.sh${NC}     - Ejecutar backtesting"
echo -e "  ${BLUE}source .venv/bin/activate${NC} - Activar entorno"
echo ""
echo -e "${YELLOW}Nota: Para trading real, usa Windows o un VPS Windows${NC}"
