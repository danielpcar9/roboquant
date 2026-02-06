import logging
import os
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

# Try to import MT5, but make it optional to avoid issues in environments without MT5
try:
    from core.mt5_compat import mt5, MT5_AVAILABLE

    MT5_AVAILABLE = True
except ImportError:
    mt5 = None  # type: ignore
    MT5_AVAILABLE = False

TRADE_COLUMNS = [
    "timestamp_open",
    "timestamp_close",
    "ticket",
    "symbol",
    "side",
    "volume",
    "entry_price",
    "exit_price",
    "sl",
    "tp",
    "pnl",
    "pnl_pct",
    "duration_minutes",
    "reason_closed",
    "donchian_upper",
    "donchian_lower",
    "atr",
    "momentum",
    "spread_at_entry",
    "hour_of_day",
    "day_of_week",
    "balance_before",
    "balance_after",
    "mae",
    "mfe",
    "expected_entry",
    "actual_entry",
]

TRADES_FILE = os.path.join(os.path.dirname(__file__), "logs", "trades.csv")

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def ensure_logs_dir() -> None:
    """Ensure the logs directory exists."""
    os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)


def log_trade(trade_dict: dict[str, Any]) -> None:
    """
    Log a trade to the trades CSV file.

    Args:
        trade_dict: Dictionary containing trade information

    """
    ensure_logs_dir()

    # Create a complete row with all columns, filling missing values with None
    complete_row = []
    complete_row.extend(trade_dict.get(col) for col in TRADE_COLUMNS)
    # Create DataFrame with proper column structure
    df = pd.DataFrame(data=[complete_row], columns=pd.Index(TRADE_COLUMNS))

    if os.path.exists(TRADES_FILE):
        # If file exists, append without headers
        df.to_csv(TRADES_FILE, mode="a", header=False, index=False)

    else:
        # If file doesn't exist, create it with headers
        df.to_csv(TRADES_FILE, index=False)
    logging.info("Trade %s registered in %s", trade_dict.get("ticket"), TRADES_FILE)


def analyze_recent_trades(n: int = 100) -> dict[str, Any]:
    """
    Analyze recent trades and calculate performance metrics.

    Args:
        n: Number of recent trades to analyze

    Returns:
        Dictionary with performance metrics

    """
    if not os.path.exists(TRADES_FILE):
        logging.warning("Trades file not found: %s", TRADES_FILE)
        return {}

    try:
        df = pd.read_csv(TRADES_FILE)
    except Exception as e:
        logging.exception("Error reading trades file: %s", e)
        return {}

    if len(df) == 0:
        return {}

    # Check if required columns exist
    if "pnl" not in df.columns:
        logging.warning("PnL column not found in trades file")
        return {}

    # Filter for recent trades with PnL data
    recent = df.tail(n).copy()
    recent = recent[recent["pnl"].notna()]

    if len(recent) == 0:
        return {}

    # Separate winning and losing trades
    winning = recent[recent["pnl"] > 0]
    losing = recent[recent["pnl"] < 0]

    # Calculate basic metrics
    win_rate = len(winning) / len(recent) if len(recent) > 0 else 0
    avg_win = winning["pnl"].mean() if len(winning) > 0 else 0
    avg_loss = abs(losing["pnl"].mean()) if len(losing) > 0 else 0

    # Calculate profit factor
    total_wins = winning["pnl"].sum() if len(winning) > 0 else 0
    total_losses = abs(losing["pnl"].sum()) if len(losing) > 0 else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

    # Calculate maximum consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for pnl in recent["pnl"]:
        if pnl < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0

    # Calculate additional metrics
    total_pnl = recent["pnl"].sum()
    avg_pnl = recent["pnl"].mean()
    std_pnl = recent["pnl"].std()

    # Sharpe ratio (assuming risk-free rate of 0)
    sharpe_ratio = avg_pnl / std_pnl if std_pnl > 0 else 0

    # Maximum drawdown
    if "pnl" in recent.columns:
        cumulative_pnl = recent["pnl"].cumsum()
        # Convert to Series if it's not already
        if not isinstance(cumulative_pnl, pd.Series):
            cumulative_pnl = pd.Series(cumulative_pnl)
        running_max = cumulative_pnl.cummax()
        drawdown = cumulative_pnl - running_max
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
    else:
        max_drawdown = 0

    # Sortino ratio (downside risk)
    negative_returns = recent[recent["pnl"] < 0]["pnl"]
    downside_deviation = negative_returns.std() if len(negative_returns) > 0 else 0
    sortino_ratio = avg_pnl / downside_deviation if downside_deviation > 0 else 0

    # Calmar ratio
    calmar_ratio = abs(avg_pnl / max_drawdown) if max_drawdown < 0 else 0

    # Trade duration statistics
    avg_duration = (
        recent["duration_minutes"].mean() if "duration_minutes" in recent.columns else 0
    )

    # Best and worst trades
    best_trade = recent["pnl"].max() if len(recent) > 0 else 0
    worst_trade = recent["pnl"].min() if len(recent) > 0 else 0

    # Time-based performance
    hourly_performance = (
        recent.groupby("hour_of_day")["pnl"].mean()
        if "hour_of_day" in recent.columns
        else pd.Series(dtype=float)
    )
    best_hour = hourly_performance.idxmax() if len(hourly_performance) > 0 else None
    worst_hour = hourly_performance.idxmin() if len(hourly_performance) > 0 else None

    metrics = {
        "n_trades": len(recent),
        "wins": len(winning),
        "losses": len(losing),
        "win_rate": win_rate,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "max_consecutive_losses": max_consecutive_losses,
        "total_pnl": total_pnl,
        "avg_pnl": avg_pnl,
        "std_pnl": std_pnl,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
        "sortino_ratio": sortino_ratio,
        "calmar_ratio": calmar_ratio,
        "avg_duration_minutes": avg_duration,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "best_hour": best_hour,
        "worst_hour": worst_hour,
    }

    logging.info(
        "POST-MORTEM: %d trades, Win Rate: %.1f%%, PnL: $%.2f, Profit Factor: %.2f",
        metrics["n_trades"],
        float(str(metrics["win_rate"])) * 100,
        metrics["total_pnl"],
        metrics["profit_factor"],
    )

    return metrics


