# Plan de Consolidación de Archivos

## 📁 Archivos a ELIMINAR (Redundantes/Duplicados)

### README.md duplicados:
- `venv/Lib/site-packages/*/README.md` (20+ archivos)
- `.venv/Lib/site-packages/*/README.md` (20+ archivos) 
- `.pytest_cache/README.md`
- `core/donchian_components/calculators/README.md` (ya documentado en principal)
- `core/donchian_components/validators/README.md` (ya documentado en principal)
- `core/donchian_components/managers/README.md` (ya documentado en principal)

### Documentación redundante:
- `SOLID_REFACTOR_SUMMARY.md` (duplicado de otros resúmenes)
- `REFACTOR_DIFFERENCES.md` (información desactualizada)
- `QUANT_SYSTEM_SUMMARY.md` (ya cubierto en README principal)

### Licencias duplicadas:
- Todas las licencias en `venv/` y `.venv/` (son de paquetes externos)

## 📁 Archivos a CONSOLIDAR

### Scripts .bat redundantes:
- `run_backtest.bat` + `run_backtest_uv.bat` → `run_backtest.bat` (solo uv)
- `run_donchian.bat` + `run_donchian_uv.bat` → `run_strategy.bat`
- `setup_uv_env.bat` + `uv_commands.bat` → `setup_project.bat`

### Documentación técnica:
- `OVERFITTING_ANALYSIS.md` + `OVERFITTING_GUIDE.md` + `VALIDATION_RESULTS.md` → `VALIDATION.md`
- `FINAL_SUMMARY.md` + `SOLID_IMPLEMENTATION_SUMMARY.md` + `STRATEGY_IMPROVEMENTS.md` → `PROJECT_HISTORY.md`

## 📁 Archivos a MANTENER

### Esenciales:
- `README.md` (raíz del proyecto)
- `core/donchian_components/README.md` (documentación técnica principal)
- `UV_MIGRATION_GUIDE.md` (guía de migración importante)
- `MIGRATION_GUIDE.md` (guía de componentes)

### Scripts únicos:
- `run_advanced_validation.bat`
- `run_export_data.bat` 
- `run_webhook.bat`

## 📋 Acciones Específicas

1. **Eliminar 40+ archivos README.md** de dependencias externas
2. **Consolidar 8 scripts .bat** en 4 scripts principales
3. **Unificar 6 documentos .md** en 2 documentos consolidados
4. **Mantener solo documentación esencial** y actualizada

## 💡 Beneficios Esperados

- Reducción de 50 a ~15 archivos de documentación/scripts
- Proyecto más limpio y profesional
- Menos confusión para nuevos desarrolladores
- Mantenimiento más sencillo
- Tiempo de carga de IDE reducido