import os
import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Any, Optional

TRADE_COLUMNS = [
    'timestamp_open', 'timestamp_close', 'ticket', 'symbol',
    'side', 'volume', 'entry_price', 'exit_price',
    'sl', 'tp', 'pnl', 'pnl_pct', 'duration_minutes',
    'reason_closed',
    'donchian_upper', 'donchian_lower', 'atr', 'momentum',
    'spread_at_entry', 'hour_of_day', 'day_of_week',
    'balance_before', 'balance_after', 'mae', 'mfe',
    'expected_entry', 'actual_entry'
]

TRADES_FILE = os.path.join(os.path.dirname(__file__), 'logs', 'trades.csv')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def ensure_logs_dir():
    """Ensure the logs directory exists."""
    os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)

def log_trade(trade_dict: Dict[str, Any]) -> None:
    """
    Log a trade to the trades CSV file.
    
    Args:
        trade_dict: Dictionary containing trade information
    """
    ensure_logs_dir()
    
    # Create a complete row with all columns, filling missing values with None
    complete_row = []
    for col in TRADE_COLUMNS:
        complete_row.append(trade_dict.get(col, None))
    
    # Create DataFrame with proper column structure
    df = pd.DataFrame(data=[complete_row], columns=pd.Index(TRADE_COLUMNS))
    
    # Check if file exists to determine if we need to write headers
    file_exists = os.path.exists(TRADES_FILE)
    
    if not file_exists:
        # If file doesn't exist, create it with headers
        df.to_csv(TRADES_FILE, index=False)
    else:
        # If file exists, append without headers
        df.to_csv(TRADES_FILE, mode='a', header=False, index=False)
    
    logging.info("Trade %s registered in %s", trade_dict.get('ticket'), TRADES_FILE)

def analyze_recent_trades(n: int = 100) -> Dict[str, Any]:
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
        logging.error("Error reading trades file: %s", e)
        return {}
    
    if len(df) == 0:
        return {}
    
    # Check if required columns exist
    if 'pnl' not in df.columns:
        logging.warning("PnL column not found in trades file")
        return {}
    
    # Filter for recent trades with PnL data
    recent = df.tail(n).copy()
    recent = recent[recent['pnl'].notna()]
    
    if len(recent) == 0:
        return {}
    
    # Separate winning and losing trades
    winning = recent[recent['pnl'] > 0]
    losing = recent[recent['pnl'] < 0]
    
    # Calculate basic metrics
    win_rate = len(winning) / len(recent) if len(recent) > 0 else 0
    avg_win = winning['pnl'].mean() if len(winning) > 0 else 0
    avg_loss = abs(losing['pnl'].mean()) if len(losing) > 0 else 0
    
    # Calculate profit factor
    total_wins = winning['pnl'].sum() if len(winning) > 0 else 0
    total_losses = abs(losing['pnl'].sum()) if len(losing) > 0 else 0
    profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
    
    # Calculate maximum consecutive losses
    consecutive_losses = 0
    max_consecutive_losses = 0
    for pnl in recent['pnl']:
        if pnl < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0
    
    # Calculate additional metrics
    total_pnl = recent['pnl'].sum()
    avg_pnl = recent['pnl'].mean()
    std_pnl = recent['pnl'].std()
    
    # Sharpe ratio (assuming risk-free rate of 0)
    sharpe_ratio = avg_pnl / std_pnl if std_pnl > 0 else 0
    
    # Maximum drawdown
    if 'pnl' in recent.columns:
        cumulative_pnl = recent['pnl'].cumsum()
        # Convert to Series if it's not already
        if not isinstance(cumulative_pnl, pd.Series):
            cumulative_pnl = pd.Series(cumulative_pnl)
        running_max = cumulative_pnl.cummax()
        drawdown = cumulative_pnl - running_max
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0
    else:
        max_drawdown = 0
    
    # Sortino ratio (downside risk)
    negative_returns = recent[recent['pnl'] < 0]['pnl']
    downside_deviation = negative_returns.std() if len(negative_returns) > 0 else 0
    sortino_ratio = avg_pnl / downside_deviation if downside_deviation > 0 else 0
    
    # Calmar ratio
    calmar_ratio = abs(avg_pnl / max_drawdown) if max_drawdown < 0 else 0
    
    # Trade duration statistics
    avg_duration = recent['duration_minutes'].mean() if 'duration_minutes' in recent.columns else 0
    
    # Best and worst trades
    best_trade = recent['pnl'].max() if len(recent) > 0 else 0
    worst_trade = recent['pnl'].min() if len(recent) > 0 else 0
    
    # Time-based performance
    hourly_performance = recent.groupby('hour_of_day')['pnl'].mean() if 'hour_of_day' in recent.columns else pd.Series()
    best_hour = hourly_performance.idxmax() if len(hourly_performance) > 0 else None
    worst_hour = hourly_performance.idxmin() if len(hourly_performance) > 0 else None
    
    metrics = {
        'n_trades': len(recent),
        'wins': len(winning),
        'losses': len(losing),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_consecutive_losses': max_consecutive_losses,
        'total_pnl': total_pnl,
        'avg_pnl': avg_pnl,
        'std_pnl': std_pnl,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'sortino_ratio': sortino_ratio,
        'calmar_ratio': calmar_ratio,
        'avg_duration_minutes': avg_duration,
        'best_trade': best_trade,
        'worst_trade': worst_trade,
        'best_hour': best_hour,
        'worst_hour': worst_hour
    }
    
    logging.info("POST-MORTEM: %d trades, Win Rate: %.1f%%, PnL: $%.2f, Profit Factor: %.2f", 
                 metrics['n_trades'], metrics['win_rate'] * 100, metrics['total_pnl'], metrics['profit_factor'])
    
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
        with open(output_file, 'w') as f:
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
            f.write(f"Maximum Consecutive Losses: {metrics['max_consecutive_losses']}\n\n")
            
            f.write("TRADE CHARACTERISTICS\n")
            f.write("-" * 20 + "\n")
            f.write(f"Best Trade: ${metrics['best_trade']:.2f}\n")
            f.write(f"Worst Trade: ${metrics['worst_trade']:.2f}\n")
            f.write(f"Average Trade Duration: {metrics['avg_duration_minutes']:.1f} minutes\n")
            if metrics['best_hour'] is not None:
                f.write(f"Best Performing Hour: {int(metrics['best_hour'])}:00\n")
            if metrics['worst_hour'] is not None:
                f.write(f"Worst Performing Hour: {int(metrics['worst_hour'])}:00\n")
        
        logging.info("Performance report generated: %s", output_file)
        
    except Exception as e:
        logging.error("Error generating performance report: %s", e)