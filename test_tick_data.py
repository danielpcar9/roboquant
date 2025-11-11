import MetaTrader5 as mt5
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Initialize MT5
if not mt5.initialize():
    logging.error("Failed to initialize MT5")
    exit(1)

# Select symbol
symbol = "XAUUSD"
if not mt5.symbol_select(symbol, True):
    logging.error(f"Failed to select symbol {symbol}")
    mt5.shutdown()
    exit(1)

# Get symbol info
symbol_info = mt5.symbol_info(symbol)
if symbol_info:
    logging.info(f"Symbol info: {symbol_info}")
else:
    logging.error(f"Failed to get symbol info for {symbol}")

# Get tick data
tick = mt5.symbol_info_tick(symbol)
if tick:
    logging.info(f"Tick data: {tick}")
    logging.info(f"  Bid: {tick.bid}")
    logging.info(f"  Ask: {tick.ask}")
    logging.info(f"  Last: {tick.last}")
else:
    logging.error(f"Failed to get tick data for {symbol}")

# Shutdown MT5
mt5.shutdown()