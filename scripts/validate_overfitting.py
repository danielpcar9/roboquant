"""
Overfitting Detection Tool
Validates strategy robustness using multiple techniques
"""
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from scripts.backtest_apex_vectorbt import load_data, run_backtest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def walk_forward_analysis(df, n_splits=5, optimization_ratio=0.7):
    """
    Walk-Forward Analysis: The gold standard for overfitting detection
    
    Splits data into multiple periods:
    - In-Sample (IS): Used for optimization
    - Out-of-Sample (OOS): Used for validation (not touched during optimization)
    
    Args:
        df: Historical data
        n_splits: Number of walk-forward windows
        optimization_ratio: % of each window used for IS (typically 0.6-0.8)
    
    Returns:
        DataFrame with IS vs OOS performance comparison
    """
    logging.info("="*70)
    logging.info("🔍 WALK-FORWARD ANALYSIS - Overfitting Detection")
    logging.info("="*70)
    
    total_rows = len(df)
    window_size = total_rows // n_splits
    
    results = []
    
    for i in range(n_splits):
        start_idx = i * window_size
        end_idx = min((i + 1) * window_size, total_rows)
        
        if end_idx >= total_rows:
            end_idx = total_rows
        
        window_df = df.iloc[start_idx:end_idx]
        
        # Split window into IS and OOS
        is_size = int(len(window_df) * optimization_ratio)
        is_df = window_df.iloc[:is_size]
        oos_df = window_df.iloc[is_size:]
        
        logging.info(f"\n📊 Window {i+1}/{n_splits}")
        logging.info(f"   Period: {window_df.index[0]} → {window_df.index[-1]}")
        logging.info(f"   IS: {len(is_df)} bars, OOS: {len(oos_df)} bars")
        
        # Run backtest on In-Sample
        logging.info("   ⏳ Running In-Sample backtest...")
        is_portfolio = run_backtest(
            is_df.copy(),
            initial_capital=10000,
            donchian_period=20,
            momentum_period=40,
            sample_period=200,  # Reduced from 1000 for more signals
            sl_points=150,
            tp_points=300
        )
        
        # Run backtest on Out-of-Sample
        logging.info("   ⏳ Running Out-of-Sample backtest...")
        oos_portfolio = run_backtest(
            oos_df.copy(),
            initial_capital=10000,
            donchian_period=20,
            momentum_period=40,
            sample_period=200,  # Reduced from 1000 for more signals
            sl_points=150,
            tp_points=300
        )
        
        if is_portfolio and oos_portfolio:
            is_return = is_portfolio.total_return() * 100
            oos_return = oos_portfolio.total_return() * 100
            is_sharpe = is_portfolio.sharpe_ratio()
            oos_sharpe = oos_portfolio.sharpe_ratio()
            is_trades = is_portfolio.trades.count()
            oos_trades = oos_portfolio.trades.count()
            
            # Calculate degradation
            return_degradation = ((is_return - oos_return) / abs(is_return) * 100) if is_return != 0 else 0
            sharpe_degradation = ((is_sharpe - oos_sharpe) / abs(is_sharpe) * 100) if is_sharpe != 0 else 0
            
            results.append({
                'Window': i + 1,
                'Period': f"{window_df.index[0].strftime('%Y-%m')} → {window_df.index[-1].strftime('%Y-%m')}",
                'IS_Return_%': round(is_return, 2),
                'OOS_Return_%': round(oos_return, 2),
                'Return_Degradation_%': round(return_degradation, 2),
                'IS_Sharpe': round(is_sharpe, 2),
                'OOS_Sharpe': round(oos_sharpe, 2),
                'Sharpe_Degradation_%': round(sharpe_degradation, 2),
                'IS_Trades': is_trades,
                'OOS_Trades': oos_trades
            })
            
            logging.info(f"   IS Return: {is_return:.2f}% | OOS Return: {oos_return:.2f}%")
            logging.info(f"   IS Sharpe: {is_sharpe:.2f} | OOS Sharpe: {oos_sharpe:.2f}")
            logging.info(f"   Degradation: {return_degradation:.1f}%")
    
    results_df = pd.DataFrame(results)
    
    # Overall assessment
    avg_degradation = results_df['Return_Degradation_%'].mean()
    
    print("\n" + "="*70)
    print("📊 WALK-FORWARD RESULTS SUMMARY")
    print("="*70)
    print(results_df.to_string(index=False))
    print("="*70)
    print(f"\n🎯 Average Performance Degradation: {avg_degradation:.1f}%")
    
    # Overfitting assessment
    if avg_degradation < 20:
        print("   ✅ EXCELLENT - Low overfitting risk")
        print("   Strategy generalizes well to unseen data")
    elif avg_degradation < 40:
        print("   ⚠️  MODERATE - Some overfitting detected")
        print("   Consider simplifying parameters or adding filters")
    else:
        print("   ❌ HIGH OVERFITTING - Strategy likely overfit to historical data")
        print("   Rethink strategy logic and reduce parameter count")
    
    # Save results
    results_df.to_csv("walk_forward_results.csv", index=False)
    logging.info("\n📁 Results saved: walk_forward_results.csv")
    
    return results_df


