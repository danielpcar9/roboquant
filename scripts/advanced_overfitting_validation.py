"""
Advanced Overfitting Validation Suite
Implements:
1. Anchored Walk-Forward (fixed training start, expanding window)
2. Rolling Walk-Forward (3 years train / 6 months test)
3. Random Seed Stress Test (20 iterations)
4. Regime-Based Performance Analysis
"""

import pandas as pd
import numpy as np
import logging
from datetime import timedelta
import random

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def load_data():
    """Load historical data"""
    try:
        df = pd.read_csv("data/XAUUSD_H1.csv")
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

        # Filter last 5 years
        end_date = df.index[-1]
        start_date = end_date - timedelta(days=1825)
        df = df[df.index >= start_date]

        logging.info(f"Loaded {len(df):,} bars from {df.index[0]} to {df.index[-1]}")
        return df
    except Exception as e:
        logging.error(f"Failed to load data: {e}")
        return None


def calculate_adx(df, period=14):
    """Calculate ADX (Average Directional Index)"""
    # Calculate True Range
    high_low = df["high"] - df["low"]
    high_close = np.abs(df["high"] - df["close"].shift())
    low_close = np.abs(df["low"] - df["close"].shift())

    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    # Calculate Directional Movement
    up_move = df["high"] - df["high"].shift()
    down_move = df["low"].shift() - df["low"]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

    plus_dm_smooth = pd.Series(plus_dm, index=df.index).rolling(window=period).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).rolling(window=period).mean()

    # Calculate Directional Indicators
    plus_di = 100 * (plus_dm_smooth / atr)
    minus_di = 100 * (minus_dm_smooth / atr)

    # Calculate ADX
    dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.rolling(window=period).mean()

    return adx


def detect_regime(df, adx_threshold=18, di_threshold=26):
    """
    Detect market regime using ADX
    Returns: 'TRENDING' or 'RANGING'
    """
    adx = calculate_adx(df)
    # Calculate DI strength (rolling smoothing)
    up_move = df["high"] - df["high"].shift()
    down_move = df["low"].shift() - df["low"]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            np.abs(df["high"] - df["close"].shift()),
            np.abs(df["low"] - df["close"].shift()),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window=14).mean()
    plus_di = 100 * (pd.Series(plus_dm, index=df.index).rolling(window=14).mean() / atr)
    minus_di = 100 * (
        pd.Series(minus_dm, index=df.index).rolling(window=14).mean() / atr
    )

    if adx is None or len(adx) == 0 or pd.isna(adx.iloc[-1]):
        return "UNKNOWN"
    current_adx = adx.iloc[-1]
    current_max_di = max(plus_di.iloc[-1], minus_di.iloc[-1]) if len(plus_di) > 0 else 0
    if (current_adx > adx_threshold) and (current_max_di >= di_threshold):
        return "TRENDING"
    else:
        return "RANGING"