def generate_performance_report(output_file: str = "performance_report.txt") -> None:
    """
    Generate a detailed performance report.

    Args:
        output_file: Path to output file

    """
    metrics = analyze_recent_trades()

    if not metrics:
        logging.warning("No metrics available for performance report")
        return

    try:
        with open(output_file, "w") as f:
            f.write("ROBOQUANT PERFORMANCE REPORT\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("TRADE STATISTICS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total Trades: {metrics['n_trades']}\n")
            f.write(f"Winning Trades: {metrics['wins']}\n")
            f.write(f"Losing Trades: {metrics['losses']}\n")
            f.write(f"Win Rate: {metrics['win_rate'] * 100:.2f}%\n\n")

            f.write("PROFITABILITY METRICS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Total P&L: ${metrics['total_pnl']:.2f}\n")
            f.write(f"Average Win: ${metrics['avg_win']:.2f}\n")
            f.write(f"Average Loss: ${metrics['avg_loss']:.2f}\n")
            f.write(f"Profit Factor: {metrics['profit_factor']:.2f}\n")
            f.write(f"Average P&L per Trade: ${metrics['avg_pnl']:.2f}\n")
            f.write(f"P&L Standard Deviation: ${metrics['std_pnl']:.2f}\n\n")

            f.write("RISK METRICS\n")
            f.write("-" * 15 + "\n")
            f.write(f"Sharpe Ratio: {metrics['sharpe_ratio']:.2f}\n")
            f.write(f"Sortino Ratio: {metrics['sortino_ratio']:.2f}\n")
            f.write(f"Calmar Ratio: {metrics['calmar_ratio']:.2f}\n")
            f.write(f"Maximum Drawdown: ${metrics['max_drawdown']:.2f}\n")
            f.write(
                f"Maximum Consecutive Losses: {metrics['max_consecutive_losses']}\n\n",
            )

            f.write("TRADE CHARACTERISTICS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Best Trade: ${metrics['best_trade']:.2f}\n")
            f.write(f"Worst Trade: ${metrics['worst_trade']:.2f}\n")
            f.write(
                f"Average Trade Duration: {metrics['avg_duration_minutes']:.1f} minutes\n",
            )
            if metrics["best_hour"] is not None:
                f.write(f"Best Performing Hour: {int(metrics['best_hour'])}:00\n")
            if metrics["worst_hour"] is not None:
                f.write(f"Worst Performing Hour: {int(metrics['worst_hour'])}:00\n")

        logging.info("Performance report generated: %s", output_file)

    except Exception as e:
        logging.exception("Error generating performance report: %s", e)


def get_mt5_trade_history(days_back=30, magic_number=None, mt5_module=None):
    """
    Get closed trades from MT5 history

    Args:
        days_back: Number of days to look back
        magic_number: Filter by magic number (optional)
        mt5_module: MT5 module (for testing)

    Returns:
        List of trades with profit/loss

    """
    # Use provided MT5 module or global one
    mt5_to_use = mt5_module or mt5

    # Check if MT5 is available
    if not mt5_to_use or not MT5_AVAILABLE:
        logging.warning("MT5 not available for history analysis")
        return []

    # Get history for the specified period
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now()

    # Get deals from history
    deals = mt5_to_use.history_deals_get(from_date, to_date)

    if not deals or len(deals) == 0:
        logging.warning("No trade history found")
        return []

    # Convert to list and filter
    trades = []
    for deal in deals:
        # Filter by magic number if specified
        if magic_number and getattr(deal, "magic", None) != magic_number:
            continue

        # Only consider exit deals (not balance operations)
        if getattr(deal, "entry", None) == mt5_to_use.DEAL_ENTRY_OUT:
            trades.append(
                {
                    "time": datetime.fromtimestamp(deal.time),
                    "symbol": deal.symbol,
                    "profit": deal.profit,
                    "volume": deal.volume,
                    "type": "BUY" if deal.type == mt5_to_use.DEAL_TYPE_BUY else "SELL",
                },
            )

    return trades


def _calculate_gross_values_from_trades(trades):
    """
    Helper function to calculate gross profit and gross loss from trades.

    Args:
        trades: List of trades with profit field

    Returns:
        tuple: (gross_profit, gross_loss)
    """
    gross_profit = sum(t["profit"] for t in trades if t["profit"] > 0)
    gross_loss = abs(sum(t["profit"] for t in trades if t["profit"] < 0))
    return gross_profit, gross_loss


def calculate_profit_factor_from_trades(trades):
    """
    Calculate Profit Factor from trades
    Profit Factor = Gross Profit / Gross Loss

    Args:
        trades: List of trades with profit field

    Returns:
        float: Profit factor

    """
    if not trades:
        return 0.0

    gross_profit, gross_loss = _calculate_gross_values_from_trades(trades)

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def calculate_sharpe_ratio_from_trades(trades, risk_free_rate=0.02):
    """
    Calculate Sharpe Ratio from trades
    Sharpe Ratio = (Mean Return - Risk Free Rate) / Standard Deviation of Returns

    Args:
        trades: List of trades with profit field
        risk_free_rate: Annual risk-free rate (default 2%)

    Returns:
        float: Sharpe ratio (annualized)

    """
    if not trades or len(trades) < 2:
        return 0.0

    # Calculate returns
    returns = [t["profit"] for t in trades]

    # Calculate statistics
    mean_return = np.mean(returns)
    std_return = np.std(returns)

    if std_return == 0:
        return 0.0

    # Annualize (assuming daily trades, adjust if needed)
    trading_days = len(trades)
    annual_factor = np.sqrt(252 / trading_days) if trading_days > 0 else 1

    return (mean_return - risk_free_rate / 252) / std_return * annual_factor


def calculate_win_rate_from_trades(trades):
    """Calculate win rate percentage from trades"""
    if not trades:
        return 0.0

    winning_trades = sum(t["profit"] > 0 for t in trades)
    total_trades = len(trades)

    return (winning_trades / total_trades) * 100 if total_trades > 0 else 0.0


def _calculate_returns_statistics(returns):
    """
    Helper function to calculate basic statistics from returns.

    Args:
        returns: List of returns/profits

    Returns:
        tuple: (mean_return, std_return)
    """
    if not returns:
        return 0.0, 0.0

    mean_return = np.mean(returns)
    std_return = np.std(returns)
    return mean_return, std_return


def get_mt5_performance_report(days_back=30, magic_number=None, mt5_module=None):
    """
    Generate comprehensive performance report from MT5 history

    Args:
        days_back: Number of days to analyze
        magic_number: Filter by magic number (optional)
        mt5_module: MT5 module (for testing)

    Returns:
        dict: Performance metrics

    """
    trades = get_mt5_trade_history(days_back, magic_number, mt5_module)

    if not trades:
        return {
            "error": "No trades found in the specified period",
            "days_analyzed": days_back,
        }

    # Calculate all metrics
    profit_factor = calculate_profit_factor_from_trades(trades)
    sharpe_ratio = calculate_sharpe_ratio_from_trades(trades)
    win_rate = calculate_win_rate_from_trades(trades)

    # Calculate average win and loss
    wins = [t["profit"] for t in trades if t["profit"] > 0]
    losses = [t["profit"] for t in trades if t["profit"] < 0]
    avg_win = np.mean(wins) if wins else 0.0
    avg_loss = np.mean(losses) if losses else 0.0

    max_dd = 0

    # Calculate maximum drawdown
    if trades:
        # Sort trades by time
        sorted_trades = sorted(trades, key=lambda x: x["time"])

        # Calculate cumulative profit
        cumulative = []
        total = 0
        for trade in sorted_trades:
            total += trade["profit"]
            cumulative.append(total)

        # Calculate drawdown
        peak = cumulative[0] if cumulative else 0
        for value in cumulative:
            if value > peak:
                peak = value
            dd = peak - value
            if dd > max_dd:
                max_dd = dd
    # Total profit
    total_profit = sum(t["profit"] for t in trades)

    return {
        "period": f"Last {days_back} days",
        "total_trades": len(trades),
        "total_profit": round(total_profit, 2),
        "profit_factor": round(profit_factor, 2),
        "sharpe_ratio": round(sharpe_ratio, 2),
        "win_rate": round(win_rate, 2),
        "average_win": round(avg_win, 2),
        "average_loss": round(avg_loss, 2),
        "max_drawdown": round(max_dd, 2),
        "trades": trades,
    }


def rate_pf(pf: float) -> str:
    """Rate the profit factor."""
    if pf >= 2.0:
        return "EXCELLENT"
    if pf >= 1.5:
        return "GOOD"
    return "ACCEPTABLE" if pf >= 1.0 else "POOR"


def rate_sharpe(sr: float) -> str:
    """Rate the sharpe ratio."""
    if sr >= 3.0:
        return "EXCELLENT"
    if sr >= 2.0:
        return "VERY GOOD"
    return "GOOD" if sr >= 1.0 else "SUBOPTIMAL"


def _print_section_header(section_name: str) -> None:
    """Helper function to print section headers."""
    print(f"\n{section_name}:")


def print_trading_activity(report: dict[str, Any]) -> None:
    """Print trading activity section."""
    _print_section_header("TRADING ACTIVITY")
    print(f"  Total Trades: {report['total_trades']}")
    print(f"  Total Profit: ${report['total_profit']:.2f}")
    print(f"  Win Rate: {report['win_rate']:.2f}%")


def print_key_metrics(report):
    """Print key metrics section"""
    _print_section_header("KEY METRICS")
    pf_rating = rate_pf(report["profit_factor"])
    print(f"  Profit Factor: {report['profit_factor']:.2f} ({pf_rating})")

    sr_rating = rate_sharpe(report["sharpe_ratio"])
    print(f"  Sharpe Ratio: {report['sharpe_ratio']:.2f} ({sr_rating})")


def print_risk_metrics(report):
    """Print risk metrics section"""
    _print_section_header("RISK METRICS")
    print(f"  Max Drawdown: ${report['max_drawdown']:.2f}")
    print(f"  Average Win: ${report['average_win']:.2f}")
    print(f"  Average Loss: ${report['average_loss']:.2f}")

    if report["average_loss"] != 0:
        rr_ratio = abs(report["average_win"] / report["average_loss"])
        print(f"  Risk/Reward Ratio: 1:{rr_ratio:.2f}")


def print_mt5_performance_report(days_back=30, magic_number=None, mt5_module=None):
    """Print formatted performance report from MT5 history"""
    report = get_mt5_performance_report(days_back, magic_number, mt5_module)

    if "error" in report:
        print(f"\n{report['error']}")
        return

    print("\n" + "=" * 60)
    print(f"MT5 PERFORMANCE REPORT - {report['period']}")
    print("=" * 60)

    print_trading_activity(report)
    print_key_metrics(report)
    print_risk_metrics(report)

    print("=" * 60 + "\n")