def robustness_test(df, base_params):
    """
    Parameter Robustness Test
    Tests if strategy works with slightly different parameters
    
    A robust strategy should perform reasonably well with ±10-20% parameter variation
    """
    logging.info("\n" + "="*70)
    logging.info("🔧 PARAMETER ROBUSTNESS TEST")
    logging.info("="*70)
    
    # Base parameters
    base_donchian = base_params.get('donchian_period', 20)
    base_sl = base_params.get('sl_points', 150)
    base_tp = base_params.get('tp_points', 300)
    
    # Test variations (±20%)
    variations = [
        {'name': 'Base', 'donchian': base_donchian, 'sl': base_sl, 'tp': base_tp, 'sample': 200},
        {'name': '-20%', 'donchian': int(base_donchian * 0.8), 'sl': int(base_sl * 0.8), 'tp': int(base_tp * 0.8), 'sample': 160},
        {'name': '-10%', 'donchian': int(base_donchian * 0.9), 'sl': int(base_sl * 0.9), 'tp': int(base_tp * 0.9), 'sample': 180},
        {'name': '+10%', 'donchian': int(base_donchian * 1.1), 'sl': int(base_sl * 1.1), 'tp': int(base_tp * 1.1), 'sample': 220},
        {'name': '+20%', 'donchian': int(base_donchian * 1.2), 'sl': int(base_sl * 1.2), 'tp': int(base_tp * 1.2), 'sample': 240},
    ]
    
    results = []
    
    for var in variations:
        logging.info(f"\n📊 Testing {var['name']} variation")
        logging.info(f"   Donchian: {var['donchian']}, SL: {var['sl']}, TP: {var['tp']}")
        
        portfolio = run_backtest(
            df.copy(),
            initial_capital=10000,
            donchian_period=var['donchian'],
            momentum_period=40,
            sample_period=var['sample'],
            sl_points=var['sl'],
            tp_points=var['tp']
        )
        
        if portfolio:
            results.append({
                'Variation': var['name'],
                'Donchian': var['donchian'],
                'SL': var['sl'],
                'TP': var['tp'],
                'Return_%': round(portfolio.total_return() * 100, 2),
                'Sharpe': round(portfolio.sharpe_ratio(), 2),
                'Max_DD_%': round(portfolio.max_drawdown() * 100, 2),
                'Win_Rate_%': round(portfolio.trades.win_rate() * 100, 2),
                'Trades': portfolio.trades.count()
            })
    
    results_df = pd.DataFrame(results)
    
    print("\n" + "="*70)
    print("📊 ROBUSTNESS TEST RESULTS")
    print("="*70)
    print(results_df.to_string(index=False))
    print("="*70)
    
    # Calculate stability score
    returns = results_df['Return_%']
    return_std = returns.std()
    return_mean = returns.mean()
    coefficient_of_variation = (return_std / abs(return_mean) * 100) if return_mean != 0 else 999
    
    print(f"\n🎯 Return Variability (CV): {coefficient_of_variation:.1f}%")
    
    if coefficient_of_variation < 30:
        print("   ✅ ROBUST - Strategy performs consistently across parameters")
    elif coefficient_of_variation < 60:
        print("   ⚠️  MODERATE - Some parameter sensitivity detected")
    else:
        print("   ❌ FRAGILE - Strategy highly dependent on specific parameters")
        print("   This is a strong sign of overfitting")
    
    # Save results
    results_df.to_csv("robustness_test_results.csv", index=False)
    logging.info("\n📁 Results saved: robustness_test_results.csv")
    
    return results_df


