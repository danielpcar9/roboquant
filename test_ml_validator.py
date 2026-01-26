#!/usr/bin/env python3
"""Script para probar el ML Strategy Validator con datos reales"""

import logging

from core.quant.validators.ml_validator import MLStrategyValidator


def test_ml_validator():
    """Prueba el ML validator con datos de mercado reales"""
    logging.basicConfig(level=logging.INFO)

    print("🤖 Probando ML Strategy Validator")
    print("=" * 40)

    try:
        # Inicializar el validador
        print("Inicializando ML Validator...")
        validator = MLStrategyValidator()

        symbol = "XAUUSD"
        print(f"Probando con símbolo: {symbol}")

        # Extraer features
        print("\n📊 Extrayendo features de mercado...")
        features = validator.extract_features(symbol)

        if not features:
            print("❌ No se pudieron extraer features")
            return False

        print("✅ Features extraídos exitosamente:")
        for feature, value in features.items():
            print(f"   {feature}: {value:.6f}")

        # Validar señal con ML
        print("\n🧠 Validando señal con ML...")
        should_trade, confidence, action = validator.validate_signal(features)

        print("✅ Validación ML completada:")
        print(f"   ¿Debería operar?: {should_trade}")
        print(f"   Confianza: {confidence:.3f}")
        print(f"   Acción predicha: {action}")

        # Mostrar decisión final
        print("\n🎯 Decisión Final:")
        if should_trade and confidence > 0.6:
            print(f"   ✅ TRADE RECOMENDADO - Confianza alta ({confidence:.1%})")
            print(f"   Acción sugerida: {action}")
        elif should_trade:
            print(f"   ⚠️  TRADE POSIBLE - Confianza moderada ({confidence:.1%})")
            print(f"   Acción sugerida: {action}")
        else:
            print(f"   ❌ NO OPERAR - Confianza baja ({confidence:.1%})")
            print(f"   Mantener posición: {action}")

        # Información adicional
        print("\n📋 Información del modelo:")
        print(f"   Modelo cargado: {'Sí' if validator.model else 'No'}")
        if validator.model:
            print(f"   Features esperados: {len(validator.feature_names)}")
            print(f"   Features disponibles: {len(features)}")

        return True

    except Exception as e:
        print(f"❌ Error durante la prueba: {e}")
        logging.exception("Error en prueba de ML validator")
        return False

def test_multiple_symbols():
    """Prueba el validador con múltiples símbolos"""
    print("\n" + "="*50)
    print("🔄 Probando múltiples símbolos")
    print("="*50)

    symbols_to_test = ["XAUUSD", "EURUSD", "GBPUSD"]
    validator = MLStrategyValidator()

    results = []

    for symbol in symbols_to_test:
        try:
            print(f"\nProbando {symbol}...")
            features = validator.extract_features(symbol)

            if features:
                should_trade, confidence, action = validator.validate_signal(features)
                results.append({
                    'symbol': symbol,
                    'should_trade': should_trade,
                    'confidence': confidence,
                    'action': action,
                    'features_count': len(features)
                })
                print(f"   Resultado: {action} (Confianza: {confidence:.1%})")
            else:
                print("   ❌ No hay datos suficientes")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Resumen
    print("\n📊 Resumen de pruebas:")
    print(f"   Símbolos probados: {len(results)}")

    trade_recommendations = [r for r in results if r['should_trade']]
    print(f"   Recomendados para trading: {len(trade_recommendations)}")

    for result in results:
        status = "✅ RECOMENDADO" if result['should_trade'] else "❌ NO RECOMENDADO"
        print(f"   {result['symbol']}: {status} ({result['action']}, {result['confidence']:.1%})")

if __name__ == "__main__":
    print("🚀 INICIANDO PRUEBAS DEL ML VALIDATOR")
    print("=" * 50)

    # Prueba individual
    success = test_ml_validator()

    if success:
        # Prueba múltiple
        test_multiple_symbols()
        print("\n✅ Todas las pruebas completadas exitosamente!")
    else:
        print("\n❌ Hubo errores en las pruebas")

    print("\n🏁 Fin de pruebas")
