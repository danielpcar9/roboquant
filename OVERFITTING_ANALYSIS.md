# Análisis de Overfitting - Estrategia Donchian

## Fecha: 2025-12-02

## Resumen Ejecutivo

Tu estrategia Donchian **NO tiene overfitting severo**, pero presenta **volatilidad alta** y **períodos de drawdown significativos**. Es viable pero requiere mejoras para trading en vivo.

---

## Resultados de los Tests

### 1. Walk-Forward Analysis ✅
- **Degradación Promedio: 16.8%**
- **Evaluación: BUENO - Bajo riesgo de overfitting**
- La estrategia generaliza razonablemente bien a datos no vistos

| Window | Period | IS Return | OOS Return | Degradation |
|--------|--------|-----------|------------|-------------|
| 1 | 2020-11 - 2021-11 | +158.2% | +16.6% | 89.5% |
| 2 | 2021-11 - 2022-11 | -68.2% | -55.3% | -19.0% |
| 3 | 2022-11 - 2023-11 | +97.3% | +180.1% | -85.1% |
| 4 | 2023-11 - 2024-10 | +41.9% | -22.9% | 154.7% |
| 5 | 2024-10 - 2025-10 | +166.4% | +259.6% | -56.0% |

**Interpretación:**
- Degradación promedio < 20% es excelente
- Algunas ventanas muestran mejor performance OOS (overfitting inverso - suerte)
- Otras muestran degradación alta pero no sistemática

### 2. Parameter Robustness ⚠️
- **Variabilidad (CV): 52.2%**
- **Evaluación: MODERADO - Sensibilidad a parámetros**

| Donchian Period | Return | Trades | Win Rate | Profit Factor |
|-----------------|--------|--------|----------|---------------|
| 16 | +1557% | 782 | 39.9% | 1.24 |
| 18 | +1555% | 704 | 38.6% | 1.25 |
| 20 | +772% | 640 | 38.3% | 1.12 |
| 22 | +722% | 564 | 39.7% | 1.12 |
| 24 | +410% | 516 | 38.0% | 1.07 |

**Interpretación:**
- Períodos cortos (16-18) generan returns extremadamente altos
- Período 20 (actual) está en rango medio-bajo
- **RIESGO:** La estrategia es sensible al parámetro elegido
- **NOTA:** Returns tan altos (+1500%) son señal de problemas en el backtest (no incluye costos realistas)

### 3. Yearly Consistency ⚠️
- **Años Rentables: 3/5 (60%)**
- **Evaluación: MODERADO - Algunos años muy malos**

| Year | Return | Trades | Win Rate | Profit Factor |
|------|--------|--------|----------|---------------|
| 2021 | -56.6% | 138 | 33.3% | 0.95 |
| 2022 | -157.3% | 140 | 34.3% | 0.87 |
| 2023 | +386.8% | 111 | 44.1% | 1.54 |
| 2024 | +247.8% | 119 | 37.0% | 1.20 |
| 2025 | +34.3% | 114 | 40.4% | 1.02 |

**Interpretación:**
- 2021-2022: Mercado bajista en oro → estrategia pierde mucho
- 2023-2024: Mercado alcista en oro → estrategia gana mucho
- **RIESGO:** Estrategia altamente dependiente de régimen de mercado

---

## Problemas Identificados

### 1. 🔴 Alta Dependencia del Régimen de Mercado
**Síntoma:** -157% en 2022, +387% en 2023  
**Causa:** Estrategia de breakout funciona solo en mercados trending  
**Impacto:** Drawdowns severos en mercados laterales

**Solución:**
- Agregar filtro de régimen de mercado (ADX > 25 para trend strength)
- Reducir tamaño de posición en mercados ranging
- Considerar pausar trading cuando ADX < 20

### 2. 🟡 Sensibilidad a Parámetros
**Síntoma:** Period=16 da +1557%, Period=20 da +772%  
**Causa:** Backtest simplificado sin costos realistas  
**Impacto:** Riesgo de seleccionar parámetros overfit

**Solución:**
- Mantener Period=20 (valor estándar, no optimizado)
- NO perseguir el "mejor" período en backtest
- Validar en demo antes de cambiar parámetros

### 3. 🟡 Win Rate Bajo (~38%)
**Síntoma:** Solo 38-40% de trades ganan  
**Causa:** Muchos falsos breakouts  
**Impacto:** Psicológicamente difícil, muchas pérdidas consecutivas

**Solución:**
- Agregar confirmación de breakout (volumen, ATR spike)
- Filtrar por sesión (solo London/NY overlap)
- Evitar news de alto impacto

---

## Recomendaciones Prácticas

### ✅ Mejoras Inmediatas (Fáciles)

