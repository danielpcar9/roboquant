"""
Improved Backtest with Dynamic ATR-Based Stops

This script implements a more robust backtesting approach that:
1. Uses dynamic ATR-based SL/TP instead of fixed points
2. Implements proper trend filtering
3. Avoids look-ahead bias
4. Provides realistic transaction cost modeling

Author: RoboQuant Team
Date: 2026-02-05
"""

import logging
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Import consolidated indicators
from indicators import TechnicalIndicators

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def load_data(filepath: str = "data/XAUUSD_H1.csv", years: int = 5) -> pd.DataFrame | None:
    """
    Load and prepare historical data.

    Args:
        filepath: Path to CSV file
        years: Number of years to load

    Returns:
        Prepared DataFrame or None if failed
    """
    try:
        df = pd.read_csv(filepath)
        df["time"] = pd.to_datetime(df["time"])
        df.set_index("time", inplace=True)
        df.sort_index(inplace=True)

        # Filter to requested years
        end_date = df.index[-1]
        start_date = end_date - timedelta(days=365 * years)
        df = df[df.index >= start_date]

        # Forward fill any missing data
        df = df.ffill()

        logging.info(f"Loaded {len(df):,} bars from {df.index[0]} to {df.index[-1]}")
        return df

    except Exception as e:
        logging.exception(f"Failed to load data: {e}")
        return None


def generate_signals(
    df: pd.DataFrame,
    donchian_period: int = 20,
    adx_threshold: float = 20.0,
    di_threshold: float = 20.0,
    require_trend: bool = True
) -> pd.DataFrame:
    """
    Generate trading signals with improved filtering.

    Args:
        df: Price DataFrame
        donchian_period: Donchian channel period
        adx_threshold: Minimum ADX for trend confirmation
        di_threshold: Minimum DI for directional strength
        require_trend: If True, only trade in trending markets

    Returns:
        DataFrame with signals added
    """
    df = df.copy()

    # Calculate Donchian Channels (shifted to avoid look-ahead)
    upper, lower, middle = TechnicalIndicators.calculate_donchian_channels(
        df, donchian_period, shift=True
    )
    df["dc_upper"] = upper
    df["dc_lower"] = lower
    df["dc_middle"] = middle

    # Calculate ADX and DI
    adx_data = TechnicalIndicators.calculate_adx(df, period=14)
    df["adx"] = adx_data["adx"]
    df["di_plus"] = adx_data["di_plus"]
    df["di_minus"] = adx_data["di_minus"]
    df["atr"] = adx_data["atr"]

    # Calculate additional momentum confirmation
    df["rsi"] = TechnicalIndicators.calculate_rsi(df["close"], period=14)

    # Generate base breakout signals
    df["long_breakout"] = df["close"] > df["dc_upper"]
    df["short_breakout"] = df["close"] < df["dc_lower"]

    # Trend filter condition
    if require_trend:
        # Strong trend: ADX > threshold AND DI in correct direction
        strong_uptrend = (
            (df["adx"] > adx_threshold) &
            (df["di_plus"] > df["di_minus"]) &
            (df["di_plus"] > di_threshold)
        )
        strong_downtrend = (
            (df["adx"] > adx_threshold) &
            (df["di_minus"] > df["di_plus"]) &
            (df["di_minus"] > di_threshold)
        )

        # Only take signals aligned with trend
        df["long_signal"] = df["long_breakout"] & strong_uptrend
        df["short_signal"] = df["short_breakout"] & strong_downtrend
    else:
        df["long_signal"] = df["long_breakout"]
        df["short_signal"] = df["short_breakout"]

    # Avoid overtrading: no signal if already in same direction
    # (This reduces consecutive signals)
    df["long_signal"] = df["long_signal"] & ~df["long_signal"].shift(1).fillna(False)
    df["short_signal"] = df["short_signal"] & ~df["short_signal"].shift(1).fillna(False)

    return df


