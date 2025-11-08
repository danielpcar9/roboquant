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

# Create a complete row with all columns, filling missing values with None
trade_dict = {'ticket': 123456, 'pnl': 12.22}
complete_row = []
for col in TRADE_COLUMNS:
    complete_row.append(trade_dict.get(col, None))

print("Complete row:", complete_row)
print("Length:", len(complete_row))

# Create DataFrame with proper column structure
df = pd.DataFrame(data=[complete_row], columns=pd.Index(TRADE_COLUMNS))

print("\nDataFrame:")
print(df)
print("\nColumns:", df.columns.tolist())
print("Shape:", df.shape)