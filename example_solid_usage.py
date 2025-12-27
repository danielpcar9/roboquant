#!/usr/bin/env python3
"""
Ejemplo de uso de la estrategia Donchian refactorizada con principios SOLID
"""

from core.donchian_strategy_refactored import DonchianStrategy


def demonstrate_solid_usage():
    """Demostrar el uso de la estrategia refactorizada"""
    print("🎯 Demostración de la Estrategia Donchian Refactorizada")
    print("=" * 55)
    
    print("\n1. Creación de la estrategia con arquitectura SOLID:")
    print("   - Se instancia la clase DonchianStrategy")
    print("   - Esta clase delega a servicios especializados")
    print("   - Cada servicio tiene una única responsabilidad")
    
    # Crear instancia de la estrategia
    strategy = DonchianStrategy()
    print("   ✅ Estrategia creada exitosamente")
    
    print("\n2. Servicios especializados integrados:")
    print(f"   - MarketDataService: {type(strategy.market_data).__name__}")
    print(f"   - RiskCalculator: {type(strategy.risk_calc).__name__}")
    print(f"   - SessionManager: {type(strategy.session_manager).__name__}")
    print(f"   - QuantitativeIntegration: {type(strategy.quant_integration).__name__}")
    
    print("\n3. Beneficios de la arquitectura SOLID:")
    print("   ✅ Separación de responsabilidades clara")
    print("   ✅ Fácil de testear cada componente por separado")
    print("   ✅ Fácil de extender con nuevas funcionalidades")
    print("   ✅ Código más mantenible y comprensible")
    print("   ✅ Reutilización de servicios en otros componentes")
    
    print("\n4. Ejemplo de uso en ejecución:")
    print("   # strategy.run_strategy('XAUUSD')  # Ejecutar estrategia")
    print("   # strategy.market_data.get_donchian_channels('XAUUSD', 20)  # Obtener canales")
    print("   # strategy.risk_calc.compute_lot_size(balance, risk_pct, sl_distance, 'XAUUSD')  # Calcular tamaño")
    
    print("\n🎉 La arquitectura refactorizada permite:")
    print("   • Mayor claridad en el código")
    print("   • Mejor mantenibilidad")
    print("   • Mayor facilidad para realizar pruebas unitarias")
    print("   • Extensibilidad sin afectar otros componentes")
    print("   • Cumplimiento de principios de diseño de software")


if __name__ == "__main__":
    demonstrate_solid_usage()