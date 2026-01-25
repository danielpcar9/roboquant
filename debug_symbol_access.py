#!/usr/bin/env python3
"""Debug MT5 symbol availability"""

import MetaTrader5 as mt5


def debug_symbol_access():
    """Debug symbol access issues"""
    print("🔍 Debugging Symbol Access")
    print("=" * 30)

    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return

    try:
        symbol = "XAUUSD"

        # Check if symbol exists
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"❌ Symbol {symbol} not found")

            # List available symbols
            symbols = mt5.symbols_get()
            if symbols:
                print(f"📝 Available symbols ({len(symbols)} total):")
                gold_symbols = [s.name for s in symbols if 'GOLD' in s.name.upper() or 'XAU' in s.name.upper()]
                print(f"Gold-related symbols: {gold_symbols[:10]}")  # Show first 10
            return
        else:
            print(f"✅ Symbol {symbol} found")
            print(f"   Path: {symbol_info.path}")
            print(f"   Description: {symbol_info.description}")

        # Try to get rates
        print("\n📈 Testing data retrieval:")
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)
        if rates is not None:
            print(f"✅ Got {len(rates)} bars")
            print(f"   First bar: {rates[0]}")
            print(f"   Last bar: {rates[-1]}")
        else:
            print(f"❌ Failed to get rates for {symbol}")

        # Try alternative symbols
        alternatives = ['GOLD', 'XAUUSDm', 'XAUUSD.pro']
        print("\n🧪 Testing alternative symbols:")
        for alt_symbol in alternatives:
            alt_rates = mt5.copy_rates_from_pos(alt_symbol, mt5.TIMEFRAME_H1, 0, 10)
            if alt_rates is not None:
                print(f"✅ {alt_symbol}: {len(alt_rates)} bars")
            else:
                print(f"❌ {alt_symbol}: No data")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    debug_symbol_access()
