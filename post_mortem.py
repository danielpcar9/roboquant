# post_mortem.py
import os
import logging
import pandas as pd

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


def ensure_logs_dir():
    os.makedirs(os.path.join(os.path.dirname(__file__), 'logs'), exist_ok=True)


def log_trade(trade_dict):
    ensure_logs_dir()
    
    for col in TRADE_COLUMNS:
        if col not in trade_dict:
            trade_dict[col] = None
    
    df = pd.DataFrame([trade_dict])
    
    if not os.path.exists(TRADES_FILE):
        df[TRADE_COLUMNS].to_csv(TRADES_FILE, index=False)
    else:
        df[TRADE_COLUMNS].to_csv(TRADES_FILE, mode='a', header=False, index=False)
    
    logging.info("Trade %s registrado en %s", trade_dict.get('ticket'), TRADES_FILE)


def analyze_recent_trades(n=100):
    if not os.path.exists(TRADES_FILE):
        logging.warning("Archivo de trades no encontrado")
        return {}
    
    df = pd.read_csv(TRADES_FILE)
    
    if len(df) == 0:
        return {}
    
    recent = df.tail(n).copy()
    recent = recent[recent['pnl'].notna()]
    
    if len(recent) == 0:
        return {}
    
    winning = recent[recent['pnl'] > 0]
    losing = recent[recent['pnl'] < 0]
    
    win_rate = len(winning) / len(recent) if len(recent) > 0 else 0
    avg_win = winning['pnl'].mean() if len(winning) > 0 else 0
    avg_loss = abs(losing['pnl'].mean()) if len(losing) > 0 else 0
    
    profit_factor = (winning['pnl'].sum() / abs(losing['pnl'].sum())) \
                    if len(losing) > 0 and losing['pnl'].sum() != 0 else 0
    
    consecutive_losses = 0
    max_consecutive_losses = 0
    for pnl in recent['pnl']:
        if pnl < 0:
            consecutive_losses += 1
            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
        else:
            consecutive_losses = 0
    
    metrics = {
        'n_trades': len(recent),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': profit_factor,
        'max_consecutive_losses': max_consecutive_losses,
        'total_pnl': recent['pnl'].sum()
    }
    
    logging.info("POST-MORTEM: %d trades, Win Rate: %.1f%%, PnL: $%.2f", 
                 metrics['n_trades'], metrics['win_rate'] * 100, metrics['total_pnl'])
    
    return metrics