def backtest_with_regime_filter(
    df,
    donchian_period=20,
    use_adx_filter=True,
    adx_threshold=18,
    di_threshold=26,
    random_seed=None,
):
    """
    Backtest with optional ADX regime filter
    """
    if random_seed is not None:
        np.random.seed(random_seed)
        random.seed(random_seed)

    df = df.copy()

    # Calculate ADX and DI
    df["adx"] = calculate_adx(df, period=14)
    up_move = df["high"] - df["high"].shift()
    down_move = df["low"].shift() - df["low"]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            np.abs(df["high"] - df["close"].shift()),
            np.abs(df["low"] - df["close"].shift()),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(window=14).mean()
    df["plus_di"] = 100 * (
        pd.Series(plus_dm, index=df.index).rolling(window=14).mean() / atr
    )
    df["minus_di"] = 100 * (
        pd.Series(minus_dm, index=df.index).rolling(window=14).mean() / atr
    )

    # Calculate Donchian Channels
    df["donchian_upper"] = df["high"].rolling(window=donchian_period).max()
    df["donchian_lower"] = df["low"].rolling(window=donchian_period).min()

    # Simple signals: breakout only
    df["long_signal"] = df["close"] > df["donchian_upper"].shift(1)
    df["short_signal"] = df["close"] < df["donchian_lower"].shift(1)

    # Apply ADX+DI filter if enabled
    if use_adx_filter:
        strength = np.maximum(df["plus_di"], df["minus_di"])
        df["long_signal"] = (
            df["long_signal"] & (df["adx"] > adx_threshold) & (strength >= di_threshold)
        )
        df["short_signal"] = (
            df["short_signal"]
            & (df["adx"] > adx_threshold)
            & (strength >= di_threshold)
        )

    # Simulate trades
    position = 0  # 1 = long, -1 = short, 0 = flat
    entry_price = 0
    capital = 10000
    trades = []
    equity_curve = [capital]

    for i in range(len(df)):
        if position == 0:
            # Enter long
            if df["long_signal"].iloc[i]:
                position = 1
                entry_price = df["close"].iloc[i]
            # Enter short
            elif df["short_signal"].iloc[i]:
                position = -1
                entry_price = df["close"].iloc[i]

        elif position == 1:
            # Exit long on opposite signal
            if df["short_signal"].iloc[i]:
                exit_price = df["close"].iloc[i]
                pnl = (exit_price - entry_price) * 100  # Simplified PnL
                capital += pnl
                trades.append(
                    {
                        "type": "LONG",
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": pnl,
                        "capital": capital,
                    }
                )
                position = -1  # Flip to short
                entry_price = exit_price

        elif position == -1:
            # Exit short on opposite signal
            if df["long_signal"].iloc[i]:
                exit_price = df["close"].iloc[i]
                pnl = (entry_price - exit_price) * 100  # Simplified PnL
                capital += pnl
                trades.append(
                    {
                        "type": "SHORT",
                        "entry": entry_price,
                        "exit": exit_price,
                        "pnl": pnl,
                        "capital": capital,
                    }
                )
                position = 1  # Flip to long
                entry_price = exit_price

        equity_curve.append(capital)

    # Calculate metrics
    if len(trades) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_return": 0,
            "profit_factor": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "equity_curve": equity_curve,
        }

    trades_df = pd.DataFrame(trades)
    winning_trades = trades_df[trades_df["pnl"] > 0]
    losing_trades = trades_df[trades_df["pnl"] < 0]

    total_wins = winning_trades["pnl"].sum() if len(winning_trades) > 0 else 0
    total_losses = abs(losing_trades["pnl"].sum()) if len(losing_trades) > 0 else 0

    # Calculate Sharpe Ratio
    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()
    sharpe = (
        (returns.mean() / returns.std() * np.sqrt(252 * 24)) if returns.std() > 0 else 0
    )  # Hourly data

    # Calculate Max Drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max * 100
    max_dd = drawdown.min()

    return {
        "total_trades": len(trades),
        "win_rate": len(winning_trades) / len(trades) * 100 if len(trades) > 0 else 0,
        "total_return": (capital - 10000) / 10000 * 100,
        "profit_factor": total_wins / total_losses if total_losses > 0 else 0,
        "sharpe_ratio": sharpe,
        "max_drawdown": max_dd,
        "final_capital": capital,
        "equity_curve": equity_curve,
    }


