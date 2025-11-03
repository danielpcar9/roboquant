import time
import logging
from datetime import datetime
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore
from mt5_utils import build_and_send_order, normalize_volume
from safety import Safety

# Configuration parameters - OPTIMIZED VALUES
DONCHIAN_PERIOD = 50          # Increased to reduce false signals
MOMENTUM_PERIOD = 40
SAMPLE_PERIOD = 1000
LOTS = 0.01
STOP_LOSS_POINTS = 150        # CRITICAL: Adjusted to gold's volatility
TAKE_PROFIT_POINTS = 300      # Maintains 1:2 ratio
TIMEFRAME = mt5.TIMEFRAME_M5  # Reduced noise, more reliable signals
from datetime import timezone

TRADING_HOUR_START = 13  # GMT
TRADING_HOUR_END = 22    # GMT
MAGIC_NUMBER = 123456         # Magic number to identify bot trades

# Set up logging with more detailed level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

def initialize_mt5():
    """Initialize MT5 connection"""
    # Add more detailed initialization info
    logging.info("Attempting to initialize MT5...")
    if not mt5.initialize():  # type: ignore
        logging.error("Failed to initialize MT5")
        error = mt5.last_error()  # type: ignore
        logging.error(f"MT5 initialization error: {error}")
        return False
    logging.info("MT5 initialized successfully")
    return True

def in_trading_hours():
    """Check if current time is within trading hours (GMT)"""
    # Obtener hora UTC correctamente
    current_hour_utc = datetime.now(timezone.utc).hour
    current_hour_local = datetime.now().hour
    
    in_hours = TRADING_HOUR_START <= current_hour_utc <= TRADING_HOUR_END
    
    logging.debug(f"México: {current_hour_local}:00 | UTC: {current_hour_utc}:00 | Trading: {TRADING_HOUR_START}-{TRADING_HOUR_END} UTC | Active: {in_hours}")
    
    return in_hours

def get_donchian_channels(symbol, period):
    """Calculate Donchian channels"""
    logging.debug(f"Calculating Donchian channels for {symbol} with period {period}")
    # UPDATED: Use configurable timeframe
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, period)  # type: ignore
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
    # UPDATED: Use configurable timeframe
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, lookback)  # type: ignore
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

def get_current_price(symbol, order_type):
    """Get current price based on order type"""
    logging.debug(f"Getting current price for {symbol}, order type: {order_type}")
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error(f"Failed to get tick data for {symbol}")
        return None
    
    price = tick.ask if order_type == "BUY" else tick.bid
    logging.debug(f"Current price for {symbol}: {price}")
    return price

def execute_trade(symbol, order_type, lots, sl_points, tp_points):
    """Execute a trade with given parameters"""
    logging.info(f"Attempting to execute {order_type} trade for {symbol}")
    price = get_current_price(symbol, order_type)
    if price is None:
        logging.error("Failed to get current price")
        return False
    
    # Get symbol info for point value
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if symbol_info is None:
        logging.error(f"Failed to get symbol info for {symbol}")
        return False
        
    point = symbol_info.point
    logging.debug(f"Symbol point value: {point}")
    
    if order_type == "BUY":
        sl = price - sl_points * point
        tp = price + tp_points * point
    else:  # SELL
        sl = price + sl_points * point
        tp = price - tp_points * point
    
    logging.info(f"Trade parameters - Price: {price}, SL: {sl}, TP: {tp}, Volume: {lots}")
    
    try:
        # Normalize volume to ensure it meets broker requirements
        original_lots = lots
        lots = normalize_volume(symbol, lots)
        if lots != original_lots:
            logging.info(f"Volume normalized from {original_lots} to {lots}")
        
        logging.info(f"Calling build_and_send_order with parameters: symbol={symbol}, side={order_type}, volume={lots}, sl={sl}, tp={tp}")
        result = build_and_send_order(
            symbol=symbol,
            side=order_type,
            volume=lots,
            sl=sl,
            tp=tp,
            magic=MAGIC_NUMBER
        )
        
        if result:
            logging.info(f"{order_type} executed: Price={price:.5f} SL={sl:.5f} TP={tp:.5f}")
            logging.info(f"Order result: {result}")
            return True
        else:
            logging.error("Failed to execute trade - build_and_send_order returned None")
            return False
            
    except Exception as e:
        logging.error(f"Error executing trade: {e}", exc_info=True)
        return False

