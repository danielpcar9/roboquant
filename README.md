# RoboQuant - Donchian Breakout Strategy

This repository contains a Python implementation of a Donchian Breakout trading strategy for MetaTrader 5.

## Strategy Overview

The Donchian Breakout strategy is based on the classic trend-following system developed by Richard Donchian. This implementation includes additional filters based on momentum to reduce false breakouts.

### Key Features:
- Donchian Channel breakout detection
- Momentum filter to avoid trading in low volatility conditions
- Configurable trading hours
- Risk management with Stop Loss and Take Profit levels
- Integration with existing safety checks
- Webhook receiver for external signals
- Backtesting capabilities
- Performance dashboard

## Files

- [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py) - Main strategy implementation
- [webhook_receiver.py](file:///C:/Users/edgar/roboquant/webhook_receiver.py) - Webhook receiver for external signals
- [backtest_apex_vectorbt.py](file:///C:/Users/edgar/roboquant/backtest_apex_vectorbt.py) - Backtesting script using VectorBT
- [performance_dashboard.py](file:///C:/Users/edgar/roboquant/performance_dashboard.py) - Performance visualization dashboard
- [mt5_utils.py](file:///C:/Users/edgar/roboquant/mt5_utils.py) - Utility functions for MT5 interaction
- [safety.py](file:///C:/Users/edgar/roboquant/safety.py) - Safety checks module
- [alerts.py](file:///C:/Users/edgar/roboquant/alerts.py) - Alert notifications
- [run_donchian.bat](file:///C:/Users/edgar/roboquant/run_donchian.bat) - Batch file to run the strategy on Windows
- [run_webhook.bat](file:///C:/Users/edgar/roboquant/run_webhook.bat) - Batch file to run the webhook receiver
- [run_backtest.bat](file:///C:/Users/edgar/roboquant/run_backtest.bat) - Batch file to run backtesting
- [test_mt5_connection.py](file:///C:/Users/edgar/roboquant/test_mt5_connection.py) - Script to test MT5 connection

## Configuration

The strategy uses the following optimized parameters (can be adjusted in [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py)):

- Donchian Period: 50 (increased to reduce false signals)
- Momentum Period: 40
- Sample Period: 1000
- Lot Size: 0.01
- Stop Loss: 150 points (adjusted for gold volatility)
- Take Profit: 300 points (maintains 1:2 ratio)
- Timeframe: M5 (reduced noise, more reliable signals)
- Trading Hours: 13-22 (London and NY sessions)
- Magic Number: 234000

## Requirements

- MetaTrader 5
- Python 3.7+
- See [requirements.txt](file:///C:/Users/edgar/roboquant/requirements.txt) for complete list of dependencies

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install required packages:
   ```
   pip install -r requirements.txt
   ```
4. Configure your MT5 credentials in the [.env](file:///C:/Users/edgar/roboquant/.env) file
5. Set up webhook security by adding a strong secret key to [.env](file:///C:/Users/edgar/roboquant/.env):
   ```
   WEBHOOK_SECRET_KEY=your_very_long_random_secret_key_here
   ```

## Usage

### Running the Strategy
Run the strategy using the batch file:
```
run_donchian.bat
```

Or run directly with Python:
```
python donchian_strategy.py
```

### Webhook Receiver
To receive external trading signals:
```
run_webhook.bat
```

Or run directly:
```
python webhook_receiver.py
```

### Backtesting
To run backtesting:
```
run_backtest.bat
```

Or run directly:
```
python backtest_apex_vectorbt.py
```

### Performance Dashboard
To generate a performance dashboard:
```
python performance_dashboard.py
```

## Webhook Security

The webhook receiver implements HMAC authentication to prevent unauthorized trading signals:

### For Signal Senders:
```python
import hmac
import hashlib
import json
import requests

# Your secret key from .env
SECRET_KEY = "your_secret_key_here"

# Signal data
body = json.dumps({"symbol": "XAUUSD", "order_type": "BUY"})

# Calculate signature
signature = hmac.new(
    SECRET_KEY.encode(), 
    body.encode(), 
    hashlib.sha256
).hexdigest()

# Send request with signature
headers = {"X-Webhook-Signature": signature}
response = requests.post("http://your-server:5000/webhook", data=body, headers=headers)
```

## How It Works

1. The strategy calculates Donchian channels (highest high and lowest low over the specified period)
2. It calculates momentum as the average absolute price movement over two periods
3. When the current price breaks above the upper channel AND momentum is higher than historical average, it enters a long position
4. When the current price breaks below the lower channel AND momentum is higher than historical average, it enters a short position
5. Positions are managed with fixed stop loss and take profit levels

## Safety Features

This strategy integrates with the existing safety module which includes:
- Kill switch functionality
- Drawdown limits
- Daily loss limits
- Concurrent position limits
- Correlation checks

## Backtesting

The backtesting script uses VectorBT to simulate trading performance with proper exit conditions based on stop loss and take profit levels.

## Performance Monitoring

The performance dashboard generates interactive HTML visualizations including:
- Equity curve
- Drawdown analysis
- Win/loss distribution
- Hourly trading patterns
- Monthly performance
- Profit factor evolution

## Disclaimer

This is a educational example and should not be used for live trading without proper testing and risk management.