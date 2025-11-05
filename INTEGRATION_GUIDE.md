# Integration Guide: New Services

## Overview

This guide explains how to integrate the new MT5ConnectionManager, DatabaseService, and logging system into your trading bot.

---

## 1. Centralized Logging

### Setup (One-time)

```python
from logging_config import get_logger

# Initialize logger once in your main module
logger = get_logger("RoboQuant")
```

### Usage

```python
# Instead of print() and logging.basicConfig()
logger.debug("Detailed information")
logger.info("General informational message")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)  # Include traceback
logger.critical("Critical failure")
```

### Output Locations

```
logs/
├── roboquant_20251105.log          # All logs (debug level)
└── roboquant_errors_20251105.log   # Errors only
```

---

## 2. MT5 Connection Manager

### Old Way (Duplicated Across Files)

```python
# In multiple files...
import metatrader5 as mt5
from security_manager import SecureCredentialManager

credential_manager = SecureCredentialManager()
login = credential_manager.get_credential('MT5_LOGIN')
password = credential_manager.get_credential('MT5_PASSWORD')
server = credential_manager.get_credential('MT5_SERVER')

if not mt5.initialize(login=int(login), password=password, server=server):
    print("Failed to initialize MT5")
    return False
```

### New Way (Centralized)

```python
from mt5_connection_manager import get_mt5_manager

# In your main function
manager = get_mt5_manager()

# Connect (singleton pattern - only connects once)
if not manager.connect():
    logger.error("Failed to connect to MT5")
    return False

# Select symbol
if not manager.select_symbol("XAUUSD"):
    logger.error("Failed to select symbol")
    return False

# Get MT5 module for direct access
mt5 = manager.get_mt5_module()

# Trades and operations...
positions = mt5.positions_get(symbol="XAUUSD")

# Automatic cleanup on exit (no manual shutdown needed)
```

### Benefits

- Single connection instance across entire application
- Automatic credential management
- Built-in error handling
- Proper resource cleanup

---

## 3. Database Service

### Setup

```python
from database_service import get_database_service, Trade, PerformanceMetrics

db = get_database_service()
```

### Saving Trades

```python
from database_service import Trade
from datetime import datetime

# When opening a trade
trade = Trade(
    timestamp_open=datetime.now(),
    symbol="XAUUSD",
    side="BUY",
    volume=0.01,
    entry_price=1234.56,
    sl=1230.00,
    tp=1240.00,
    ticket=12345
)

# Save to database
db.save_trade(trade)
```

### Updating Trade on Close

```python
# When closing a trade
db.update_trade_close(
    ticket=12345,
    exit_price=1235.78,
    pnl=12.22,  # In account currency
    pnl_pct=0.99,  # Percentage
    reason_closed="TP reached"
)
```

### Retrieving Trades

```python
# Get recent trades
trades = db.get_trades(symbol="XAUUSD", days=30, limit=100)

for trade in trades:
    print(f"Trade {trade['ticket']}: {trade['side']} @ {trade['entry_price']}")
```

### Saving Performance Metrics

```python
from database_service import PerformanceMetrics

metrics = PerformanceMetrics(
    period="daily",
    total_trades=15,
    win_rate=0.60,
    profit_factor=2.15,
    sharpe_ratio=1.85,
    max_drawdown=-3.2,
    total_pnl=1250.50
)

db.save_performance_metrics(metrics)
```

### Retrieving Performance Metrics

```python
# Get daily performance metrics
metrics = db.get_performance_metrics(period="daily", limit=30)

for metric in metrics:
    print(f"{metric['calculated_at']}: Win rate {metric['win_rate']}%")
```

---

## 4. Integration with Donchian Strategy

### Update imports

```python
# OLD
import metatrader5 as mt5
from security_manager import SecureCredentialManager
credential_manager = SecureCredentialManager()

# NEW
from mt5_connection_manager import get_mt5_manager
from database_service import get_database_service, Trade
from logging_config import get_logger

logger = get_logger("DonchianStrategy")
mt5_manager = get_mt5_manager()
db_service = get_database_service()
mt5 = mt5_manager.get_mt5_module()
```

### Update initialization

```python
# OLD
def initialize_mt5():
    login = credential_manager.get_credential('MT5_LOGIN')
    password = credential_manager.get_credential('MT5_PASSWORD')
    server = credential_manager.get_credential('MT5_SERVER')

    if not mt5.initialize(login=int(login), password=password, server=server):
        logging.error("Failed to initialize MT5")
        return False
    return True

# NEW
def initialize_mt5():
    if not mt5_manager.connect():
        logger.error("Failed to connect to MT5")
        return False

    if not mt5_manager.select_symbol("XAUUSD"):
        logger.error("Failed to select symbol")
        return False

    logger.info("MT5 initialized and symbol selected")
    return True
```

### Update main loop

