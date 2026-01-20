# Guía de Migración - Donchian Strategy

## 🔄 Migración de la Versión Monolítica a Modular

Esta guía explica cómo migrar desde la versión monolítica original de `donchian_strategy.py` (1647 líneas) a la nueva arquitectura modular.

## 📋 Cambios Principales

### Estructura Anterior (Monolítica)
```
core/
└── donchian_strategy.py  # 1647 líneas - Todo en un archivo
```

### Nueva Estructura (Modular)
```
core/
├── donchian_components/
│   ├── calculators/
│   │   └── technical_indicators.py
│   ├── validators/
│   │   └── risk_market_validators.py
│   ├── managers/
│   │   └── position_managers.py
│   └── donchian_strategy.py  # ~200 líneas - Solo coordinación
└── donchian_strategy.py      # Archivo principal refactorizado
```

## 🛠️ Actualización de Imports

### Imports Antiguos
```python
# Antes: Imports directos del archivo monolítico
from core.donchian_strategy import (
    MarketDataService,
    RiskCalculator,
    SessionManager,
    DonchianStrategy
)
```

### Imports Nuevos
```python
# Ahora: Imports específicos de cada componente
from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
from core.donchian_components.validators.risk_market_validators import RiskValidator, MarketValidator
from core.donchian_components.managers.position_managers import PositionManager, TradeTracker
from core.donchian_strategy import DonchianStrategy  # Coordinador principal
```

## 📝 Ejemplos de Migración

### 1. Inicialización de Componentes

**Antes:**
```python
# Versión monolítica
strategy = DonchianStrategy()
market_data = MarketDataService()
risk_calc = RiskCalculator(market_data)
```

**Ahora:**
```python
# Versión modular
from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
from core.donchian_components.validators.risk_market_validators import RiskValidator
from core.donchian_components.managers.position_managers import PositionManager

# Inicializar componentes individualmente
market_data = TechnicalIndicatorsCalculator()
risk_validator = RiskValidator(market_data)
position_manager = PositionManager(market_data, risk_validator)

# Usar estrategia principal
from core.donchian_strategy import DonchianStrategy
strategy = DonchianStrategy()
```

### 2. Uso de Métodos de Cálculo

**Antes:**
```python
# Acceso a través de la clase monolítica
upper, lower = strategy.market_data.get_donchian_channels("XAUUSD", 50)
atr = strategy.market_data.calculate_atr("XAUUSD", 14)
```

**Ahora:**
```python
# Acceso directo al componente especializado
from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator

tech_calc = TechnicalIndicatorsCalculator()
upper, lower = tech_calc.get_donchian_channels("XAUUSD", 50)
atr = tech_calc.calculate_atr("XAUUSD", 14)
```

### 3. Validación de Riesgo

**Antes:**
```python
# A través del objeto de estrategia
sl, tp = strategy.risk_calc.calculate_dynamic_stops(
    "XAUUSD", entry_price, "BUY", atr
)
```

**Ahora:**
```python
# Componente especializado
from core.donchian_components.validators.risk_market_validators import RiskValidator

risk_validator = RiskValidator(market_data)
sl, tp = risk_validator.calculate_dynamic_stops(
    "XAUUSD", entry_price, "BUY", atr
)
```

## 🔄 Script de Actualización Automática

Puedes usar este script para actualizar automáticamente los imports en tus archivos:

```bash
# Buscar y reemplazar imports antiguos
find . -name "*.py" -exec sed -i 's/from core.donchian_strategy import MarketDataService/from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator/g' {} \;

find . -name "*.py" -exec sed -i 's/from core.donchian_strategy import RiskCalculator/from core.donchian_components.validators.risk_market_validators import RiskValidator/g' {} \;

find . -name "*.py" -exec sed -i 's/from core.donchian_strategy import SessionManager/from core.donchian_components.validators.risk_market_validators import MarketValidator/g' {} \;
```

## ⚠️ Breaking Changes

### Clases Renombradas/Eliminadas
- `MarketDataService` → `TechnicalIndicatorsCalculator`
- `RiskCalculator` → `RiskValidator` (parcialmente)
- `SessionManager` → Partes en `MarketValidator` y `PositionManager`

### Métodos Movidos
- Métodos de cálculo técnico → `TechnicalIndicatorsCalculator`
- Métodos de validación de riesgo → `RiskValidator`
- Métodos de gestión de posiciones → `PositionManager`

### Variables Globales
Las variables globales `QUANT_OPTIMAL_LOTS`, `CURRENT_ENTRY_SCORE`, `TRADE_ENTRY_SCORES` se mantienen en el archivo principal `donchian_strategy.py` para compatibilidad.

## 🧪 Testing Post-Migración

Después de actualizar los imports, ejecuta estos tests para verificar la funcionalidad:

```bash
# Tests de seguridad
uv run python -m pytest tests_integration/test_security.py -v

# Tests de componentes individuales (una vez creados)
uv run python -m pytest tests/unit/test_technical_indicators.py
uv run python -m pytest tests/unit/test_risk_validators.py
uv run python -m pytest tests/unit/test_position_managers.py

# Test de estrategia principal
uv run python core/donchian_strategy.py
```

## 📊 Beneficios de la Migración

### ✅ Ventajas Alcanzadas
- **Reducción de 88%** en líneas de código del archivo principal
- **Mejor mantenibilidad** con componentes especializados
- **Mayor testabilidad** con módulos independientes
- **Menor acoplamiento** entre funcionalidades
- **Escalabilidad mejorada** para futuras extensiones

### 📈 Métricas de Mejora
| Métrica | Antes | Después | Mejora |
|---------|-------|---------|---------|
| Líneas archivo principal | 1647 | ~200 | 88% reducción |
| Archivos >1000 líneas | 1 | 0 | 100% eliminados |
| Componentes | 1 (monolítico) | 4+ (modular) | +300% modularidad |

## 🆘 Troubleshooting

### Problemas Comunes

1. **ImportError: No module named 'core.donchian_strategy'**
   ```bash
   # Verificar que estás usando los imports correctos
   # Antes: from core.donchian_strategy import MarketDataService
   # Ahora: from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
   ```

2. **AttributeError: 'X' object has no attribute 'Y'**
   ```python
   # Verificar que estás llamando al método en el componente correcto
   # Los métodos se han movido a diferentes clases especializadas
   ```

3. **NameError: name 'QUANT_OPTIMAL_LOTS' is not defined**
   ```python
   # Las variables globales se mantienen en core/donchian_strategy.py
   # Importa desde el archivo principal si las necesitas
   from core.donchian_strategy import QUANT_OPTIMAL_LOTS
   ```

## 📞 Soporte

Si encuentras problemas durante la migración:
1. Verifica que todos los imports estén actualizados
2. Ejecuta los tests para identificar puntos problemáticos
3. Consulta la documentación específica de cada componente
4. Revisa los ejemplos en esta guía

---

*Última actualización: 2026-01-20*
*Autor: Daniel Bot*