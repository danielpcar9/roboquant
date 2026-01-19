#!/usr/bin/env python3
"""
Script de prueba para verificar que el sistema funciona correctamente con uv
"""

import sys
import logging

# Configurar logging básico
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_imports():
    """Prueba las importaciones principales"""
    try:
        # Core modules
        from core.donchian_strategy import DonchianStrategy
        from core.quant_engine import QuantitativeEngine
        
        # Brokers
        from brokers.mt5_core import initialize_mt5
        from brokers.mt5_utils import monitor_and_update_stops
        
        # Config
        from config.config_manager import config_manager
        
        # Risk
        from risk.ftmo_manager import ftmo_manager
        
        print("✅ Todas las importaciones principales funcionan correctamente")
        return True
    except Exception as e:
        print(f"❌ Error en importaciones: {e}")
        return False

def test_quant_engine():
    """Prueba el motor cuantitativo"""
    try:
        from core.quant_engine import QuantitativeEngine
        engine = QuantitativeEngine()
        print("✅ QuantitativeEngine inicializado correctamente")
        
        # Prueba cálculo de tamaño de posición
        position_size = engine.calculate_optimal_position_size(
            account_balance=10000.0,
            entry_score=0.75
        )
        print(f"✅ Cálculo de posición: {position_size:.4f}")
        return True
    except Exception as e:
        print(f"❌ Error en QuantitativeEngine: {e}")
        return False

def test_config_loading():
    """Prueba carga de configuración"""
    try:
        from config.config_manager import config_manager
        
        # Probar obtener valor de configuración
        donchian_period = config_manager.get('DONCHIAN_PERIOD', 20)
        print(f"✅ Configuración accesible: DONCHIAN_PERIOD = {donchian_period}")
        return True
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("=" * 50)
    print("🧪 TEST DE VERIFICACIÓN DEL SISTEMA CON UV")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 3
    
    # Ejecutar tests
    if test_imports():
        tests_passed += 1
    
    if test_quant_engine():
        tests_passed += 1
        
    if test_config_loading():
        tests_passed += 1
    
    print("=" * 50)
    print(f"RESULTADOS: {tests_passed}/{total_tests} tests pasados")
    
    if tests_passed == total_tests:
        print("🎉 ¡Todos los tests pasaron! El sistema está listo para usar con uv.")
        return 0
    else:
        print("⚠️  Algunos tests fallaron. Revisa los errores arriba.")
        return 1

if __name__ == "__main__":
    sys.exit(main())