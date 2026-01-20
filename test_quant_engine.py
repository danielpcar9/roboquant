"""
Test script for the quantitative trading engine
"""
import numpy as np
from core.quant_engine import QuantitativeEngine, QuantitativeAnalyzer, PositionSizer, QuantitativeOptimizer

def test_quantitative_analyzer():
    """Test the quantitative analyzer components"""
    print("=== Testing Quantitative Analyzer ===")

    analyzer = QuantitativeAnalyzer()

    # Create sample price data
    np.random.seed(42)
    base_price = 100
    trend = np.linspace(0, 10, 100)  # Upward trend
    noise = np.random.normal(0, 1, 100)  # Random noise
    prices = base_price + trend + noise

    # Test momentum score
    momentum = analyzer.calculate_momentum_score(prices)
    print(f"Momentum Score: {momentum:.3f}")

    # Test volatility score
    volatility = analyzer.calculate_volatility_score(prices)
    print(f"Volatility Score: {volatility:.3f}")

    # Test trend strength
    trend_strength = analyzer.calculate_trend_strength(prices)
    print(f"Trend Strength: {trend_strength:.3f}")

    # Test statistical probability calculation
    prob_result = analyzer.calculate_statistical_probability(
        momentum_score=momentum,
        volatility_score=volatility,
        trend_strength=trend_strength,
        adx_value=25.0,
        di_plus=20.0,
        di_minus=15.0
    )
    print(f"Entry Probability: {prob_result['probability']:.3f}")
    print(f"Components: {prob_result['components']}")

    return True

def test_position_sizer():
    """Test the position sizing components"""
    print("\n=== Testing Position Sizer ===")

    sizer = PositionSizer()

    # Test Kelly Criterion
    kelly_size = sizer.kelly_criterion(
        win_rate=0.55,
        avg_win_ratio=2.0,
        avg_loss_ratio=1.0
    )
    print(f"Kelly Criterion Size: {kelly_size:.3f}")

    # Test Sharpe-based position sizing
    returns = np.random.normal(0.001, 0.02, 100)  # Simulated returns
    sharpe_size = sizer.sharpe_ratio_position_size(returns)
    print(f"Sharpe-based Size: {sharpe_size:.3f}")

    return True

def test_optimizer():
    """Test the optimization components"""
    print("\n=== Testing Optimizer ===")

    optimizer = QuantitativeOptimizer()

    # Create sample price data
    np.random.seed(42)
    base_price = 100
    trend = np.linspace(0, 5, 200)  # Gentle trend
    noise = np.random.normal(0, 0.5, 200)  # Low noise for clearer signals
    prices = base_price + trend + noise

    # Test Donchian period optimization
    optimal_period = optimizer.optimize_donchian_period(prices)
    print(f"Optimal Donchian Period: {optimal_period}")

    return True

def test_full_engine():
    """Test the full quantitative engine"""
    print("\n=== Testing Full Quantitative Engine ===")

    engine = QuantitativeEngine()

    # Create sample price data
    np.random.seed(42)
    base_price = 100
    trend = np.linspace(0, 8, 150)  # Moderate upward trend
    noise = np.random.normal(0, 1.2, 150)  # Moderate noise
    prices = base_price + trend + noise

    # Test entry score calculation
    entry_result = engine.calculate_entry_score(
        prices=prices,
        adx_value=28.0,
        di_plus=25.0,
        di_minus=12.0
    )

    print(f"Entry Score: {entry_result['entry_score']:.3f}")
    print(f"Recommendation: {entry_result['recommendation']}")
    print(f"Filters passed: {entry_result['filters']}")

    # Test position sizing
    position_size = engine.calculate_optimal_position_size(
        account_balance=10000,
        entry_score=entry_result['entry_score']
    )
    print(f"Optimal Position Size: {position_size:.3f} lots")

    return True

def run_all_tests():
    """Run all tests"""
    print("Starting Quantitative Engine Tests...\n")

    try:
        test_quantitative_analyzer()
        test_position_sizer()
        test_optimizer()
        test_full_engine()

        print("\n✅ All tests passed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    run_all_tests()
