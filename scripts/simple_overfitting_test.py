"""
Simple Overfitting Test - Using actual strategy logic
Simplified to work with the real Donchian strategy
"""

import pandas as pd
import logging
from datetime import timedelta

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


def simple_backtest(df, donchian_period=20, initial_capital=10000):
    """
    Simplified backtest using pure Donchian breakout
    Matches the live strategy logic more closely
    """
    df = df.copy()

    # Calculate Donchian Channels
    df["donchian_upper"] = df["high"].rolling(window=donchian_period).max()
    df["donchian_lower"] = df["low"].rolling(window=donchian_period).min()

    # Simple signals: breakout only
    df["long_signal"] = df["close"] > df["donchian_upper"].shift(1)
    df["short_signal"] = df["close"] < df["donchian_lower"].shift(1)

    # Simulate trades
    position = 0  # 1 = long, -1 = short, 0 = flat
    entry_price = 0
    capital = initial_capital
    trades = []

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
            # Exit long on opposite signal or stop
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
            # Exit short on opposite signal or stop
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

    # Calculate metrics
    if len(trades) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "total_return": 0,
            "profit_factor": 0,
            "avg_win": 0,
            "avg_loss": 0,
        }

    trades_df = pd.DataFrame(trades)
    winning_trades = trades_df[trades_df["pnl"] > 0]
    losing_trades = trades_df[trades_df["pnl"] < 0]

    total_wins = winning_trades["pnl"].sum() if len(winning_trades) > 0 else 0
    total_losses = abs(losing_trades["pnl"].sum()) if len(losing_trades) > 0 else 0

    return {
        "total_trades": len(trades),
        "win_rate": len(winning_trades) / len(trades) * 100 if len(trades) > 0 else 0,
        "total_return": (capital - initial_capital) / initial_capital * 100,
        "profit_factor": total_wins / total_losses if total_losses > 0 else 0,
        "avg_win": winning_trades["pnl"].mean() if len(winning_trades) > 0 else 0,
        "avg_loss": losing_trades["pnl"].mean() if len(losing_trades) > 0 else 0,
        "final_capital": capital,
    }