def period_stability_test(df, years_back=5):
    """
    Period Stability Test
    Tests if strategy works consistently across different market periods
    """
    logging.info("\n" + "="*70)
    logging.info("📅 PERIOD STABILITY TEST")
    logging.info("="*70)
    
    results = []
    
    end_date = df.index[-1]
    
    for year_offset in range(years_back):
        year_end = end_date - timedelta(days=365 * year_offset)
        year_start = year_end - timedelta(days=365)
        
        year_df = df[(df.index >= year_start) & (df.index < year_end)]
        
        if len(year_df) < 100:
            logging.warning(f"   Skipping year {year_end.year} - insufficient data")
            continue
        
        logging.info(f"\n📊 Testing year ending {year_end.strftime('%Y-%m')}")
        
        portfolio = run_backtest(
            year_df.copy(),
            initial_capital=10000,
            donchian_period=20,
            momentum_period=40,
            sample_period=200,
            sl_points=150,
            tp_points=300
        )
        
        if portfolio:
            results.append({
                'Year': year_end.strftime('%Y'),
                'Period': f"{year_start.strftime('%Y-%m')} → {year_end.strftime('%Y-%m')}",
                'Return_%': round(portfolio.total_return() * 100, 2),
                'Sharpe': round(portfolio.sharpe_ratio(), 2),
                'Max_DD_%': round(portfolio.max_drawdown() * 100, 2),
                'Win_Rate_%': round(portfolio.trades.win_rate() * 100, 2),
                'Trades': portfolio.trades.count()
            })
    
    results_df = pd.DataFrame(results)
    
    print("\n" + "="*70)
    print("📊 PERIOD STABILITY RESULTS")
    print("="*70)
    print(results_df.to_string(index=False))
    print("="*70)
    
    # Assess consistency
    positive_years = len(results_df[results_df['Return_%'] > 0])
    total_years = len(results_df)
    consistency_rate = (positive_years / total_years * 100) if total_years > 0 else 0
    
    print(f"\n🎯 Profitable Years: {positive_years}/{total_years} ({consistency_rate:.0f}%)")
    
    if consistency_rate >= 80:
        print("   ✅ CONSISTENT - Strategy works across different market conditions")
    elif consistency_rate >= 60:
        print("   ⚠️  MODERATE - Some years underperform")
    else:
        print("   ❌ INCONSISTENT - Strategy may be overfit to specific market conditions")
    
    # Save results
    results_df.to_csv("period_stability_results.csv", index=False)
    logging.info("\n📁 Results saved: period_stability_results.csv")
    
    return results_df


def main():
    """Run complete overfitting detection suite"""
    logging.info("="*70)
    logging.info("🚀 OVERFITTING DETECTION SUITE")
    logging.info("="*70)
    
    # Load data
    df = load_data("XAUUSD", "H1", days_back=1825)  # ~5 years
    if df is None:
        logging.error("❌ Failed to load data")
        return
    
    # Run all tests
    logging.info("\n🧪 Running 3 overfitting detection tests...\n")
    
    # Test 1: Walk-Forward Analysis (most important)
    wf_results = walk_forward_analysis(df, n_splits=5)
    
    # Test 2: Parameter Robustness
    rob_results = robustness_test(df, {
        'donchian_period': 20,
        'sl_points': 150,
        'tp_points': 300
    })
    
    # Test 3: Period Stability
    period_results = period_stability_test(df, years_back=5)
    
    # Final summary
    print("\n" + "="*70)
    print("🎯 FINAL OVERFITTING ASSESSMENT")
    print("="*70)
    print("\n✅ All tests completed!")
    print("\n📁 Results saved:")
    print("   - walk_forward_results.csv")
    print("   - robustness_test_results.csv")
    print("   - period_stability_results.csv")
    print("\n💡 Next Steps:")
    print("   1. Review walk-forward degradation (should be < 20%)")
    print("   2. Check parameter robustness (CV should be < 30%)")
    print("   3. Verify period consistency (>80% profitable years)")
    print("\n⚠️  If overfitting detected:")
    print("   - Simplify strategy logic")
    print("   - Reduce number of parameters")
    print("   - Use broader parameter values")
    print("   - Add more filters (regime, news, session)")
    print("="*70)


if __name__ == "__main__":
    main()
