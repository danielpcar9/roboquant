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
    'ticket': 123456,
    'pnl': 12.22
}

# Create a complete row with all columns, filling missing values with None
complete_row = []
for col in TRADE_COLUMNS:
    complete_row.append(trade_data.get(col, None))

# Create a temporary file for testing
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    temp_file = f.name

print("Temp file:", temp_file)

try:
    # Create DataFrame with proper column structure
    df = pd.DataFrame(data=[complete_row], columns=pd.Index(TRADE_COLUMNS))
    
    print("DataFrame:")
    print(df)
    print("Columns:", df.columns.tolist())
    
    # Write to CSV with headers
    df.to_csv(temp_file, index=False)
    
    # Check file contents
    print("\nFile contents after first write:")
    with open(temp_file, 'r') as f:
        content = f.read()
        print(repr(content))
    
    # Read back with pandas
    df2 = pd.read_csv(temp_file)
    print("\nRead back DataFrame:")
    print(df2)
    print("Columns:", df2.columns.tolist())
    print("PnL column exists:", 'pnl' in df2.columns)
    
    # Now test appending
    print("\n--- Testing append ---")
    df.to_csv(temp_file, mode='a', header=False, index=False)
    
    # Check file contents after append
    print("\nFile contents after append:")
    with open(temp_file, 'r') as f:
        content = f.read()
        print(repr(content))
    
    # Read back with pandas
    df3 = pd.read_csv(temp_file)
    print("\nRead back DataFrame after append:")
    print(df3)
    print("Shape:", df3.shape)
    print("Columns:", df3.columns.tolist())
    print("PnL column exists:", 'pnl' in df3.columns)
    
finally:
    try:
        os.unlink(temp_file)
    except:
        pass