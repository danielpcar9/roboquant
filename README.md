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

## Files

- [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py) - Main strategy implementation
- [run_donchian.bat](file:///C:/Users/edgar/roboquant/run_donchian.bat) - Batch file to run the strategy on Windows
- [test_mt5_connection.py](file:///C:/Users/edgar/roboquant/test_mt5_connection.py) - Script to test MT5 connection

## Configuration

The strategy uses the following parameters (can be adjusted in [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py)):

- Donchian Period: 20
- Momentum Period: 25
- Sample Period: 800
- Lot Size: 0.01
- Stop Loss: 50 points
- Take Profit: 100 points
- Magic Number: 234000
- Trading Hours: 0-23 (24-hour format)

## Requirements

- MetaTrader 5
- Python 3.7+
- MetaTrader 5 Python package
- python-dotenv

## Installation

1. Clone this repository
2. Install required packages:
   ```
   pip install MetaTrader5 python-dotenv
   ```
3. Configure your MT5 credentials in the [.env](file:///C:/Users/edgar/roboquant/.env) file

## Usage

Run the strategy using the batch file:
```
run_donchian.bat
```

Or run directly with Python:
```
python donchian_strategy.py
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

## Disclaimer

This is a educational example and should not be used for live trading without proper testing and risk management.