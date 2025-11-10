# Set File Manager Demo

## Overview
This demo shows how to use the Set File Manager to configure different trading strategies without modifying code.

## Available Configuration Sets

1. **ftmo_challenge.json** - For FTMO Challenge accounts
   - Risk: 0.75% per trade
   - Daily loss limit: -4%
   - Risk/Reward ratio: 2.0

2. **ftmo_verification.json** - For FTMO Verification accounts
   - Risk: 0.5% per trade
   - Daily loss limit: -4%
   - Risk/Reward ratio: 2.5

3. **conservative.json** - Conservative trading approach
   - Risk: 0.5% per trade
   - Daily loss limit: -2%
   - Risk/Reward ratio: 3.0

4. **aggressive.json** - Aggressive trading approach
   - Risk: 3% per trade
   - Daily loss limit: -8%
   - Risk/Reward ratio: 1.5
   - Max positions: 3

5. **default.json** - Default configuration
   - Risk: 1% per trade
   - Daily loss limit: -5%
   - Risk/Reward ratio: 2.0

## Usage

### Windows PowerShell:
```powershell
$env:ROBOQUANT_SET_FILE="aggressive.json"
python donchian_strategy.py
```

### Windows Command Prompt:
```cmd
set ROBOQUANT_SET_FILE=aggressive.json
python donchian_strategy.py
```

### Linux/Mac:
```bash
export ROBOQUANT_SET_FILE=aggressive.json
python donchian_strategy.py
```

## Creating Custom Sets

To create a custom configuration set:

1. Create a new JSON file in the `config/` directory
2. Follow the structure:
```json
{
  "risk_management": {
    "risk_per_trade_pct": 1.5
  },
  "strategy": {
    "donchian_period": 50
  },
  "trading_hours": {
    "start": 7,
    "end": 16
  },
  "position_limits": {
    "max_positions": 2
  },
  "performance": {
    "daily_loss_limit_pct": -3.0,
    "risk_reward_ratio": 2.2
  }
}
```

3. Use the filename with the ROBOQUANT_SET_FILE environment variable