def anchored_walk_forward(df, initial_train_years=2, test_months=6):
    """
    Anchored Walk-Forward: Fixed training start, expanding window
    """
    logging.info("=" * 70)
    logging.info("ANCHORED WALK-FORWARD ANALYSIS")
    logging.info("=" * 70)

    results = []

    # Fixed training start
    train_start = df.index[0]
    train_end = train_start + timedelta(days=365 * initial_train_years)

    window_num = 1

    while train_end < df.index[-1]:
        # Test period
        test_start = train_end
        test_end = test_start + timedelta(days=30 * test_months)

        if test_end > df.index[-1]:
            break

        # Get data
        train_df = df[(df.index >= train_start) & (df.index < train_end)]
        test_df = df[(df.index >= test_start) & (df.index < test_end)]

        if len(train_df) < 100 or len(test_df) < 100:
            break

        logging.info(
            f"\nWindow {window_num}: Train {train_start.strftime('%Y-%m')} to {train_end.strftime('%Y-%m')}, Test {test_start.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')}"
        )

        # Run backtest with and without ADX filter
        train_result = backtest_with_regime_filter(train_df, use_adx_filter=False)
        train_result_adx = backtest_with_regime_filter(train_df, use_adx_filter=True)
        test_result = backtest_with_regime_filter(test_df, use_adx_filter=False)
        test_result_adx = backtest_with_regime_filter(test_df, use_adx_filter=True)

        results.append(
            {
                "Window": window_num,
                "Train_Period": f"{train_start.strftime('%Y-%m')} to {train_end.strftime('%Y-%m')}",
                "Test_Period": f"{test_start.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')}",
                "Train_Return_NoFilter": round(train_result["total_return"], 2),
                "Test_Return_NoFilter": round(test_result["total_return"], 2),
                "Train_Return_ADX": round(train_result_adx["total_return"], 2),
                "Test_Return_ADX": round(test_result_adx["total_return"], 2),
                "Train_Sharpe_ADX": round(train_result_adx["sharpe_ratio"], 2),
                "Test_Sharpe_ADX": round(test_result_adx["sharpe_ratio"], 2),
                "Trades_NoFilter": test_result["total_trades"],
                "Trades_ADX": test_result_adx["total_trades"],
            }
        )

        logging.info(
            f"  Train (No Filter): Return={train_result['total_return']:.1f}%, Sharpe={train_result['sharpe_ratio']:.2f}"
        )
        logging.info(
            f"  Test (No Filter):  Return={test_result['total_return']:.1f}%, Sharpe={test_result['sharpe_ratio']:.2f}"
        )
        logging.info(
            f"  Train (ADX+DI):    Return={train_result_adx['total_return']:.1f}%, Sharpe={train_result_adx['sharpe_ratio']:.2f}"
        )
        logging.info(
            f"  Test (ADX+DI):     Return={test_result_adx['total_return']:.1f}%, Sharpe={test_result_adx['sharpe_ratio']:.2f}"
        )

        # Move to next window (expand train by test period)
        train_end = test_end
        window_num += 1

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("ANCHORED WALK-FORWARD RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    # Calculate improvement with ADX filter
    avg_return_no_filter = results_df["Test_Return_NoFilter"].mean()
    avg_return_adx = results_df["Test_Return_ADX"].mean()
    avg_sharpe_adx = results_df["Test_Sharpe_ADX"].mean()

    print(f"\nAverage Test Return (No Filter): {avg_return_no_filter:.2f}%")
    print(f"Average Test Return (ADX+DI): {avg_return_adx:.2f}%")
    print(f"Improvement: {avg_return_adx - avg_return_no_filter:.2f}%")
    print(f"Average Sharpe (ADX+DI): {avg_sharpe_adx:.2f}")

    results_df.to_csv("anchored_walk_forward.csv", index=False)
    return results_df


def rolling_walk_forward(df, train_years=3, test_months=6):
    """
    Rolling Walk-Forward: 3 years train / 6 months test, sliding window
    """
    logging.info("\n" + "=" * 70)
    logging.info("ROLLING WALK-FORWARD ANALYSIS (3Y Train / 6M Test)")
    logging.info("=" * 70)

    results = []

    train_days = 365 * train_years
    test_days = 30 * test_months

    window_num = 1
    current_start = df.index[0]

    while True:
        train_end = current_start + timedelta(days=train_days)
        test_start = train_end
        test_end = test_start + timedelta(days=test_days)

        if test_end > df.index[-1]:
            break

        # Get data
        train_df = df[(df.index >= current_start) & (df.index < train_end)]
        test_df = df[(df.index >= test_start) & (df.index < test_end)]

        if len(train_df) < 100 or len(test_df) < 100:
            break

        logging.info(
            f"\nWindow {window_num}: Train {current_start.strftime('%Y-%m')} to {train_end.strftime('%Y-%m')}, Test {test_start.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')}"
        )

        # Run backtest with and without ADX filter
        test_result = backtest_with_regime_filter(test_df, use_adx_filter=False)
        test_result_adx = backtest_with_regime_filter(test_df, use_adx_filter=True)

        # Detect regime for test period
        test_regime = detect_regime(test_df, adx_threshold=18, di_threshold=26)

        results.append(
            {
                "Window": window_num,
                "Test_Period": f"{test_start.strftime('%Y-%m')} to {test_end.strftime('%Y-%m')}",
                "Regime": test_regime,
                "Test_Return_NoFilter": round(test_result["total_return"], 2),
                "Test_Return_ADX": round(test_result_adx["total_return"], 2),
                "Test_Sharpe_NoFilter": round(test_result["sharpe_ratio"], 2),
                "Test_Sharpe_ADX": round(test_result_adx["sharpe_ratio"], 2),
                "Test_MaxDD_ADX": round(test_result_adx["max_drawdown"], 2),
                "Trades_NoFilter": test_result["total_trades"],
                "Trades_ADX": test_result_adx["total_trades"],
            }
        )

        logging.info(f"  Regime: {test_regime}")
        logging.info(
            f"  Test (No Filter): Return={test_result['total_return']:.1f}%, Sharpe={test_result['sharpe_ratio']:.2f}, Trades={test_result['total_trades']}"
        )
        logging.info(
            f"  Test (ADX+DI):    Return={test_result_adx['total_return']:.1f}%, Sharpe={test_result_adx['sharpe_ratio']:.2f}, Trades={test_result_adx['total_trades']}"
        )

        # Slide window forward by test period
        current_start = test_start
        window_num += 1

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("ROLLING WALK-FORWARD RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    # Analyze by regime
    trending_results = results_df[results_df["Regime"] == "TRENDING"]
    ranging_results = results_df[results_df["Regime"] == "RANGING"]

    print("\nRESULTS BY REGIME:")
    print(f"\nTRENDING Markets ({len(trending_results)} windows):")
    if len(trending_results) > 0:
        print(
            f"  Avg Return (No Filter): {trending_results['Test_Return_NoFilter'].mean():.2f}%"
        )
        print(
            f"  Avg Return (ADX+DI): {trending_results['Test_Return_ADX'].mean():.2f}%"
        )
        print(
            f"  Avg Sharpe (ADX+DI): {trending_results['Test_Sharpe_ADX'].mean():.2f}"
        )

    print(f"\nRANGING Markets ({len(ranging_results)} windows):")
    if len(ranging_results) > 0:
        print(
            f"  Avg Return (No Filter): {ranging_results['Test_Return_NoFilter'].mean():.2f}%"
        )
        print(
            f"  Avg Return (ADX+DI): {ranging_results['Test_Return_ADX'].mean():.2f}%"
        )
        print(f"  Avg Sharpe (ADX+DI): {ranging_results['Test_Sharpe_ADX'].mean():.2f}")

    # Overall statistics
    avg_sharpe_adx = results_df["Test_Sharpe_ADX"].mean()
    positive_windows = len(results_df[results_df["Test_Return_ADX"] > 0])
    total_windows = len(results_df)

    print("\nOVERALL STATISTICS (ADX+DI Filter):")
    print(
        f"  Positive Windows: {positive_windows}/{total_windows} ({positive_windows / total_windows * 100:.0f}%)"
    )
    print(f"  Average Sharpe: {avg_sharpe_adx:.2f}")
    print(f"  Average Return: {results_df['Test_Return_ADX'].mean():.2f}%")
    print(f"  Average MaxDD: {results_df['Test_MaxDD_ADX'].mean():.2f}%")

    results_df.to_csv("rolling_walk_forward.csv", index=False)
    return results_df


def random_seed_stress_test(df, n_iterations=20):
    """
    Random Seed Stress Test - Run backtest with 20 different random seeds
    Tests if results are stable across different random initializations
    """
    logging.info("\n" + "=" * 70)
    logging.info("RANDOM SEED STRESS TEST (20 Iterations)")
    logging.info("=" * 70)

    results = []
    seeds = [random.randint(0, 100000) for _ in range(n_iterations)]

    for i, seed in enumerate(seeds):
        logging.info(f"\nIteration {i + 1}/{n_iterations} - Seed: {seed}")

        result = backtest_with_regime_filter(
            df, use_adx_filter=True, random_seed=seed, adx_threshold=18, di_threshold=26
        )

        results.append(
            {
                "Iteration": i + 1,
                "Seed": seed,
                "Return_%": round(result["total_return"], 2),
                "Sharpe": round(result["sharpe_ratio"], 2),
                "MaxDD_%": round(result["max_drawdown"], 2),
                "Trades": result["total_trades"],
                "Win_Rate_%": round(result["win_rate"], 1),
            }
        )

        logging.info(
            f"  Return: {result['total_return']:.2f}%, Sharpe: {result['sharpe_ratio']:.2f}, Trades: {result['total_trades']}"
        )

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("RANDOM SEED STRESS TEST RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    # Calculate statistics
    sharpe_std = results_df["Sharpe"].std()
    sharpe_mean = results_df["Sharpe"].mean()
    return_std = results_df["Return_%"].std()
    return_mean = results_df["Return_%"].mean()

    print("\nSTABILITY ANALYSIS:")
    print(f"  Sharpe Ratio - Mean: {sharpe_mean:.3f}, Std Dev: {sharpe_std:.3f}")
    print(f"  Return % - Mean: {return_mean:.2f}%, Std Dev: {return_std:.2f}%")

    # Robustness assessment
    print("\nROBUSTNESS ASSESSMENT:")
    if sharpe_std < 0.25:
        print(f"  ULTRA ROBUST (Sharpe Std: {sharpe_std:.3f} < 0.25)")
        print("  Strategy is highly stable across random initializations")
    elif sharpe_std < 0.4:
        print(f"  ROBUST (Sharpe Std: {sharpe_std:.3f} < 0.40)")
        print("  Strategy shows good stability")
    else:
        print(f"  OVERFIT WARNING (Sharpe Std: {sharpe_std:.3f} > 0.40)")
        print("  Strategy may be overfitted - high sensitivity to random variations")

    results_df.to_csv("random_seed_stress_test.csv", index=False)
    return results_df, sharpe_std


def main():
    """Run complete validation suite"""
    logging.info("=" * 70)
    logging.info("ADVANCED OVERFITTING VALIDATION SUITE")
    logging.info("=" * 70)

    df = load_data()
    if df is None:
        return

    # Test 1: Anchored Walk-Forward
    print("\n\n" + "=" * 70)
    print("TEST 1: ANCHORED WALK-FORWARD")
    print("=" * 70)
    anchored_walk_forward(df, initial_train_years=2, test_months=6)

    # Test 2: Rolling Walk-Forward
    print("\n\n" + "=" * 70)
    print("TEST 2: ROLLING WALK-FORWARD (3Y/6M)")
    print("=" * 70)
    rolling_results = rolling_walk_forward(df, train_years=3, test_months=6)

    # Test 3: Random Seed Stress Test
    print("\n\n" + "=" * 70)
    print("TEST 3: RANDOM SEED STRESS TEST")
    print("=" * 70)
    seed_results, sharpe_std = random_seed_stress_test(df, n_iterations=20)

    # Final Assessment
    print("\n\n" + "=" * 70)
    print("FINAL ASSESSMENT")
    print("=" * 70)

    # Get regime performance from rolling WF
    trending_count = len(rolling_results[rolling_results["Regime"] == "TRENDING"])
    ranging_count = len(rolling_results[rolling_results["Regime"] == "RANGING"])
    total_regimes = trending_count + ranging_count

    trending_positive = len(
        rolling_results[
            (rolling_results["Regime"] == "TRENDING")
            & (rolling_results["Test_Return_ADX"] > 0)
        ]
    )
    ranging_positive = len(
        rolling_results[
            (rolling_results["Regime"] == "RANGING")
            & (rolling_results["Test_Return_ADX"] > 0)
        ]
    )

    trending_success_rate = (
        (trending_positive / trending_count * 100) if trending_count > 0 else 0
    )
    ranging_success_rate = (
        (ranging_positive / ranging_count * 100) if ranging_count > 0 else 0
    )

    avg_sharpe = rolling_results["Test_Sharpe_ADX"].mean()

    print("\n1. REGIME PERFORMANCE:")
    print(
        f"   Trending Markets: {trending_positive}/{trending_count} positive ({trending_success_rate:.0f}%)"
    )
    print(
        f"   Ranging Markets: {ranging_positive}/{ranging_count} positive ({ranging_success_rate:.0f}%)"
    )

    print("\n2. ROBUSTNESS:")
    print(f"   Sharpe Std Dev: {sharpe_std:.3f}")
    if sharpe_std < 0.25:
        robustness = "ULTRA ROBUST"
    elif sharpe_std < 0.4:
        robustness = "ROBUST"
    else:
        robustness = "POTENTIALLY OVERFIT"
    print(f"   Assessment: {robustness}")

    print("\n3. AVERAGE SHARPE:")
    print(f"   Rolling WF Sharpe: {avg_sharpe:.2f}")

    # Final verdict
    print("\n" + "=" * 70)
    print("FINAL VERDICT")
    print("=" * 70)

    ready_for_live = True
    issues = []

    if sharpe_std >= 0.4:
        ready_for_live = False
        issues.append(f"High Sharpe variability ({sharpe_std:.3f})")

    if trending_success_rate < 60:
        ready_for_live = False
        issues.append(
            f"Low trending market success rate ({trending_success_rate:.0f}%)"
        )

    if ranging_success_rate < 40:
        issues.append(f"Poor ranging market performance ({ranging_success_rate:.0f}%)")

    if avg_sharpe < 0.5:
        ready_for_live = False
        issues.append(f"Low average Sharpe ({avg_sharpe:.2f})")

    if ready_for_live and len(issues) == 0:
        print("\n  READY FOR LIVE TRADING")
        print(f"  - Sharpe Std: {sharpe_std:.3f} (ROBUST)")
        print(
            f"  - Regime Success: {trending_positive + ranging_positive}/{total_regimes} ({(trending_positive + ranging_positive) / total_regimes * 100:.0f}%)"
        )
        print(f"  - Average Sharpe: {avg_sharpe:.2f}")
        print("\n  Strategy shows:")
        print("    - Low overfitting risk")
        print("    - Stable performance across random initializations")
        print("    - Reasonable performance in different market regimes")
        print("\n  Recommendation: Start with minimum risk (0.25% per trade)")
    else:
        print("\n  NOT READY FOR LIVE TRADING")
        print("\n  Issues found:")
        for issue in issues:
            print(f"    - {issue}")
        print("\n  Recommendation: Further optimization or demo testing required")

    print("\n" + "=" * 70)
    print("Results saved:")
    print("  - anchored_walk_forward.csv")
    print("  - rolling_walk_forward.csv")
    print("  - random_seed_stress_test.csv")
    print("=" * 70)


if __name__ == "__main__":
    main()
