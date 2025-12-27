#!/usr/bin/env python3
"""
Ejemplo de uso del sistema cuantitativo de trading
Este script demuestra cómo integrar y usar el motor cuantitativo
en un entorno de trading real
"""

import numpy as np
import logging
from core.quant_engine import QuantitativeEngine
from core.donchian_strategy import DonchianStrategy
from brokers.mt5_connection_manager import MT5ConnectionManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def example_basic_quant_analysis():
    """Ejemplo básico de análisis cuantitativo"""
    print("📊 Ejemplo Básico de Análisis Cuantitativo")
    print("-" * 50)
    
    # Inicializar el motor cuantitativo
    quant_engine = QuantitativeEngine()
    
    # Datos de ejemplo (simulando precios históricos)
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.normal(0, 0.1, 200))  # 200 puntos de precio
    
    # Indicadores técnicos simulados
    adx_value = 28.5  # Valor ADX
    di_plus = 22.1    # Valor +DI
    di_minus = 18.3   # Valor -DI
    
    logger.info(f"📈 Datos de entrada - Precio actual: {prices[-1]:.5f}")
    logger.info(f"📈 Indicadores - ADX: {adx_value}, +DI: {di_plus}, -DI: {di_minus}")
    
    # Calcular puntaje de entrada cuantitativo
    result = quant_engine.calculate_entry_score(
        prices=prices,
        adx_value=adx_value,
        di_plus=di_plus,
        di_minus=di_minus
    )
    
    logger.info(f"🎯 Puntaje de Entrada Cuantitativo: {result['entry_score']:.3f}")
    logger.info(f"💡 Recomendación: {result['recommendation']}")
    logger.info(f"🔍 Componentes: {result['components']}")
    logger.info(f"⚙️  Filtros: {result['filters']}")
    
    # Calcular tamaño óptimo de posición
    optimal_size = quant_engine.calculate_optimal_position_size(
        entry_score=result['entry_score'],
        account_balance=10000  # $10,000 de balance
    )
    
    logger.info(f"💰 Tamaño óptimo de posición: {optimal_size:.3f} lotes")
    
    print("-" * 50)

def example_strategy_integration():
    """Ejemplo de integración con la estrategia Donchian"""
    print("⚙️  Ejemplo de Integración con Estrategia Donchian")
    print("-" * 50)
    
    # Inicializar la estrategia (que incluye el motor cuantitativo)
    strategy = DonchianStrategy()
    
    # Simular datos que normalmente vendrían de MT5
    np.random.seed(123)
    mock_prices = 1.2000 + np.cumsum(np.random.normal(0, 0.001, 200))
    
    # Simular indicadores técnicos
    adx_value = 32.0
    di_plus = 25.0
    di_minus = 15.0
    
    logger.info("🔄 Simulando análisis cuantitativo en la estrategia...")
    
    # Simular cómo se usaría el análisis cuantitativo en la estrategia
    quant_engine = QuantitativeEngine()
    
    entry_result = quant_engine.calculate_entry_score(
        prices=mock_prices,
        adx_value=adx_value,
        di_plus=di_plus,
        di_minus=di_minus
    )
    
    logger.info(f"🎯 Puntaje de entrada: {entry_result['entry_score']:.3f}")
    logger.info(f"💡 Recomendación: {entry_result['recommendation']}")
    
    # Simular el cálculo de tamaño de posición
    position_size = quant_engine.calculate_optimal_position_size(
        entry_score=entry_result['entry_score'],
        account_balance=25000  # $25,000 de balance
    )
    
    logger.info(f"📊 Tamaño de posición calculado: {position_size:.3f} lotes")
    
    print("-" * 50)

def example_parameter_optimization():
    """Ejemplo de optimización de parámetros"""
    print("⚙️  Ejemplo de Optimización de Parámetros")
    print("-" * 50)
    
    # Inicializar el motor cuantitativo
    quant_engine = QuantitativeEngine()
    
    # Datos históricos para optimización
    np.random.seed(456)
    historical_prices = 1.1500 + np.cumsum(np.random.normal(0, 0.0008, 300))
    
    logger.info("🔄 Optimizando período Donchian...")
    
    # Optimizar el período Donchian
    optimal_period = quant_engine.optimizer.optimize_donchian_period(
        prices=historical_prices,
        periods_range=(10, 30)
    )
    
    logger.info(f"🎯 Período Donchian óptimo: {optimal_period}")
    
    print("-" * 50)

def example_risk_management():
    """Ejemplo de gestión de riesgo cuantitativo"""
    print("🛡️  Ejemplo de Gestión de Riesgo Cuantitativo")
    print("-" * 50)
    
    # Inicializar el motor cuantitativo
    quant_engine = QuantitativeEngine()
    
    # Simular diferentes condiciones del mercado
    market_conditions = [
        {"adx": 45.0, "di_plus": 35.0, "di_minus": 10.0, "scenario": "Tendencia Fuerte Alcista"},
        {"adx": 15.0, "di_plus": 20.0, "di_minus": 18.0, "scenario": "Mercado Sin Tendencia"},
        {"adx": 38.0, "di_plus": 12.0, "di_minus": 32.0, "scenario": "Tendencia Fuerte Bajista"}
    ]
    
    prices = 1.3000 + np.cumsum(np.random.normal(0, 0.001, 150))
    
    for condition in market_conditions:
        logger.info(f"📈 Escenario: {condition['scenario']}")
        
        result = quant_engine.calculate_entry_score(
            prices=prices,
            adx_value=condition['adx'],
            di_plus=condition['di_plus'],
            di_minus=condition['di_minus']
        )
        
        position_size = quant_engine.calculate_optimal_position_size(
            entry_score=result['entry_score'],
            account_balance=15000
        )
        
        logger.info(f"  Puntaje: {result['entry_score']:.3f}")
        logger.info(f"  Recomendación: {result['recommendation']}")
        logger.info(f"  Tamaño de posición: {position_size:.3f} lotes")
        print()

def main():
    """Función principal del ejemplo"""
    print("🚀 Ejemplos de Sistema Cuantitativo de Trading")
    print("=" * 60)
    
    try:
        # Ejemplo básico de análisis cuantitativo
        example_basic_quant_analysis()
        
        # Ejemplo de integración con estrategia
        example_strategy_integration()
        
        # Ejemplo de optimización de parámetros
        example_parameter_optimization()
        
        # Ejemplo de gestión de riesgo
        example_risk_management()
        
        print("=" * 60)
        print("✅ Todos los ejemplos se ejecutaron correctamente")
        print("📈 El sistema cuantitativo está listo para usar en trading real")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Error en los ejemplos: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())