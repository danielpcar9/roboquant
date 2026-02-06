#!/usr/bin/env python3
"""Debug script to isolate ML training error"""

from core.mt5_compat import mt5, MT5_AVAILABLE
import numpy as np

from core.quant.validators.ml_validator import MLStrategyValidator


def debug_training_error():
    """Debug the specific training error"""
    print("🔍 Debugging ML Training Error")
    print("=" * 40)

    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return

    try:
        validator = MLStrategyValidator()
        symbol = "XAUUSD"
        n_days = 5  # Very small amount for testing

        print(f"Testing with {n_days} days of data...")

        # Step by step debugging
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, n_days * 24)
        print(f"Got {len(rates) if rates is not None else 0} rates")

        if rates is None or len(rates) < 10:
            print("❌ Insufficient data")
            return

        prices = np.array([rate[4] for rate in rates]).astype(np.float64)
        print(f"Prices shape: {prices.shape}, type: {prices.dtype}")
        print(f"Sample prices: {prices[:5]}")

        # Test label creation
        try:
            labels = validator.create_labels(prices, window=3, threshold=0.005)
            print(f"Labels created: {len(labels)} labels")
            print(f"Label distribution: BUY={np.sum(labels==1)}, SELL={np.sum(labels==-1)}, HOLD={np.sum(labels==0)}")
        except Exception as e:
            print(f"❌ Label creation failed: {e}")
            import traceback
            traceback.print_exc()
            return

        # Test feature extraction for one point
        try:
            print("Testing feature extraction...")
            features = validator.extract_features(symbol)
            print(f"Features extracted: {bool(features)}")
            if features:
                print(f"Feature keys: {list(features.keys())}")
                print(f"Sample values: {list(features.values())[:3]}")
        except Exception as e:
            print(f"❌ Feature extraction failed: {e}")
            import traceback
            traceback.print_exc()
            return

        print("✅ All basic components working")

    except Exception as e:
        print(f"❌ Overall error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    debug_training_error()