def backtest_dynamic_stops(
    df: pd.DataFrame,
    atr_sl_multiplier: float = 2.0,
    atr_tp_multiplier: float = 4.0,
    initial_capital: float = 10000.0,
    risk_per_trade: float = 0.01,  # 1% risk per trade
    commission: float = 0.0002,  # 0.02% per side
    slippage: float = 0.0001,  # 0.01%
) -> dict:
    """
    Run backtest with dynamic ATR-based stops.

    Args:
        df: DataFrame with signals
        atr_sl_multiplier: ATR multiplier for stop loss
        atr_tp_multiplier: ATR multiplier for take profit
        initial_capital: Starting capital
        risk_per_trade: Fraction of capital to risk per trade
        commission: Commission per trade (fraction)
        slippage: Slippage per trade (fraction)

    Returns:
        Dictionary with backtest results
    """
    capital = initial_capital
    position = 0  # 1 = long, -1 = short, 0 = flat
    entry_price = 0.0
    stop_loss = 0.0
    take_profit = 0.0
    position_size = 0.0

    trades = []
    equity_curve = [capital]

    for i in range(len(df)):
        current_close = df["close"].iloc[i]
        current_atr = df["atr"].iloc[i] if not pd.isna(df["atr"].iloc[i]) else 0

        if position == 0:
            # Check for new entry signals
            if df["long_signal"].iloc[i] and current_atr > 0:
                position = 1
                entry_price = current_close * (1 + slippage)  # Slippage on entry

                # Dynamic stops based on ATR
                stop_loss = entry_price - (current_atr * atr_sl_multiplier)
                take_profit = entry_price + (current_atr * atr_tp_multiplier)

                # Position sizing based on risk
                risk_amount = capital * risk_per_trade
                sl_distance = entry_price - stop_loss
                position_size = risk_amount / sl_distance if sl_distance > 0 else 0

                # Apply commission
                capital -= entry_price * position_size * commission

            elif df["short_signal"].iloc[i] and current_atr > 0:
                position = -1
                entry_price = current_close * (1 - slippage)  # Slippage on entry

                # Dynamic stops based on ATR
                stop_loss = entry_price + (current_atr * atr_sl_multiplier)
                take_profit = entry_price - (current_atr * atr_tp_multiplier)

                # Position sizing based on risk
                risk_amount = capital * risk_per_trade
                sl_distance = stop_loss - entry_price
                position_size = risk_amount / sl_distance if sl_distance > 0 else 0

                # Apply commission
                capital -= entry_price * position_size * commission

        elif position == 1:  # In long position
            exit_price = 0
            exit_reason = ""

            # Check stop loss
            if df["low"].iloc[i] <= stop_loss:
                exit_price = stop_loss * (1 - slippage)
                exit_reason = "SL"
            # Check take profit
            elif df["high"].iloc[i] >= take_profit:
                exit_price = take_profit * (1 - slippage)
                exit_reason = "TP"
            # Check for reversal signal
            elif df["short_signal"].iloc[i]:
                exit_price = current_close * (1 - slippage)
                exit_reason = "REVERSE"

            if exit_price > 0:
                pnl = (exit_price - entry_price) * position_size
                capital += pnl
                capital -= exit_price * position_size * commission

                trades.append({
                    "type": "LONG",
                    "entry": entry_price,
                    "exit": exit_price,
                    "pnl": pnl,
                    "exit_reason": exit_reason,
                    "capital": capital
                })

                position = 0

        elif position == -1:  # In short position
            exit_price = 0
            exit_reason = ""

            # Check stop loss
            if df["high"].iloc[i] >= stop_loss:
                exit_price = stop_loss * (1 + slippage)
                exit_reason = "SL"
            # Check take profit
            elif df["low"].iloc[i] <= take_profit:
                exit_price = take_profit * (1 + slippage)
                exit_reason = "TP"
            # Check for reversal signal
            elif df["long_signal"].iloc[i]:
                exit_price = current_close * (1 + slippage)
                exit_reason = "REVERSE"

            if exit_price > 0:
                pnl = (entry_price - exit_price) * position_size
                capital += pnl
                capital -= exit_price * position_size * commission

                trades.append({
                    "type": "SHORT",
                    "entry": entry_price,
                    "exit": exit_price,
                    "pnl": pnl,
                    "exit_reason": exit_reason,
                    "capital": capital
                })

                position = 0

        equity_curve.append(capital)

    # Calculate metrics
    return calculate_metrics(trades, equity_curve, initial_capital)


