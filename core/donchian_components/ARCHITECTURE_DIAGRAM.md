# Diagrama de Arquitectura Modular

## 🏗️ Estructura de Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    DONCHIAN STRATEGY                        │
│                    (Coordinador Principal)                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ CALCULATORS │  │ VALIDATORS  │  │  MANAGERS   │        │
│  │             │  │             │  │             │        │
│  │  Technical  │  │ Risk &      │  │ Position &  │        │
│  │ Indicators  │  │ Market      │  │ Trade       │        │
│  │             │  │ Validation  │  │ Management  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🔗 Relaciones entre Componentes

```
DonchianStrategy (Principal)
    │
    ├─── TechnicalIndicatorsCalculator
    │        ├── Obtiene datos de mercado
    │        ├── Calcula indicadores técnicos
    │        └── Provee análisis técnico
    │
    ├─── RiskValidator
    │        ├── Valida parámetros de riesgo
    │        ├── Calcula stops dinámicos
    │        └── Determina tamaño de posición
    │
    ├─── MarketValidator
    │        ├── Valida condiciones de mercado
    │        ├── Verifica horarios de trading
    │        └── Aplica filtros de sesión
    │
    ├─── PositionManager
    │        ├── Ejecuta órdenes de trading
    │        ├── Gestiona parámetros de entrada
    │        └── Coordina ejecución de trades
    │
    └─── TradeTracker
             ├── Registra trades activos
             ├── Monitorea posiciones
             └── Gestiona seguimiento post-trade
```

## 🎯 Aplicación de Principios SOLID

### 1. Single Responsibility Principle (SRP)
```
┌─────────────────────────┐  ┌─────────────────────────┐
│ TechnicalIndicatorsCalc │  │    SOLO CÁLCULOS        │
│ - Donchian Channels     │  │    TÉCNICOS             │
│ - ATR, Momentum         │  │                         │
│ - Precios de mercado    │  └─────────────────────────┘
└─────────────────────────┘

┌─────────────────────────┐  ┌─────────────────────────┐
│     RiskValidator       │  │    SOLO VALIDACIÓN      │
│ - Stops dinámicos       │  │    DE RIESGO            │
│ - Tamaño de posición    │  │                         │
│ - Gestión de capital    │  └─────────────────────────┘
└─────────────────────────┘

┌─────────────────────────┐  ┌─────────────────────────┐
│    PositionManager      │  │    SOLO GESTIÓN DE      │
│ - Ejecución de trades   │  │    POSICIONES           │
│ - Validación de mercado │  │                         │
│ - Coordinación de orden │  └─────────────────────────┘
└─────────────────────────┘
```

### 2. Open/Closed Principle (OCP)
```
SISTEMA ABIERTO PARA EXTENSIÓN:

┌─────────────────────────────────────────────┐
│              NUEVOS COMPONENTES             │
├─────────────────────────────────────────────┤
│                                             │
│ ┌─────────────────┐  ┌─────────────────┐   │
│ │ NuevosIndicadores├──┤ NuevasValidaciones│  │
│ │ ├── RSI         │  │ ├── Volatilidad  │   │
│ │ ├── MACD        │  │ ├── Drawdown     │   │
│ │ └── Bollinger   │  │ └── Sesiones     │   │
│ └─────────────────┘  └─────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘

SISTEMA CERRADO PARA MODIFICACIÓN:
- Componentes existentes no requieren cambios
- Nueva funcionalidad se añade en nuevos módulos
- Interfaces estables preservan compatibilidad
```

### 3. Liskov Substitution Principle (LSP)
```
COMPONENTES INTERCAMBIABLES:

┌─────────────────────────────────────────────┐
│              INTERFAZ COMÚN                 │
├─────────────────────────────────────────────┤
│ calculate_indicators(symbol, params)        │
│ validate_conditions(symbol, context)        │
│ execute_action(symbol, parameters)          │
└─────────────────────────────────────────────┘
        ▲              ▲              ▲
        │              │              │
┌───────┴───────┐┌─────┴──────┐┌─────┴──────┐
│TechnicalCalc  ││RiskValidator││PositionMgr │
│(implementa)   ││(implementa) ││(implementa)│
└───────────────┘└─────────────┘└────────────┘
```

### 4. Interface Segregation Principle (ISP)
```
INTERFACES ESPECÍFICAS:

┌─────────────────────────────────────────────┐
│           INTERFACES SEGREGADAS             │
├─────────────────────────────────────────────┤
│                                             │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────┐ │
│ │IndicatorAPI │ │ValidatorAPI │ │ManagerAPI│ │
│ │- get_price()│ │- is_valid() │ │- execute()│ │
│ │- calculate()│ │- check_risk()│ │- manage() │ │
│ └─────────────┘ └─────────────┘ └─────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### 5. Dependency Inversion Principle (DIP)
```
DEPENDENCIAS HACIA ABSTRACCIONES:

┌─────────────────────────────────────────────┐
│              ABSTRACCIONES                  │
├─────────────────────────────────────────────┤
│ IMarketDataProvider                         │
│ ITradingValidator                           │
│ IPositionExecutor                           │
└─────────────────────────────────────────────┘
        ▲              ▲              ▲
        │              │              │
┌───────┴───────┐┌─────┴──────┐┌─────┴──────┐
│Implementación ││Implementación│Implementación│
│  Concreta     ││  Concreta   ││  Concreta  │
└───────────────┘└─────────────┘└────────────┘
```

## 📊 Flujo de Datos

```
ENTRADA: Símbolo (XAUUSD) + Parámetros
    │
    ├─► TechnicalIndicatorsCalculator
    │      ├── Obtiene datos históricos
    │      ├── Calcula indicadores
    │      └── Retorna análisis técnico
    │
    ├─► RiskValidator + MarketValidator
    │      ├── Validan condiciones de mercado
    │      ├── Calculan parámetros de riesgo
    │      └── Determinan viabilidad del trade
    │
    └─► PositionManager
           ├── Coordina ejecución
           ├── Gestiona parámetros
           └── Ejecuta orden en MT5
           
SALIDA: Trade ejecutado + Registro para seguimiento
```

## 🛡️ Capas de Seguridad

```
┌─────────────────────────────────────────────┐
│              CAPA DE VALIDACIÓN             │
├─────────────────────────────────────────────┤
│ Input Validation                            │
│ ├── Símbolo válido                          │
│ ├── Parámetros en rangos                    │
│ └── Tipos de datos correctos                │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│              CAPA DE NEGOCIO                │
├─────────────────────────────────────────────┤
│ Business Logic                              │
│ ├── Análisis técnico                        │
│ ├── Validación de riesgo                    │
│ └── Gestión de posiciones                   │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│              CAPA DE DATOS                  │
├─────────────────────────────────────────────┤
│ Data Access                                 │
│ ├── Conexión MT5                            │
│ ├── Obtención de precios                    │
│ └── Ejecución de órdenes                    │
└─────────────────────────────────────────────┘
```

---

*Última actualización: 2026-01-20*
*Autor: Daniel Bot*