```python
def main():
    logger = get_logger("RoboQuant")

    if not initialize_mt5():
        return

    try:
        while True:
            ok, reason = safety.check_all(new_symbol="XAUUSD")
            if not ok:
                logger.error(f"Safety check failed: {reason}")
                continue

            # Run strategy
            run_strategy("XAUUSD")

            # Save performance metrics every hour
            # ... metrics calculation code ...
            db_service.save_performance_metrics(metrics)

            time.sleep(300)

    except KeyboardInterrupt:
        logger.info("Strategy stopped by user")
    except Exception as e:
        logger.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        # No manual shutdown needed - manager handles it
        logger.info("Shutdown complete")
```

---

## 5. Migration Checklist

### For Existing Files

- [ ] `donchian_strategy.py`
  - [ ] Add `from mt5_connection_manager import get_mt5_manager`
  - [ ] Add `from database_service import get_database_service, Trade`
  - [ ] Add `from logging_config import get_logger`
  - [ ] Replace manual `mt5.initialize()` with `mt5_manager.connect()`
  - [ ] Add trade logging to database after execution

- [ ] `risk_orders.py`
  - [ ] Replace `from mt5_connection_manager` and `database_service`
  - [ ] Update `initialize_mt5()` function
  - [ ] Add trade persistence

- [ ] `post_mortem.py`
  - [ ] Integrate with `DatabaseService` for trade queries
  - [ ] Use database for performance metrics instead of CSV

- [ ] All test files
  - [ ] Use `get_logger()` instead of `print()`
  - [ ] Mock `mt5_manager` for isolated testing

### New Requirements

Add to `requirements.txt`:

```
supabase>=1.0.0
python-dotenv>=0.21.0
```

Install:
```bash
pip install -r requirements.txt
```

### Environment Configuration

Add to `.env`:

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key-here
```

### Database Setup

1. Create Supabase project: https://supabase.com
2. Create new project and get credentials
3. Apply migration via Supabase SQL editor:
   - Content in `supabase/migrations/20251105053124_create_trading_tables.sql`
   - Copy and paste into Supabase SQL editor
   - Execute

---

## 6. Error Handling

### Proper Error Handling Pattern

```python
from logging_config import get_logger

logger = get_logger("MyModule")

try:
    # Your code
    result = some_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}", exc_info=True)
    # Handle or re-raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise
```

### Database Error Handling

```python
# Database operations handle errors internally
# Returns False/None on failure, logs the error

if not db_service.save_trade(trade):
    logger.warning("Failed to save trade to database")
    # Continue anyway - trade still executed

trades = db_service.get_trades()  # Returns [] on error
```

---

## 7. Monitoring & Debugging

### Check Logs

```bash
# View real-time logs
tail -f logs/roboquant_20251105.log

# View errors only
tail -f logs/roboquant_errors_20251105.log

# Search for specific errors
grep "ERROR" logs/roboquant_*.log
```

### Verify Database Connection

```python
from database_service import get_database_service

db = get_database_service()

# If not initialized, this will log and return None
config = db.get_strategy_config("default")

if config:
    print("Database connected successfully")
else:
    print("Database not configured - check logs for details")
```

### Test MT5 Connection

```python
from mt5_connection_manager import get_mt5_manager

manager = get_mt5_manager()

if manager.connect():
    print("MT5 connected")
    if manager.select_symbol("XAUUSD"):
        print("Symbol selected successfully")
else:
    print("MT5 connection failed - check logs")
```

---

## 8. Common Integration Issues

### Issue: "Database service not initialized"

**Solution:** Verify `.env` has SUPABASE_URL and SUPABASE_ANON_KEY set

```bash
echo $SUPABASE_URL
echo $SUPABASE_ANON_KEY
```

### Issue: "MT5 not connected"

**Solution:** Use `get_mt5_manager().connect()` before operations

### Issue: "Trade not saved to database"

**Solution:** Check:
1. Supabase credentials in `.env`
2. Database tables created (run migration)
3. Check logs for specific database error

### Issue: Duplicate connections or memory leaks

**Solution:** Always use singleton pattern
- `get_mt5_manager()` - not `MT5ConnectionManager()`
- `get_database_service()` - not `DatabaseService()`

---

## 9. Performance Tips

- **Connection Manager**: Singleton pattern ensures single MT5 connection (efficient)
- **Database**: Batch inserts when possible for performance
- **Logging**: File handlers use rotation (automatic cleanup)
- **Memory**: Use `.maybeSingle()` for optional single row queries

---

## 10. Next Steps

1. Run tests to verify integration
```bash
python test_login.py
python test_mt5_connection.py
python test_security.py
```

2. Start with demo account
3. Monitor logs for any issues
4. Forward test for 3+ months

---

*For detailed API documentation, see inline code comments in:*
- `mt5_connection_manager.py`
- `database_service.py`
- `logging_config.py`
