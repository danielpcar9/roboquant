import logging
from datetime import datetime

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

# Configuration parameters (same as in donchian_strategy.py)
DONCHIAN_PERIOD = 20
MOMENTUM_PERIOD = 25
SAMPLE_PERIOD = 800

def in_trading_hours():
    """Check if current time is within trading hours"""
    current_hour = datetime.now().hour
    TRADING_HOUR_START = 0
    TRADING_HOUR_END = 23
    in_hours = TRADING_HOUR_START <= current_hour <= TRADING_HOUR_END
    logging.debug(f"Current hour: {current_hour}, Trading hours: {TRADING_HOUR_START}-{TRADING_HOUR_END}, In hours: {in_hours}")
    return in_hours

def get_donchian_channels(symbol, period):
    """Calculate Donchian channels"""
    logging.debug(f"Calculating Donchian channels for {symbol} with period {period}")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, period)  # type: ignore
    if rates is None or len(rates) < period:
        logging.error(f"Failed to get rate data for Donchian calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
        return None, None
    
    highs = [rate['high'] for rate in rates]
    lows = [rate['low'] for rate in rates]
    
    upper_channel = max(highs)
    lower_channel = min(lows)
    
    logging.debug(f"Calculated channels - Upper: {upper_channel}, Lower: {lower_channel}")
    return upper_channel, lower_channel

def calculate_avg_momentum(symbol, lookback):
    """Calculate average momentum over a lookback period"""
    logging.debug(f"Calculating momentum for {symbol} with lookback {lookback}")
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, lookback)  # type: ignore
    if rates is None or len(rates) < lookback:
        logging.error(f"Failed to get rate data for momentum calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
        return 0
    
    sum_momentum = 0
    for rate in rates:
        body = abs(rate['close'] - rate['open'])
        sum_momentum += body
    
    momentum = sum_momentum / lookback if lookback > 0 else 0
    logging.debug(f"Calculated momentum: {momentum}")
    return momentum

def test_strategy_conditions():
    """Test if strategy conditions are being met"""
    logging.info("Starting strategy conditions test")
    
    # Initialize MT5
    if not mt5.initialize():  # type: ignore
        logging.error("Failed to initialize MT5")
        return False
    
    logging.info("MT5 initialized successfully")
    
    # Select symbol
    symbol = "XAUUSD"
    if not mt5.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()  # type: ignore
        return False
    
    logging.info(f"Symbol {symbol} selected successfully")
    
    # Check trading hours
    if not in_trading_hours():
        logging.info("Outside trading hours")
        mt5.shutdown()  # type: ignore
        return False
    
    # Check existing positions
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    logging.debug(f"Current positions for {symbol}: {positions}")
    if positions is not None and len(positions) > 0:
        logging.info("Position already open, skipping")
        mt5.shutdown()  # type: ignore
        return False
    
    # Get Donchian channels
    upper_channel, lower_channel = get_donchian_channels(symbol, DONCHIAN_PERIOD)
    if upper_channel is None or lower_channel is None:
        logging.error("Failed to calculate Donchian channels")
        mt5.shutdown()  # type: ignore
        return False
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error("Failed to get current tick data")
        mt5.shutdown()  # type: ignore
        return False
    
    current_close = tick.last
    logging.info(f"Current close price: {current_close}")
    logging.info(f"Upper channel: {upper_channel}")
    logging.info(f"Lower channel: {lower_channel}")
    
    # Calculate momentum values
    current_momentum = calculate_avg_momentum(symbol, MOMENTUM_PERIOD)
    historical_momentum = calculate_avg_momentum(symbol, SAMPLE_PERIOD)
    
    logging.info(f"Current momentum: {current_momentum}")
    logging.info(f"Historical momentum: {historical_momentum}")
    
    # Check for breakout conditions
    bullish_breakout = current_close > upper_channel
    bearish_breakout = current_close < lower_channel
    momentum_filter = current_momentum > historical_momentum
    
    logging.info(f"Breakout conditions:")
    logging.info(f"  Current price > Upper channel: {bullish_breakout}")
    logging.info(f"  Current price < Lower channel: {bearish_breakout}")
    logging.info(f"  Current momentum > Historical momentum: {momentum_filter}")
    
    if bullish_breakout and momentum_filter:
        logging.info("BULLISH BREAKOUT CONDITION MET!")
    elif bearish_breakout and momentum_filter:
        logging.info("BEARISH BREAKOUT CONDITION MET!")
    else:
        logging.info("No breakout conditions met")
        
        # Show the gaps to help understand why conditions aren't met
        upper_gap = current_close - upper_channel
        lower_gap = lower_channel - current_close
        momentum_diff = current_momentum - historical_momentum
        
        logging.info(f"Gap analysis:")
        logging.info(f"  Gap to upper channel: {upper_gap}")
        logging.info(f"  Gap to lower channel: {lower_gap}")
        logging.info(f"  Momentum difference: {momentum_diff}")
    
    # Shutdown MT5
    mt5.shutdown()  # type: ignore
    logging.info("MT5 connection closed")
    return True

if __name__ == "__main__":
    test_strategy_conditions()