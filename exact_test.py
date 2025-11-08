import pandas as pd
import tempfile
import os

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

# Create a temporary file path (but don't create the file yet)
temp_file = tempfile.mktemp(suffix='.csv')

print("Temp file:", temp_file)
print("File exists before:", os.path.exists(temp_file))

try:
    # Simulate the exact logic from post_mortem.py
    # Create a complete row with all columns, filling missing values with None
    complete_row = []
    for col in TRADE_COLUMNS:
        complete_row.append(trade_data.get(col, None))
    
    # Create DataFrame with proper column structure
    df = pd.DataFrame(data=[complete_row], columns=pd.Index(TRADE_COLUMNS))
    
    # Check if file exists to determine if we need to write headers
    file_exists = os.path.exists(temp_file)
    print("File exists:", file_exists)
    
    if not file_exists:
        # If file doesn't exist, create it with headers
        print("Writing with headers")
        df.to_csv(temp_file, index=False)
    else:
        # If file exists, append without headers
        print("Appending without headers")
        df.to_csv(temp_file, mode='a', header=False, index=False)
    
    # Check file contents
    print("\nFile contents:")
    with open(temp_file, 'r') as f:
        content = f.read()
        print(repr(content))
    
    # Read back with pandas
    df2 = pd.read_csv(temp_file)
    print("\nRead back DataFrame:")
    print(df2)
    print("Shape:", df2.shape)
    print("Columns:", df2.columns.tolist())
    print("PnL column exists:", 'pnl' in df2.columns)
    if len(df2) > 0:
        print("PnL value:", df2['pnl'].iloc[0])
    
finally:
    try:
        os.unlink(temp_file)
    except:
        pass