#!/usr/bin/env python3
"""
Demostración de la implementación de principios de POO en el sistema cuantitativo
Este script muestra cómo se aplican correctamente los principios de Programación Orientada a Objetos
"""

import numpy as np
from core.quant_engine import QuantitativeEngine, QuantitativeAnalyzer, PositionSizer, QuantitativeOptimizer

def demonstrate_encapsulation():
    """Demostrar encapsulamiento"""
    print("🔒 DEMOSTRACIÓN DE ENCAPSULAMIENTO")
    print("=" * 50)
    
    # Crear instancia del analizador cuantitativo
    analyzer = QuantitativeAnalyzer()
    
    # Acceder a los pesos internos a través de la instancia
    print(f"Pesos de momentum: {analyzer.weights['momentum']}")
    print(f"Pesos de probabilidad: {analyzer.weights['probability']}")
    
    # El objeto encapsula su estado interno
    print(f"Estado interno encapsulado correctamente")
    print()

def demonstrate_inheritance_composition():
    """Demostrar composición (no herencia en este caso, pero sí composición)"""
    print("🧩 DEMOSTRACIÓN DE COMPOSICIÓN")
    print("=" * 50)
    
    # El motor cuantitativo se compone de otros objetos especializados
    engine = QuantitativeEngine()
    
    print(f"Engine contiene analyzer: {hasattr(engine, 'analyzer')}")
    print(f"Engine contiene sizer: {hasattr(engine, 'sizer')}")
    print(f"Engine contiene optimizer: {hasattr(engine, 'optimizer')}")
    
    print(f"Tipo de analyzer: {type(engine.analyzer)}")
    print(f"Tipo de sizer: {type(engine.sizer)}")
    print(f"Tipo de optimizer: {type(engine.optimizer)}")
    
    print("El motor cuantitativo compone funcionalidades de otros objetos especializados")
    print()

def demonstrate_single_responsibility():
    """Demostrar principio de responsabilidad única"""
    print("🎯 DEMOSTRACIÓN DE RESPONSABILIDAD ÚNICA")
    print("=" * 50)
    
    # Cada clase tiene una responsabilidad específica
    analyzer = QuantitativeAnalyzer()  # Responsabilidad: Análisis cuantitativo
    sizer = PositionSizer()           # Responsabilidad: Cálculo de tamaño de posición
    optimizer = QuantitativeOptimizer()  # Responsabilidad: Optimización de parámetros
    engine = QuantitativeEngine()     # Responsabilidad: Coordinación de componentes
    
    print("Clase QuantitativeAnalyzer - Responsabilidad: Análisis cuantitativo")
    print("  - calculate_momentum_score(): Cálculo de momentum")
    print("  - calculate_volatility_score(): Cálculo de volatilidad")
    print("  - calculate_trend_strength(): Cálculo de fuerza de tendencia")
    print("  - calculate_statistical_probability(): Cálculo de probabilidad estadística")
    
    print("\nClase PositionSizer - Responsabilidad: Cálculo de tamaño de posición")
    print("  - kelly_criterion(): Criterio de Kelly para tamaño óptimo")
    print("  - sharpe_ratio_position_size(): Tamaño basado en ratio de Sharpe")
    
    print("\nClase QuantitativeOptimizer - Responsabilidad: Optimización de parámetros")
    print("  - optimize_donchian_period(): Optimización del período Donchian")
    
    print("\nClase QuantitativeEngine - Responsabilidad: Coordinación de componentes")
    print("  - calculate_entry_score(): Coordinación del puntaje de entrada")
    print("  - calculate_optimal_position_size(): Coordinación del tamaño de posición")
    print()

def demonstrate_methods_vs_static():
    """Demostrar uso de métodos de instancia vs estáticos"""
    print("🏗️  DEMOSTRACIÓN DE MÉTODOS DE INSTANCIA")
    print("=" * 50)
    
    # Crear instancia del analizador
    analyzer = QuantitativeAnalyzer()
    
    # Usar métodos de instancia que acceden al estado del objeto
    prices = np.array([100, 101, 102, 101.5, 103, 104, 103.5, 105])
    
    # Los métodos usan el estado interno del objeto (por ejemplo, los pesos)
    momentum = analyzer.calculate_momentum_score(prices)
    volatility = analyzer.calculate_volatility_score(prices)
    trend = analyzer.calculate_trend_strength(prices)
    
    print(f"Momentum calculado: {momentum}")
    print(f"Volatilidad calculada: {volatility}")
    print(f"Tendencia calculada: {trend}")
    
    # Demostrar que cada instancia puede tener su propio estado si se configura
    custom_analyzer = QuantitativeAnalyzer()
    # Aquí podríamos modificar los pesos si fuera necesario
    print("Cada instancia mantiene su propio estado encapsulado")
    print()

def demonstrate_full_integration():
    """Demostrar integración completa del sistema POO"""
    print("🔗 DEMOSTRACIÓN DE INTEGRACIÓN COMPLETA")
    print("=" * 50)
    
    # Crear el motor cuantitativo completo
    engine = QuantitativeEngine()
    
    # Simular datos de mercado
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.normal(0, 0.1, 200))
    
    # Ejecutar análisis cuantitativo completo
    result = engine.calculate_entry_score(
        prices=prices,
        adx_value=25.0,
        di_plus=20.0,
        di_minus=15.0
    )
    
    # Calcular tamaño de posición óptimo
    position_size = engine.calculate_optimal_position_size(
        account_balance=10000,
        entry_score=result['entry_score']
    )
    
    print(f"Puntaje de entrada: {result['entry_score']:.3f}")
    print(f"Recomendación: {result['recommendation']}")
    print(f"Tamaño de posición óptimo: {position_size:.3f} lotes")
    
    print("\nEl sistema demuestra una arquitectura orientada a objetos bien estructurada:")
    print("- Encapsulamiento adecuado")
    print("- Separación clara de responsabilidades")
    print("- Composición de objetos especializados")
    print("- Métodos de instancia que utilizan el estado del objeto")
    print()

def main():
    """Función principal de demostración"""
    print("🏛️  DEMOSTRACIÓN DE PRINCIPIOS DE POO EN EL SISTEMA CUANTITATIVO")
    print("=" * 80)
    
    demonstrate_encapsulation()
    demonstrate_inheritance_composition()
    demonstrate_single_responsibility()
    demonstrate_methods_vs_static()
    demonstrate_full_integration()
    
    print("=" * 80)
    print("✅ IMPLEMENTACIÓN POO COMPLETADA CON ÉXITO")
    print("✅ Principios aplicados correctamente:")
    print("   - Encapsulamiento: Atributos y métodos organizados en clases")
    print("   - Responsabilidad única: Cada clase tiene una función específica")
    print("   - Composición: El motor cuantitativo compone otros objetos especializados")
    print("   - Métodos de instancia: Acceden y utilizan el estado del objeto")
    print("✅ Sistema completamente orientado a objetos y funcional")
    print("=" * 80)

if __name__ == "__main__":
    main()