def calculate_metrics(
    trades: list,
    equity_curve: list,
    initial_capital: float
) -> dict:
    """Calculate comprehensive backtest metrics."""

    if len(trades) == 0:
        return {
            "total_trades": 0,
            "win_rate": 0,
            "profit_factor": 0,
            "sharpe_ratio": 0,
            "max_drawdown": 0,
            "total_return": 0,
            "final_capital": initial_capital,
            "trades": [],
            "equity_curve": equity_curve
        }

    trades_df = pd.DataFrame(trades)

    # Basic stats
    winning = trades_df[trades_df["pnl"] > 0]
    losing = trades_df[trades_df["pnl"] < 0]

    total_wins = winning["pnl"].sum() if len(winning) > 0 else 0
    total_losses = abs(losing["pnl"].sum()) if len(losing) > 0 else 0

    win_rate = len(winning) / len(trades_df) * 100
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

    # Calculate Sharpe ratio
    equity_series = pd.Series(equity_curve)
    returns = equity_series.pct_change().dropna()
    sharpe = returns.mean() / returns.std() * np.sqrt(252 * 24) if returns.std() > 0 else 0

    # Calculate max drawdown
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max * 100
    max_dd = drawdown.min()

    # Return statistics
    final_capital = equity_curve[-1]
    total_return = (final_capital - initial_capital) / initial_capital * 100

    # Exit reason analysis
    exit_reasons = trades_df["exit_reason"].value_counts().to_dict()

    return {
        "total_trades": len(trades_df),
        "win_rate": round(win_rate, 2),
        "profit_factor": round(profit_factor, 3),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_dd, 2),
        "total_return": round(total_return, 2),
        "final_capital": round(final_capital, 2),
        "avg_win": round(winning["pnl"].mean(), 2) if len(winning) > 0 else 0,
        "avg_loss": round(losing["pnl"].mean(), 2) if len(losing) > 0 else 0,
        "largest_win": round(winning["pnl"].max(), 2) if len(winning) > 0 else 0,
        "largest_loss": round(losing["pnl"].min(), 2) if len(losing) > 0 else 0,
        "exit_reasons": exit_reasons,
        "trades": trades,
        "equity_curve": equity_curve
    }


def print_results(results: dict, title: str = "BACKTEST RESULTS") -> None:
    """Print formatted backtest results."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

    print(f"""
📊 TRADES
   Total Trades:       {results['total_trades']}
   Win Rate:           {results['win_rate']}%
   Profit Factor:      {results['profit_factor']}

💰 RETURNS
   Total Return:       {results['total_return']}%
   Final Capital:      ${results['final_capital']:,.2f}

📉 RISK METRICS
   Sharpe Ratio:       {results['sharpe_ratio']}
   Max Drawdown:       {results['max_drawdown']}%

📈 TRADE DETAILS
   Average Win:        ${results.get('avg_win', 0):,.2f}
   Average Loss:       ${results.get('avg_loss', 0):,.2f}
   Largest Win:        ${results.get('largest_win', 0):,.2f}
   Largest Loss:       ${results.get('largest_loss', 0):,.2f}

