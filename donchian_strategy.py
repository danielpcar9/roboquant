import time
import logging
from datetime import datetime
import metatrader5 as mt5
from mt5_utils import build_and_send_order, normalize_volume
from safety import Safety

# Configuration parameters
DONCHIAN_PERIOD = 20
MOMENTUM_PERIOD = 25
SAMPLE_PERIOD = 800
LOTS = 0.01
STOP_LOSS_POINTS = 50
TAKE_PROFIT_POINTS = 100
MAGIC_NUMBER = 234000
TRADING_HOUR_START = 0
TRADING_HOUR_END = 23

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def initialize_mt5():
    """Initialize MT5 connection"""
    if not mt5.initialize():
        logging.error("Failed to initialize MT5")
        return False
    logging.info("MT5 initialized successfully")
    return True

def in_trading_hours():
    """Check if current time is within trading hours"""
    current_hour = datetime.now().hour
    return TRADING_HOUR_START <= current_hour <= TRADING_HOUR_END

def get_donchian_channels(symbol, period):
    """Calculate Donchian channels"""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, period)
    if rates is None or len(rates) < period:
        logging.error("Failed to get rate data for Donchian calculation")
        return None, None
    
    highs = [rate['high'] for rate in rates]
    lows = [rate['low'] for rate in rates]
    
    upper_channel = max(highs)
    lower_channel = min(lows)
    
    return upper_channel, lower_channel

def calculate_avg_momentum(symbol, lookback):
    """Calculate average momentum over a lookback period"""
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 1, lookback)
    if rates is None or len(rates) < lookback:
        logging.error("Failed to get rate data for momentum calculation")
        return 0
    
    sum_momentum = 0
    for rate in rates:
        body = abs(rate['close'] - rate['open'])
        sum_momentum += body
    
    return sum_momentum / lookback if lookback > 0 else 0

def get_current_price(symbol, order_type):
    """Get current price based on order type"""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None
    
    if order_type == "BUY":
        return tick.ask
    else:
        return tick.bid

def execute_trade(symbol, order_type, lots, sl_points, tp_points):
    """Execute a trade with given parameters"""
    price = get_current_price(symbol, order_type)
    if price is None:
        logging.error("Failed to get current price")
        return False
    
    point = mt5.symbol_info(symbol).point
    
    if order_type == "BUY":
        sl = price - sl_points * point
        tp = price + tp_points * point
    else:  # SELL
        sl = price + sl_points * point
        tp = price - tp_points * point
    
    try:
        # Normalize volume to ensure it meets broker requirements
        lots = normalize_volume(symbol, lots)
        
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
            return True
        else:
            logging.error("Failed to execute trade")
            return False
            
    except Exception as e:
        logging.error(f"Error executing trade: {e}")
        return False

def run_strategy(symbol="XAUUSD"):
    """Main strategy function"""
    # Check if we're in trading hours
    if not in_trading_hours():
        logging.info("Outside trading hours")
        return
    
    # Check if we already have open positions
    positions = mt5.positions_get(symbol=symbol)
    if positions is not None and len(positions) > 0:
        logging.info("Position already open, skipping")
        return
    
    # Get Donchian channels
    upper_channel, lower_channel = get_donchian_channels(symbol, DONCHIAN_PERIOD)
    if upper_channel is None or lower_channel is None:
        logging.error("Failed to calculate Donchian channels")
        return
    
    # Get current price
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        logging.error("Failed to get current tick data")
        return
    
    current_close = tick.last
    
    # Calculate momentum values
    current_momentum = calculate_avg_momentum(symbol, MOMENTUM_PERIOD)
    historical_momentum = calculate_avg_momentum(symbol, SAMPLE_PERIOD)
    
    # Check for breakout conditions
    if current_close > upper_channel and current_momentum > historical_momentum:
        # Bullish breakout
        logging.info("Bullish breakout detected")
        execute_trade(symbol, "BUY", LOTS, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS)
        
    elif current_close < lower_channel and current_momentum > historical_momentum:
        # Bearish breakout
        logging.info("Bearish breakout detected")
        execute_trade(symbol, "SELL", LOTS, STOP_LOSS_POINTS, TAKE_PROFIT_POINTS)

def main():
    """Main function to run the strategy"""
    # Initialize MT5
    if not initialize_mt5():
        return
    
    # Select symbol
    symbol = "XAUUSD"
    if not mt5.symbol_select(symbol, True):
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()
        return
    
    logging.info("Donchian Breakout Strategy started")
    logging.info(f"Parameters: Donchian Period={DONCHIAN_PERIOD}, Momentum Period={MOMENTUM_PERIOD}")
    
    try:
        while True:
            # Run strategy
            run_strategy(symbol)
            
            # Wait before next check (60 seconds)
            time.sleep(60)
            
    except KeyboardInterrupt:
        logging.info("Strategy stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}")
    finally:
        mt5.shutdown()
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    main()