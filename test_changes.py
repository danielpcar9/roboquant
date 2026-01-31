#!/usr/bin/env python3
"""Script para probar los cambios en quantitative_integration"""

import logging

from core.quant.quantitative_integration import QuantitativeIntegration

# Configurar logging para ver mensajes de debug
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("=== TESTING NEW QUANTITATIVE INTEGRATION CHANGES ===")

# Crear instancia
q = QuantitativeIntegration()
print("✓ QuantitativeIntegration initialized")

# Probar análisis cuantitativo
try:
    result = q.apply_quantitative_analysis('XAUUSD')
    print("\n=== RESULTADOS ===")
    print(f"Should trade: {result['should_trade']}")
    print(f"Entry score: {result['entry_score']:.3f}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Reason: {result['reason']}")

    if 'ml_validation' in result:
        ml = result['ml_validation']
        print("\n=== ML VALIDATION ===")
        print(f"ML Approved: {ml['ml_approved']}")
        print(f"ML Confidence: {ml['ml_confidence']:.3f}")
        print(f"ML Action: {ml['ml_action']}")

    if 'market_data' in result:
        md = result['market_data']
        print("\n=== MARKET DATA ===")
        print(f"ADX: {md['adx']:.2f}")
        print(f"DI+: {md['di_plus']:.2f}")
        print(f"DI-: {md['di_minus']:.2f}")
        print(f"DI Diff: {md['di_difference']:.2f}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETADO ===")