def walk_forward_test(df, n_windows=5):
    """Walk-forward analysis"""
    logging.info("=" * 70)
    logging.info("Walk-Forward Analysis")
    logging.info("=" * 70)

    window_size = len(df) // n_windows
    results = []

    for i in range(n_windows):
        start = i * window_size
        end = min((i + 1) * window_size, len(df))

        window_df = df.iloc[start:end]

        # Split 70/30
        split_idx = int(len(window_df) * 0.7)
        is_df = window_df.iloc[:split_idx]
        oos_df = window_df.iloc[split_idx:]

        logging.info(
            f"\nWindow {i + 1}/{n_windows}: {window_df.index[0].strftime('%Y-%m')} to {window_df.index[-1].strftime('%Y-%m')}"
        )

        is_result = simple_backtest(is_df)
        oos_result = simple_backtest(oos_df)

        results.append(
            {
                "Window": i + 1,
                "Period": f"{window_df.index[0].strftime('%Y-%m')} - {window_df.index[-1].strftime('%Y-%m')}",
                "IS_Return": round(is_result["total_return"], 2),
                "OOS_Return": round(oos_result["total_return"], 2),
                "IS_Trades": is_result["total_trades"],
                "OOS_Trades": oos_result["total_trades"],
                "IS_WinRate": round(is_result["win_rate"], 1),
                "OOS_WinRate": round(oos_result["win_rate"], 1),
            }
        )

        logging.info(
            f"  IS:  Return={is_result['total_return']:.1f}%, Trades={is_result['total_trades']}, WinRate={is_result['win_rate']:.1f}%"
        )
        logging.info(
            f"  OOS: Return={oos_result['total_return']:.1f}%, Trades={oos_result['total_trades']}, WinRate={oos_result['win_rate']:.1f}%"
        )

    results_df = pd.DataFrame(results)

    # Calculate degradation
    results_df["Degradation_%"] = results_df.apply(
        lambda row: (
            (row["IS_Return"] - row["OOS_Return"]) / abs(row["IS_Return"]) * 100
        )
        if row["IS_Return"] != 0
        else 0,
        axis=1,
    )

    print("\n" + "=" * 70)
    print("WALK-FORWARD RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    avg_degradation = results_df["Degradation_%"].mean()
    print(f"\nAverage Degradation: {avg_degradation:.1f}%")

    if avg_degradation < 20:
        print("  GOOD: Low overfitting risk")
    elif avg_degradation < 40:
        print("  MODERATE: Some overfitting detected")
    else:
        print("  HIGH: Significant overfitting")

    results_df.to_csv("walk_forward_simple.csv", index=False)
    return results_df


def parameter_robustness_test(df):
    """Test parameter sensitivity"""
    logging.info("\n" + "=" * 70)
    logging.info("Parameter Robustness Test")
    logging.info("=" * 70)

    periods = [16, 18, 20, 22, 24]  # +/-20% around 20
    results = []

    for period in periods:
        logging.info(f"\nTesting Donchian Period = {period}")
        result = simple_backtest(df, donchian_period=period)

        results.append(
            {
                "Donchian_Period": period,
                "Total_Return_%": round(result["total_return"], 2),
                "Trades": result["total_trades"],
                "Win_Rate_%": round(result["win_rate"], 1),
                "Profit_Factor": round(result["profit_factor"], 2),
            }
        )

        logging.info(
            f"  Return={result['total_return']:.1f}%, Trades={result['total_trades']}, WinRate={result['win_rate']:.1f}%"
        )

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("ROBUSTNESS TEST RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    # Calculate coefficient of variation
    returns = results_df["Total_Return_%"]
    cv = (returns.std() / abs(returns.mean()) * 100) if returns.mean() != 0 else 999

    print(f"\nReturn Variability (CV): {cv:.1f}%")

    if cv < 30:
        print("  ROBUST: Strategy performs consistently across parameters")
    elif cv < 60:
        print("  MODERATE: Some parameter sensitivity")
    else:
        print("  FRAGILE: Highly dependent on specific parameters")

    results_df.to_csv("robustness_simple.csv", index=False)
    return results_df


def yearly_consistency_test(df):
    """Test year-by-year performance"""
    logging.info("\n" + "=" * 70)
    logging.info("Yearly Consistency Test")
    logging.info("=" * 70)

    results = []

    for year in range(2021, 2026):
        year_df = df[df.index.year == year]

        if len(year_df) < 100:
            continue

        logging.info(f"\nTesting Year {year}")
        result = simple_backtest(year_df)

        results.append(
            {
                "Year": year,
                "Total_Return_%": round(result["total_return"], 2),
                "Trades": result["total_trades"],
                "Win_Rate_%": round(result["win_rate"], 1),
                "Profit_Factor": round(result["profit_factor"], 2),
            }
        )

        logging.info(
            f"  Return={result['total_return']:.1f}%, Trades={result['total_trades']}, WinRate={result['win_rate']:.1f}%"
        )

    results_df = pd.DataFrame(results)

    print("\n" + "=" * 70)
    print("YEARLY CONSISTENCY RESULTS")
    print("=" * 70)
    print(results_df.to_string(index=False))
    print("=" * 70)

    profitable_years = len(results_df[results_df["Total_Return_%"] > 0])
    total_years = len(results_df)
    consistency = (profitable_years / total_years * 100) if total_years > 0 else 0

    print(f"\nProfitable Years: {profitable_years}/{total_years} ({consistency:.0f}%)")

    if consistency >= 80:
        print("  CONSISTENT: Strategy works across different market conditions")
    elif consistency >= 60:
        print("  MODERATE: Some years underperform")
    else:
        print("  INCONSISTENT: Strategy may be overfit to specific conditions")

    results_df.to_csv("yearly_consistency.csv", index=False)
    return results_df


def main():
    """Run all tests"""
    logging.info("=" * 70)
    logging.info("SIMPLE OVERFITTING DETECTION SUITE")
    logging.info("=" * 70)

    df = load_data()
    if df is None:
        return

    # Run tests
    print("\n\nTest 1: Walk-Forward Analysis")
    print("=" * 70)
    walk_forward_test(df)

    print("\n\nTest 2: Parameter Robustness")
    print("=" * 70)
    parameter_robustness_test(df)

    print("\n\nTest 3: Yearly Consistency")
    print("=" * 70)
    yearly_consistency_test(df)

    print("\n\n" + "=" * 70)
    print("FINAL ASSESSMENT")
    print("=" * 70)
    print("\nAll tests completed!")
    print("\nResults saved:")
    print("  - walk_forward_simple.csv")
    print("  - robustness_simple.csv")
    print("  - yearly_consistency.csv")
    print("=" * 70)


if __name__ == "__main__":
    main()
