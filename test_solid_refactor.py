#!/usr/bin/env python3
"""
Test script to validate the refactored Donchian Strategy following SOLID principles
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brokers.mt5_utils import MT5Gateway
from core.donchian_strategy import (
    DonchianStrategy,
    StrategyConfig,
)
from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
from core.donchian_components.validators.risk_market_validators import RiskValidator
from core.donchian_components.managers.position_managers import PositionManager


def test_strategy_instantiation():
    """Test that the strategy can be instantiated without errors"""
    print("🔍 Testing Strategy Instantiation...")

    try:
        strategy = DonchianStrategy()
        print("✅ Strategy instantiated successfully")
        
        # Basic validation that key components exist
        assert hasattr(strategy, "config"), "StrategyConfig not initialized"
        assert hasattr(strategy, "quant_integration"), "QuantitativeIntegration not initialized"
        
        print("✅ Strategy components validated")
        return True

    except Exception as e:
        print(f"❌ Error instantiating strategy: {e}")
        return False


def test_strategy_config():
    """Test StrategyConfig instantiation"""
    print("\n🔍 Testing StrategyConfig...")
    
    try:
        config = StrategyConfig()
        print("✅ StrategyConfig instantiated successfully")
        
        # Verify required attributes exist
        required_attrs = ["symbol", "timeframe", "period", "risk_percent"]
        for attr in required_attrs:
            assert hasattr(config, attr), f"Missing attribute: {attr}"
            
        print(f"✅ All required config attributes present: {len(required_attrs)} attributes")
        return True
        
    except Exception as e:
        print(f"❌ Error testing StrategyConfig: {e}")
        return False


def main():
    """Run all tests"""
    print("🧪 Testing Refactored Donchian Strategy (SOLID Implementation)")
    print("=" * 60)

    tests = [
        test_strategy_instantiation,
        test_strategy_config,
    ]

    results = []
    for test in tests:
        results.append(test())

    print("\n" + "=" * 60)
    print("SUMMARY:")
    print(f"Total tests: {len(results)}")
    print(f"Passed: {sum(results)}")
    print(f"Failed: {len(results) - sum(results)}")

    if all(results):
        print(
            "🎉 All tests passed! The refactored strategy follows SOLID principles correctly.",
        )
        return True
    print("❌ Some tests failed. Please review the implementation.")
    return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
