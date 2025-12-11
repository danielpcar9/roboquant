# 🔍 Guía: Cómo Detectar Overfitting en tu Bot

## ¿Qué es Overfitting?

**Overfitting** = Tu bot memorizó el pasado pero no puede adaptarse al futuro.

### Señales de Alerta 🚩

| Síntoma | Descripción | Riesgo |
|---------|-------------|--------|
| Backtest perfecto (>90% win rate) | Demasiado bueno para ser verdad | 🔴 ALTO |
| Live performance << Backtest | Gran diferencia entre histórico y real | 🔴 ALTO |
| Muchos parámetros (>7-8) | Demasiadas variables optimizadas | 🟡 MEDIO |
| Parámetros muy específicos | ej: período=37 (¿por qué no 40?) | 🟡 MEDIO |
| Funciona solo en un período | No generaliza a otros años | 🔴 ALTO |

## 🧪 Cómo Usar esta Herramienta

### Paso 1: Ejecutar Tests
```bash
run_overfitting_check.bat
```

### Paso 2: Interpretar Resultados

#### Test 1: Walk-Forward Analysis
**¿Qué mide?** Compara performance In-Sample (optimización) vs Out-of-Sample (validación)

**Resultados:**
```
Average Degradation: 15%  ✅ Excelente
Average Degradation: 35%  ⚠️  Moderado
Average Degradation: 60%  ❌ Overfitting
```

**Qué hacer:**
- ✅ < 20%: Bot robusto, puedes usar en live
- ⚠️ 20-40%: Aceptable, monitorear en demo
- ❌ > 40%: Rediseñar estrategia

#### Test 2: Parameter Robustness
**¿Qué mide?** Si pequeños cambios en parámetros destruyen la performance

**Resultados:**
```
Return Variability (CV): 18%  ✅ Robusto
Return Variability (CV): 45%  ⚠️  Sensible
Return Variability (CV): 75%  ❌ Frágil
```

**Qué hacer:**
- ✅ < 30%: Parámetros bien calibrados
- ⚠️ 30-60%: Simplificar o usar valores más anchos
- ❌ > 60%: Parámetros overfit, recalibrar

#### Test 3: Period Stability
**¿Qué mide?** Si funciona en diferentes condiciones de mercado

**Resultados:**
```
Profitable Years: 4/5 (80%)  ✅ Consistente
Profitable Years: 3/5 (60%)  ⚠️  Moderado
Profitable Years: 2/5 (40%)  ❌ Inconsistente
```

**Qué hacer:**
- ✅ > 80%: Estrategia sólida
- ⚠️ 60-80%: Agregar filtros (régimen, sesión)
- ❌ < 60%: Revisar lógica de la estrategia

## 🛠️ Cómo Corregir Overfitting

### 1. Simplifica
```python
❌ ANTES: 10 condiciones, 8 parámetros optimizados
✅ DESPUÉS: 3 condiciones principales, 3 parámetros clave
```

### 2. Usa Parámetros Redondeados
```python
❌ ANTES: donchian_period = 37  (muy específico)
✅ DESPUÉS: donchian_period = 40  (valor estándar)
```

### 3. Agrega Filtros de Contexto
En vez de optimizar más, agrega reglas que hagan sentido:
```python
✅ Solo trade en sesiones de mayor liquidez
✅ Evita news de alto impacto
✅ Considera régimen de mercado (trending vs ranging)
```

### 4. Valida en Períodos Diferentes
```python
✅ Backtest 2020-2022 (optimización)
✅ Validar 2023-2024 (sin tocar parámetros)
✅ Demo 2025 (verificación final)
```

## 📊 Benchmarks Realistas

### Estrategia de Breakout (Donchian) - XAUUSD

| Métrica | Realista | Optimista | Overfitted |
|---------|----------|-----------|------------|
| Win Rate | 35-45% | 45-55% | >60% 🚩 |
| Profit Factor | 1.3-1.8 | 1.8-2.5 | >3.0 🚩 |
| Sharpe Ratio | 0.5-1.2 | 1.2-2.0 | >2.5 🚩 |
| Max Drawdown | 15-25% | 10-15% | <8% 🚩 |
| Return/Year | 20-40% | 40-80% | >100% 🚩 |

### Regla de Oro
**Si parece demasiado bueno para ser verdad... probablemente lo es.**

## 🎯 Checklist Anti-Overfitting

Antes de pasar a live/demo:

- [ ] Walk-forward degradation < 25%
- [ ] Parameter robustness CV < 40%
- [ ] Al menos 3/5 años rentables
- [ ] Menos de 6 parámetros optimizados
- [ ] Lógica hace sentido (no es "magia")
- [ ] Funciona con parámetros ±10% diferentes
- [ ] Win rate realista (30-50% para breakout)
- [ ] Probado en demo al menos 1 mes

## 📁 Archivos Generados

Después de correr `run_overfitting_check.bat`:

1. **walk_forward_results.csv** - Performance IS vs OOS por período
2. **robustness_test_results.csv** - Sensibilidad a parámetros
3. **period_stability_results.csv** - Consistencia año por año

## 💡 Ejemplo Real

```
CASO: Bot con 85% win rate en backtest, 40% en live

DIAGNÓSTICO:
✅ Run overfitting tests
📊 Walk-forward degradation: 68% ❌
📊 Parameter CV: 82% ❌
📊 Profitable years: 2/5 ❌

SOLUCIÓN:
1. Reducir parámetros de 9 a 4
2. Usar valores estándar (20, 40, 50 en vez de 23, 37, 54)
3. Agregar filtro de sesión (solo London + NY)
4. Validar de nuevo

RESULTADO:
📊 Walk-forward degradation: 22% ✅
📊 Parameter CV: 28% ✅
📊 Live performance: 42% win rate (consistente con backtest 47%)
```

## 🚀 Próximos Pasos

1. **Ejecuta los tests**: `run_overfitting_check.bat`
2. **Revisa los CSVs** generados
3. **Ajusta tu estrategia** según los resultados
4. **Re-testea** hasta que pase los 3 tests
5. **Demo trading** por 1 mes mínimo
6. **Live con riesgo mínimo** (0.1-0.5% por trade)

---

**Recuerda:** Un bot promedio pero robusto es 100x mejor que un bot "perfecto" pero overfitted.