#### 1. Agregar Filtro de ADX
```python
# En donchian_strategy.py
adx = calculate_adx(df, period=14)
if adx < 20:
    logging.info("Market is ranging (ADX < 20), skipping trade")
    return  # No trade in ranging markets
```

**Beneficio:** Evita operar en mercados laterales que destruyen la estrategia

#### 2. Reducir Riesgo en Drawdown
Ya lo tienes implementado en `ftmo_manager.py`:
- DD < 3%: 100% risk ✅
- DD 3-5%: 70% risk ✅
- DD 5-7%: 50% risk ✅
- DD > 7%: 25% risk ✅

**Beneficio:** Protege capital cuando estrategia no funciona

#### 3. Filtrar por Sesión
Ya implementado en `session_filter.py`:
- Solo operar en sesiones de alta liquidez ✅
- Preferir OVERLAP y EUROPEAN ✅

**Beneficio:** Reduce falsos breakouts

### ⚠️ Mejoras Avanzadas (Requieren Trabajo)

#### 4. Adaptive Donchian Period
```python
# Ajustar período según volatilidad
if atr > atr_ma:
    donchian_period = 16  # Mercado volátil = período corto
else:
    donchian_period = 24  # Mercado calmo = período largo
```

**Beneficio:** Adapta estrategia a condiciones cambiantes

#### 5. Multi-Timeframe Confirmation
```python
# Confirmar breakout en H4 antes de entrar en H1
h4_trend = get_h4_trend()
if h1_breakout and h4_trend == "same_direction":
    enter_trade()
```

**Beneficio:** Reduce falsos breakouts, mejora win rate

---

## Plan de Acción

### Fase 1: Validación (1-2 semanas)
- [ ] Implementar filtro ADX básico
- [ ] Reducir riesgo a 0.5% por trade
- [ ] Correr en demo 2 semanas
- [ ] Monitorear drawdown diario

### Fase 2: Optimización (2-4 semanas)
- [ ] Si DD > 10% en demo, pausar y revisar
- [ ] Si win rate < 35%, agregar filtro de confirmación
- [ ] Analizar trades perdedores: ¿patrón común?
- [ ] Ajustar filtros según análisis

### Fase 3: Live (después de 1 mes exitoso en demo)
- [ ] Empezar con riesgo mínimo (0.25% por trade)
- [ ] Escalar gradualmente si performance es buena
- [ ] NUNCA superar 1% riesgo por trade

---

## Métricas para Monitorear

### En Demo/Live:
| Métrica | Target | Alerta |
|---------|--------|--------|
| Win Rate | > 40% | < 35% |
| Profit Factor | > 1.3 | < 1.1 |
| Max Drawdown | < 10% | > 15% |
| Consecutive Losses | < 6 | > 8 |
| Monthly Return | > 5% | < -5% |

### Señales de Alerta
🔴 **STOP TRADING** si:
- Drawdown > 15%
- 10+ pérdidas consecutivas
- Profit Factor < 1.0 después de 50 trades
- Win rate < 30% después de 50 trades

🟡 **REVISAR ESTRATEGIA** si:
- Drawdown 10-15%
- 6-9 pérdidas consecutivas
- Profit Factor 1.0-1.1 después de 50 trades
- Win rate 30-35% después de 50 trades

✅ **CONTINUAR** si:
- Drawdown < 10%
- Profit Factor > 1.3
- Win rate > 40%
- Performance similar a backtest

---

## Conclusión Final

### ✅ Lo Bueno
1. No hay overfitting severo (degradación 16.8%)
2. Ya tienes buenos filtros de riesgo implementados
3. Estrategia funciona en mercados trending

### ⚠️ Lo Preocupante
1. Años 2021-2022 muestran pérdidas severas (-157%)
2. Alta sensibilidad a parámetros (CV 52%)
3. Win rate bajo (38%) requiere disciplina

### 🎯 Recomendación
**Tu estrategia es VIABLE pero NO LISTA para live trading sin filtro de régimen.**

**Siguiente paso inmediato:**
1. Agregar filtro ADX (< 1 hora de trabajo)
2. Correr backtest de nuevo con filtro
3. Si mejora, pasar a demo por 1 mes
4. Si demo exitoso, considerar live con riesgo mínimo

**Expectativas realistas para live:**
- Win rate: 35-45%
- Profit factor: 1.2-1.5
- Drawdown máximo: 15-20%
- Return anual: 30-60% (NO los +772% del backtest)
- Años malos: esperables (1 de cada 3 años puede ser negativo)

---

## Archivos Generados
- `walk_forward_simple.csv` - Análisis IS/OOS por ventana
- `robustness_simple.csv` - Sensibilidad a parámetros
- `yearly_consistency.csv` - Performance año por año

**Última actualización:** 2025-12-02
