import tempfile
import os
import pandas as pd
from post_mortem import log_trade, analyze_recent_trades

# Create test data
trade_data = {
    'ticket': 123456,
    'pnl': 12.22
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
    
    # Read with pandas to see what's happening
    print("\nReading with pandas:")
    df = pd.read_csv(temp_trades_file)
    print("DataFrame:")
    print(df)
    print("Columns:", df.columns.tolist())
    print("PnL column exists:", 'pnl' in df.columns)
    
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