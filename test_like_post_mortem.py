import pandas as pd
import tempfile
import os
from post_mortem import log_trade, analyze_recent_trades

# Create test data
trade_data = {
    'timestamp_open': '2025-11-04T22:57:12.055000',
    'timestamp_close': '2025-11-04T23:27:12.055000',
    'ticket': 123456,
    'symbol': 'XAUUSD',
    'side': 'BUY',
    'volume': 0.01,
    'entry_price': 1234.56,
    'exit_price': 1235.78,
    'sl': 1230.00,
    'tp': 1240.00,
    'pnl': 12.22,
    'pnl_pct': 0.99,
    'duration_minutes': 30,
    'reason_closed': 'TP reached'
}

# Create a temporary trades file for testing
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    temp_trades_file = f.name

print("Temp file:", temp_trades_file)

# Import post_mortem module
import post_mortem

# Store original file path
original_file = post_mortem.TRADES_FILE

try:
    # Temporarily override the TRADES_FILE path
    post_mortem.TRADES_FILE = temp_trades_file
    
    # Log the trade
    log_trade(trade_data)
    
    # Check file contents
    print("\nFile contents:")
    with open(temp_trades_file, 'r') as f:
        content = f.read()
        print(repr(content))
    
    # Read back with pandas
    df = pd.read_csv(temp_trades_file)
    print("\nRead back DataFrame:")
    print(df)
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist())
    print("PnL column exists:", 'pnl' in df.columns)
    if len(df) > 0:
        print("PnL value:", df['pnl'].iloc[0])
    
    # Analyze the trades
    metrics = analyze_recent_trades(n=10)
    print("\nMetrics:", metrics)
    
finally:
    # Restore original file path and clean up
    post_mortem.TRADES_FILE = original_file
    try:
        os.unlink(temp_trades_file)
    except:
        pass