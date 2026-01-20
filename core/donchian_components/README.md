# Donchian Strategy Components

## 🏗️ Arquitectura Modular

Esta carpeta contiene la implementación modular de la estrategia Donchian Channel, refactorizada siguiendo los principios SOLID para mejorar mantenibilidad, testabilidad y escalabilidad.

## 📁 Estructura de Componentes

```
donchian_components/
├── calculators/                    # Cálculos técnicos e indicadores
│   ├── __init__.py
│   └── technical_indicators.py    # Donchian channels, ATR, momentum, etc.
├── validators/                     # Validación de riesgo y mercado
│   ├── __init__.py
│   └── risk_market_validators.py  # RiskValidator, MarketValidator
├── managers/                       # Gestión de posiciones y ejecución
│   ├── __init__.py
│   └── position_managers.py       # PositionManager, TradeTracker
├── __init__.py
└── donchian_strategy.py           # Coordinador principal (estrategia refactorizada)
```

## 🎯 Principios SOLID Implementados

### 1. Single Responsibility Principle (SRP)
Cada componente tiene una única responsabilidad bien definida:
- **Calculators**: Solo cálculos matemáticos y técnicos
- **Validators**: Solo validación de condiciones y riesgos
- **Managers**: Solo gestión de posiciones y ejecución

### 2. Open/Closed Principle (OCP)
Los componentes están abiertos para extensión pero cerrados para modificación:
- Nuevos indicadores se añaden en `calculators/`
- Nuevas validaciones se añaden en `validators/`
- Nuevas estrategias de gestión en `managers/`

### 3. Liskov Substitution Principle (LSP)
Componentes intercambiables que mantienen el contrato esperado.

### 4. Interface Segregation Principle (ISP)
Interfaces específicas por responsabilidad en lugar de interfaces generales.

### 5. Dependency Inversion Principle (DIP)
Dependencias hacia abstracciones, no hacia implementaciones concretas.

## 🚀 Beneficios de la Arquitectura

### ✅ Reducción de Complejidad
- Archivo principal reducido de 1647 a ~200 líneas
- Código organizado por responsabilidades
- Menor acoplamiento entre componentes

### ✅ Mejor Testeabilidad
- Componentes independientes fácilmente testeables
- Mocks claros para dependencias externas (MT5)
- Cobertura de tests más precisa por módulo

### ✅ Mayor Mantenibilidad
- Cambios localizados en componentes específicos
- Menos conflictos en desarrollo colaborativo
- Documentación clara por módulo

### ✅ Escalabilidad
- Fácil adición de nuevas funcionalidades
- Reutilización de componentes en otras estrategias
- Extensión sin modificar código existente

## 📊 Métricas de Mejora

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|---------|
| Líneas en archivo principal | 1647 | ~200 | 88% reducción |
| Archivos >1000 líneas | 1 | 0 | 100% eliminados |
| Componentes independientes | 1 | 4+ | +300% modularidad |
| Acoplamiento | Alto | Bajo | Significativa mejora |

## 🛠️ Uso Básico

```python
from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
from core.donchian_components.validators.risk_market_validators import RiskValidator, MarketValidator
from core.donchian_components.managers.position_managers import PositionManager

# Inicializar componentes
market_data = TechnicalIndicatorsCalculator()
risk_validator = RiskValidator(market_data)
market_validator = MarketValidator(mt5_gateway, market_data)
position_manager = PositionManager(market_data, risk_validator)

# Usar la estrategia refactorizada
from core.donchian_strategy import DonchianStrategy
strategy = DonchianStrategy()
strategy.run_strategy("XAUUSD")
```

## 📚 Documentación por Componente

Para documentación detallada de cada componente, consulta:
- [`calculators/README.md`](calculators/README.md) - Indicadores técnicos
- [`validators/README.md`](validators/README.md) - Validadores de riesgo/mercado
- [`managers/README.md`](managers/README.md) - Gestión de posiciones

## 🔄 Migración

Para información sobre cómo migrar desde la versión monolítica, consulta:
[`MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md)

---

*Última actualización: 2026-01-20*
*Autor: Daniel Bot*