def run_strategy(symbol="XAUUSD"):
    """Main strategy function"""
    logging.info(f"Running strategy for symbol: {symbol}")
    
    # Check if we're in trading hours
    if not in_trading_hours():
        logging.info("Outside trading hours")
        return
    
    # Check if we already have open positions
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    logging.debug(f"Current positions for {symbol}: {positions}")
    if positions is not None and len(positions) > 0:
        logging.info("Position already open, skipping")
        return
    
    # Get Donchian channels
    upper_channel, lower_channel = get_donchian_channels(symbol, DONCHIAN_PERIOD)
    if upper_channel is None or lower_channel is None:
        logging.error("Failed to calculate Donchian channels")
        return
    
    # Get current price - FIXED: Use bid/ask instead of last
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error("Failed to get current tick data")
        return
    
    # Use bid price for analysis (more reliable than 'last')
    current_close = tick.bid
    logging.info(f"Current close price (bid): {current_close}")
    logging.info(f"Upper channel: {upper_channel}, Lower channel: {lower_channel}")
    
    # Calculate momentum values
    current_momentum = calculate_avg_momentum(symbol, MOMENTUM_PERIOD)
    historical_momentum = calculate_avg_momentum(symbol, SAMPLE_PERIOD)
    
    logging.info(f"Momentum values - Current: {current_momentum}, Historical: {historical_momentum}")
    
    # Check for breakout conditions
    bullish_breakout = current_close > upper_channel
    bearish_breakout = current_close < lower_channel
    momentum_filter = current_momentum > historical_momentum
    
    logging.info(f"Breakout conditions - Bullish: {bullish_breakout}, Bearish: {bearish_breakout}, Momentum filter: {momentum_filter}")
    
    if bullish_breakout and momentum_filter:
        # Bullish breakout
        logging.info("Bullish breakout detected")
        success = execute_trade(symbol, "BUY", LOTS, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS)
        if success:
            logging.info("BUY trade executed successfully")
        else:
            logging.error("Failed to execute BUY trade")
        
    elif bearish_breakout and momentum_filter:
        # Bearish breakout
        logging.info("Bearish breakout detected")
        success = execute_trade(symbol, "SELL", LOTS, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS)
        if success:
            logging.info("SELL trade executed successfully")
        else:
            logging.error("Failed to execute SELL trade")
    else:
        logging.info("No breakout conditions met")
        # Show gap analysis for debugging
        upper_gap = current_close - upper_channel
        lower_gap = lower_channel - current_close
        momentum_diff = current_momentum - historical_momentum
        logging.debug(f"Gap analysis - Upper gap: {upper_gap:.5f}, Lower gap: {lower_gap:.5f}, Momentum diff: {momentum_diff:.5f}")

def main():
    """Main function to run the strategy"""
    logging.info("Starting Donchian Breakout Strategy")
    
    # Initialize MT5
    if not initialize_mt5():
        return
    
    # Select symbol
    symbol = "XAUUSD"
    logging.info(f"Selecting symbol: {symbol}")
    if not mt5.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()  # type: ignore
        return
    
    # Initialize safety module
    safety = Safety(mt5_module=mt5)
    
    logging.info("Donchian Breakout Strategy started")
    logging.info(f"Parameters: Donchian Period={DONCHIAN_PERIOD}, Momentum Period={MOMENTUM_PERIOD}")
    
    try:
        # Run once immediately for testing
        logging.info("Running strategy immediately for testing...")
        
        # Check safety before running strategy
        ok, reason = safety.check_all(new_symbol=symbol)
        if not ok:
            logging.error(f"Safety check failed: {reason}")
            logging.info("Skipping strategy execution due to safety check failure")
        else:
            logging.info("Safety checks passed")
            run_strategy(symbol)
        
        # Then continue with the loop
        while True:
            # Run strategy
            # Check safety before running strategy
            ok, reason = safety.check_all(new_symbol=symbol)
            if not ok:
                logging.error(f"Safety check failed: {reason}")
                logging.info("Skipping strategy execution due to safety check failure")
            else:
                logging.info("Safety checks passed")
                run_strategy(symbol)
            
            # UPDATED: Sleep interval adjusted for M5 timeframe (300 seconds = 5 minutes)
            logging.debug("Waiting 300 seconds (5 minutes) before next check...")
            time.sleep(300)
            
    except KeyboardInterrupt:
        logging.info("Strategy stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        mt5.shutdown()  # type: ignore
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    main()