🎯 EXIT REASONS
""")

    for reason, count in results.get('exit_reasons', {}).items():
        percentage = count / results['total_trades'] * 100 if results['total_trades'] > 0 else 0
        print(f"   {reason}: {count} ({percentage:.1f}%)")

    print("=" * 70)

    # Verdict
    if results['sharpe_ratio'] >= 1.0 and results['win_rate'] >= 45 and results['max_drawdown'] >= -20:
        print("✅ VERDICT: Strategy meets production criteria")
    elif results['sharpe_ratio'] >= 0.5 and results['win_rate'] >= 40:
        print("🟡 VERDICT: Strategy shows promise but needs optimization")
    else:
        print("🔴 VERDICT: Strategy NOT ready for production")

    print("=" * 70)


def optimize_parameters(df: pd.DataFrame) -> dict:
    """
    Optimize strategy parameters using walk-forward approach.

    Returns:
        Best parameters found
    """
    print("\n" + "=" * 70)
    print("  PARAMETER OPTIMIZATION (Walk-Forward)")
    print("=" * 70)

    # Split data: 70% train, 30% test
    split_idx = int(len(df) * 0.7)
    train_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]

    print(f"Training period: {train_df.index[0]} to {train_df.index[-1]}")
    print(f"Testing period:  {test_df.index[0]} to {test_df.index[-1]}")

    # Parameter grid
    donchian_periods = [15, 20, 25, 30]
    atr_sl_multipliers = [1.5, 2.0, 2.5, 3.0]
    atr_tp_multipliers = [3.0, 4.0, 5.0, 6.0]
    adx_thresholds = [18, 22, 25, 30]

    best_params = {}
    best_sharpe = -100

    for dp in donchian_periods:
        for atr_sl in atr_sl_multipliers:
            for atr_tp in atr_tp_multipliers:
                for adx_t in adx_thresholds:
                    # Only test valid combinations
                    if atr_tp <= atr_sl:
                        continue

                    try:
                        signals_df = generate_signals(
                            train_df,
                            donchian_period=dp,
                            adx_threshold=adx_t
                        )

                        results = backtest_dynamic_stops(
                            signals_df,
                            atr_sl_multiplier=atr_sl,
                            atr_tp_multiplier=atr_tp
                        )

                        if results['sharpe_ratio'] > best_sharpe and results['total_trades'] >= 20:
                            best_sharpe = results['sharpe_ratio']
                            best_params = {
                                'donchian_period': dp,
                                'atr_sl_multiplier': atr_sl,
                                'atr_tp_multiplier': atr_tp,
                                'adx_threshold': adx_t,
                                'train_sharpe': results['sharpe_ratio'],
                                'train_return': results['total_return'],
                                'train_trades': results['total_trades']
                            }
                    except Exception:
                        continue

    if best_params:
        print("\n🎯 Best parameters found:")
        for k, v in best_params.items():
            print(f"   {k}: {v}")

        # Validate on test set
        print("\n📊 Validating on out-of-sample data...")

        signals_df = generate_signals(
            test_df,
            donchian_period=best_params['donchian_period'],
            adx_threshold=best_params['adx_threshold']
        )

        test_results = backtest_dynamic_stops(
            signals_df,
            atr_sl_multiplier=best_params['atr_sl_multiplier'],
            atr_tp_multiplier=best_params['atr_tp_multiplier']
        )

        print(f"\n   Test Sharpe:  {test_results['sharpe_ratio']}")
        print(f"   Test Return:  {test_results['total_return']}%")
        print(f"   Test Trades:  {test_results['total_trades']}")

        # Check for overfitting
        sharpe_diff = abs(best_params['train_sharpe'] - test_results['sharpe_ratio'])
        if sharpe_diff > 0.5:
            print("\n⚠️ WARNING: Significant performance degradation on test set")
            print("   This may indicate overfitting")
        else:
            print("\n✅ Performance stable across train/test split")

    print("=" * 70)
    return best_params


def main():
    """Main execution function."""
    print("=" * 70)
    print("  ROBOQUANT - IMPROVED BACKTEST WITH DYNAMIC STOPS")
    print("=" * 70)

    # Load data
    df = load_data()
    if df is None:
        return

    # Generate signals with improved filtering
    print("\n📊 Generating signals with trend filter...")
    signals_df = generate_signals(
        df,
        donchian_period=20,
        adx_threshold=22,
        di_threshold=20,
        require_trend=True
    )

    signal_count = signals_df["long_signal"].sum() + signals_df["short_signal"].sum()
    print(f"   Total signals generated: {signal_count}")

    # Run backtest with dynamic stops
    print("\n🔄 Running backtest with ATR-based dynamic stops...")
    results = backtest_dynamic_stops(
        signals_df,
        atr_sl_multiplier=2.0,
        atr_tp_multiplier=4.0,
        initial_capital=10000.0,
        risk_per_trade=0.01
    )

    # Print results
    print_results(results, "MAIN BACKTEST RESULTS")

    # Compare with no trend filter
    print("\n📊 Comparison: Without trend filter...")
    signals_no_filter = generate_signals(df, require_trend=False)
    results_no_filter = backtest_dynamic_stops(signals_no_filter)
    print_results(results_no_filter, "NO TREND FILTER")

    # Run optimization
    user_input = input("\n❓ Run parameter optimization? (y/n): ")
    if user_input.lower() == 'y':
        best_params = optimize_parameters(df)

        if best_params:
            # Save best parameters
            params_file = Path("optimized_params.json")
            import json
            with open(params_file, "w") as f:
                json.dump(best_params, f, indent=2)
            print(f"\n💾 Best parameters saved to {params_file}")

    print("\n✅ Backtest complete!")


if __name__ == "__main__":
    main()
