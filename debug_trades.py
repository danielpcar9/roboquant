#!/usr/bin/env python3
"""Test para diagnosticar por qué no se abren trades"""

from core.mt5_compat import mt5, MT5_AVAILABLE
import numpy as np

from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from core.quant.engine import QuantitativeEngine


def test_current_market_conditions():
    """Test con condiciones de mercado actuales"""
    print("🔍 DIAGNÓSTICO DE APERTURA DE TRADES")
    print("=" * 50)

    # Inicializar MT5
    if not mt5.initialize():
        print("❌ No se pudo inicializar MT5")
        return

    try:
        # Inicializar componentes
        calculator = TechnicalIndicatorsCalculator()
        engine = QuantitativeEngine()

        symbol = "XAUUSD"

        # Obtener datos reales del mercado
        print("📡 Obteniendo datos de mercado...")

        # Datos de precios
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        if rates is None:
            print("❌ No se pudieron obtener datos de precios")
            return

        prices = np.array([rate[4] for rate in rates])  # close prices
        print(f"✅ Precios obtenidos: {len(prices)} velas")

        # Datos ADX/DI
        adx_data = calculator.calculate_adx(symbol, 14)
        if adx_data is None:
            print("❌ No se pudo calcular ADX")
            return

        adx_value = adx_data['adx']
        di_plus = adx_data['di_plus']
        di_minus = adx_data['di_minus']

        print(f"📊 ADX: {adx_value:.2f}")
        print(f"📊 DI+: {di_plus:.2f}")
        print(f"📊 DI-: {di_minus:.2f}")
        print(f"📊 DI Diferencia: {di_plus - di_minus:.2f}")

        # Análisis cuantitativo
        print("\n🧮 Análisis Cuantitativo:")
        result = engine.calculate_entry_score(prices, adx_value, di_plus, di_minus)

        print(f"🎯 Puntaje: {result['entry_score']:.3f}")
        print(f"💡 Recomendación: {result['recommendation']}")
        print(f"📊 Componentes: {result['components']}")

        # Verificar umbrales
        print("\n📋 Verificación de Umbrales:")
        print(f"  0.70+ (STRONG): {'✅' if result['entry_score'] >= 0.70 else '❌'}")
        print(f"  0.60+ (BUY):    {'✅' if result['entry_score'] >= 0.60 else '❌'}")
        print(f"  0.40+ (HOLD):   {'✅' if result['entry_score'] >= 0.40 else '❌'}")
        print(f"  <0.40 (AVOID):  {'✅' if result['entry_score'] < 0.40 else '❌'}")

        # Simular diferentes escenarios
        print("\n🧪 Escenarios Hipotéticos:")

        # Escenario 1: Aumentar ADX
        print("1. Si ADX aumentara a 60:")
        result2 = engine.calculate_entry_score(prices, 60.0, di_plus, di_minus)
        print(f"   Puntaje: {result2['entry_score']:.3f} - {result2['recommendation']}")

        # Escenario 2: Aumentar DI diferencia
        print("2. Si DI+ aumentara a 35:")
        result3 = engine.calculate_entry_score(prices, adx_value, 35.0, di_minus)
        print(f"   Puntaje: {result3['entry_score']:.3f} - {result3['recommendation']}")

        # Escenario 3: Combinación óptima
        print("3. Condiciones óptimas (ADX=60, DI+=35, DI-=5):")
        result4 = engine.calculate_entry_score(prices, 60.0, 35.0, 5.0)
        print(f"   Puntaje: {result4['entry_score']:.3f} - {result4['recommendation']}")

        # Verificar lógica de señales Donchian
        print("\n📉 Análisis Donchian:")
        upper, lower = calculator.get_donchian_channels(symbol, 50)
        current_price = calculator.get_current_price(symbol, "BUY")

        if upper and lower and current_price:
            print(f"   Canal Superior: {upper:.2f}")
            print(f"   Canal Inferior: {lower:.2f}")
            print(f"   Precio Actual: {current_price:.2f}")
            print(f"   Breakout Alcista: {'✅' if current_price > upper else '❌'}")
            print(f"   Breakout Bajista: {'✅' if current_price < lower else '❌'}")
        else:
            print("   ❌ No se pudieron obtener canales Donchian")

    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    test_current_market_conditions()
