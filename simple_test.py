import pandas as pd

# Test creating a DataFrame
df = pd.DataFrame([{'ticket': 123456, 'pnl': 12.22}])
print("Original DataFrame:")
print(df)
print("Columns:", df.columns.tolist())