#!/usr/bin/env python3
"""
Script to test that the strategy is using 2% risk per trade
"""

import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_strategy_risk():
    print("=" * 50)
    print("TESTING STRATEGY RISK CONFIGURATION")
    print("=" * 50)

    try:
        # Test donchian_strategy
        print("\n1. Testing donchian_strategy.StrategyConfig:")
        from core.donchian_strategy import StrategyConfig
        config1 = StrategyConfig()
        print(f"   Risk percent: {config1.risk_percent}%")

        # Test current strategy configuration
        print("\n2. Testing current StrategyConfig:")
        from core.donchian_strategy import StrategyConfig as CurrentStrategyConfig
        config2 = CurrentStrategyConfig()
        print(f"   Risk percent: {config2.risk_percent}%")

        # Verify both use 2.0%
        if config1.risk_percent == 2.0 and config2.risk_percent == 2.0:
            print("\n✅ SUCCESS: Strategy is configured to use 2.0% risk per trade")
        else:
            print(f"\n❌ ERROR: Expected 2.0% risk, got {config1.risk_percent}% and {config2.risk_percent}%")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")

    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_strategy_risk()
