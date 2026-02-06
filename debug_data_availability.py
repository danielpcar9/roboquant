#!/usr/bin/env python3
"""Debug script to check available MT5 data"""

from core.mt5_compat import mt5, MT5_AVAILABLE
import numpy as np


def check_available_data():
    """Check how much historical data is available"""
    print("🔍 Checking MT5 Data Availability")
    print("=" * 40)

    # Initialize MT5
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return

    try:
        symbol = "XAUUSD"

        # Try different amounts of data
        for days in [1, 5, 10, 30, 60, 90]:
            bars_needed = days * 24
            print(f"\nTesting {days} days ({bars_needed} bars):")

            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, bars_needed)
            if rates is not None:
                print(f"  ✅ Got {len(rates)} bars")
                if len(rates) >= bars_needed * 0.8:  # At least 80% of requested
                    print("  📊 Data looks good for training")
                elif len(rates) > 50:
                    print("  ⚠️  Limited data available")
                else:
                    print("  ❌ Insufficient data")
            else:
                print("  ❌ No data returned")

        # Check what we can actually get
        print("\n📈 Maximum available data test:")
        max_bars = 1000  # Try to get maximum
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, max_bars)
        if rates is not None:
            actual_bars = len(rates)
            hours_available = actual_bars
            days_available = hours_available / 24
            print(f"  Maximum bars available: {actual_bars}")
            print(f"  Hours of data: {hours_available}")
            print(f"  Days of data: {days_available:.1f}")

            # Show some statistics
            prices = np.array([rate[4] for rate in rates])
            print(f"  Price range: {prices.min():.2f} - {prices.max():.2f}")
            print(f"  Price volatility: {np.std(prices):.2f}")
        else:
            print("  ❌ Cannot get any historical data")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    check_available_data()
