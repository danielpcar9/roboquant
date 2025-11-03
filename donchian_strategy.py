import time
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests
import math
from enum import Enum
from dataclasses import dataclass
from typing import Optional
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

# Load environment variables
load_dotenv()

# State machine for event detection
class TradingMode(Enum):
    NORMAL = "normal"
    EVENT_DETECTED = "event_detected"
    EVENT_WAIT = "event_wait"
    EVENT_ACTIVE = "event_active"
    EVENT_COOLDOWN = "event_cooldown"

@dataclass
class EventState:
    mode: TradingMode = TradingMode.NORMAL
    event_detected_at: Optional[datetime] = None
    candles_waited: int = 0
    last_event_trade_at: Optional[datetime] = None

# Global event state for persistence between loops
event_state = EventState()
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

# Event-driven trading parameters
EVENT_WAIT_CANDLES = 3
EVENT_SIZE_FACTOR = 0.25
EVENT_SL_ATR_MULTIPLIER = 2.5
EVENT_BREAKOUT_ATR_THRESHOLD = 0.3
EVENT_VOLUME_SPIKE_FACTOR = 1.7
MAX_SPREAD_POINTS = 50

# Set up logging with more detailed level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

def initialize_mt5():
    """Initialize MT5 connection"""
    # Add more detailed initialization info
    logging.info("Attempting to initialize MT5...")
    
    # Get credentials from environment
    login = os.getenv('MT5_LOGIN')
    password = os.getenv('MT5_PASSWORD')
    server = os.getenv('MT5_SERVER')
    
    # Initialize with credentials if available
    if login and password and server:
        try:
            login_int = int(login)
            logging.info(f"Initializing MT5 with credentials for account {login_int} on server {server}")
            # Log the password length and first character for debugging (but not the full password for security)
            logging.info(f"Password length: {len(password)}, First char: {password[0] if password else 'N/A'}")
            if not mt5.initialize(login=login_int, password=password, server=server):  # type: ignore
                logging.error("Failed to initialize MT5 with credentials")
                error = mt5.last_error()  # type: ignore
                logging.error(f"MT5 initialization error: {error}")
                return False
        except ValueError as e:
            logging.error(f"Invalid login format: {login}. Error: {e}")
            return False
    else:
        # Initialize without credentials
        logging.info("Initializing MT5 without credentials")
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

def get_current_spread(symbol):
    """Calculate current spread in points"""
    logging.debug(f"Calculating spread for {symbol}")
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error(f"Failed to get tick data for {symbol}")
        return None
    
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if symbol_info is None:
        logging.error(f"Failed to get symbol info for {symbol}")
        return None
    
    point = symbol_info.point
    spread_points = (tick.ask - tick.bid) / point if point > 0 else 0
    logging.debug(f"Spread for {symbol}: {spread_points:.2f} points")
    return spread_points

def calculate_atr(symbol, period=14):
    """Calculate Average True Range"""
    logging.debug(f"Calculating ATR for {symbol} with period {period}")
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, period + 1)  # type: ignore
    if rates is None or len(rates) < period + 1:
        logging.error(f"Failed to get rate data for ATR calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
        return None
    
    atr_values = []
    for i in range(1, len(rates)):
        tr1 = rates[i]['high'] - rates[i]['low']
        tr2 = abs(rates[i]['high'] - rates[i-1]['close'])
        tr3 = abs(rates[i]['low'] - rates[i-1]['close'])
        tr = max(tr1, tr2, tr3)
        atr_values.append(tr)
    
    atr = sum(atr_values) / len(atr_values) if atr_values else 0
    logging.debug(f"ATR for {symbol}: {atr:.5f}")
    return atr

def calculate_normalized_breakout(price, channel, atr):
    """Calculate normalized breakout distance (price-channel)/atr"""
    if atr is None or atr == 0:
        return 0
    distance = abs(price - channel)
    normalized = distance / atr
    return normalized

def get_volume_stats(symbol, lookback=20):
    """Get current volume vs average volume"""
    logging.debug(f"Calculating volume stats for {symbol} with lookback {lookback}")
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, lookback)  # type: ignore
    if rates is None or len(rates) < lookback:
        logging.error(f"Failed to get rate data for volume calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
        return None, None
    
    volumes = [rate['tick_volume'] for rate in rates]
    current_volume = volumes[-1] if volumes else 0
    avg_volume = sum(volumes) / len(volumes) if volumes else 0
    
    logging.debug(f"Volume stats for {symbol} - Current: {current_volume}, Average: {avg_volume:.2f}")
    return current_volume, avg_volume

def fetch_upcoming_high_impact(minutes_window=120):
    """Fetch upcoming high impact events from TradingEconomics API"""
    # This would require a TradingEconomics API key
    te_key = os.getenv('TRADINGECONOMICS_KEY')
    if not te_key:
        logging.debug("No TradingEconomics API key found, skipping event check")
        return []
    
    try:
        # This is a placeholder implementation - actual implementation would depend on TradingEconomics API
        logging.debug(f"Checking for high impact events in next {minutes_window} minutes")
        # In a real implementation, you would call the TradingEconomics API here
        return []
    except Exception as e:
        logging.error(f"Error fetching economic events: {e}")
        return []

def compute_lots_from_risk(balance, risk_pct, sl_distance, symbol):
    """Calculate lot size based on risk percentage and stop loss distance"""
    risk_amount = balance * (risk_pct / 100.0)
    
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if symbol_info is None:
        logging.error(f"Failed to get symbol info for {symbol}")
        return LOTS  # fallback to default
    
    # For XAU/USD, 1 lot = 100 oz troy, so point value is 100
    point_value = 100.0 if 'XAU' in symbol or 'GOLD' in symbol else 1.0
    point = symbol_info.point
    
    if point == 0 or sl_distance == 0:
        logging.warning(f"Invalid point or SL distance for {symbol}, using default lot size")
        return LOTS
    
    # Calculate lots: risk_amount / (sl_distance_points * point_value)
    sl_distance_points = sl_distance / point
    lots = risk_amount / (sl_distance_points * point_value)
    
    # Ensure minimum lot size
    min_lot = symbol_info.volume_min
    lots = max(lots, min_lot)
    
    # Ensure we don't exceed maximum lot size
    max_lot = symbol_info.volume_max or lots
    lots = min(lots, max_lot)
    
    # Normalize to broker requirements
    lots = normalize_volume(symbol, lots)
    
    logging.debug(f"Computed lots for {symbol}: {lots:.2f} (risk: {risk_amount:.2f}, SL: {sl_distance_points:.1f} points)")
    return lots

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

def handle_event_state(symbol):
    """Handle event state transitions"""
    global event_state
    
    current_time = datetime.now()
    
    if event_state.mode == TradingMode.NORMAL:
        # Check for high impact events
        events = fetch_upcoming_high_impact()
        if events:
            logging.info(f"High impact event detected: {len(events)} events upcoming")
            event_state.mode = TradingMode.EVENT_DETECTED
            event_state.event_detected_at = current_time
            return
    
    elif event_state.mode == TradingMode.EVENT_DETECTED:
        # Transition to wait mode
        event_state.mode = TradingMode.EVENT_WAIT
        event_state.candles_waited = 0
        return
    
    elif event_state.mode == TradingMode.EVENT_WAIT:
        # Count candles
        event_state.candles_waited += 1
        logging.debug(f"Event wait mode: {event_state.candles_waited}/{EVENT_WAIT_CANDLES} candles waited")
        
        if event_state.candles_waited >= EVENT_WAIT_CANDLES:
            event_state.mode = TradingMode.EVENT_ACTIVE
            logging.info("Event trading activated")
        return
    
    elif event_state.mode == TradingMode.EVENT_ACTIVE:
        # Check if we should exit event mode
        if event_state.last_event_trade_at:
            cooldown_period = timedelta(minutes=30)  # 30 minute cooldown
            if current_time - event_state.last_event_trade_at > cooldown_period:
                event_state.mode = TradingMode.EVENT_COOLDOWN
                logging.info("Entering event cooldown period")
        return
    
    elif event_state.mode == TradingMode.EVENT_COOLDOWN:
        # Cooldown for 1 hour after event trading
        cooldown_period = timedelta(hours=1)
        if event_state.last_event_trade_at and \
           current_time - event_state.last_event_trade_at > cooldown_period:
            event_state.mode = TradingMode.NORMAL
            event_state.event_detected_at = None
            event_state.candles_waited = 0
            event_state.last_event_trade_at = None
            logging.info("Returned to normal trading mode")
        return

def run_strategy(symbol="XAUUSD"):
    """Main strategy function"""
    global event_state
    
    logging.info(f"Running strategy for symbol: {symbol} in mode: {event_state.mode.value}")
    
    # Check if we're in trading hours
    if not in_trading_hours():
        logging.info("Outside trading hours")
        return
    
    # Check spread first
    spread = get_current_spread(symbol)
    if spread is None:
        logging.error("Failed to get current spread")
        return
    
    if spread > MAX_SPREAD_POINTS:
        logging.info(f"Spread too high: {spread:.2f} points > {MAX_SPREAD_POINTS} points, skipping")
        return
    
    # Handle event state transitions
    handle_event_state(symbol)
    
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
    
    # Calculate ATR for event-driven trading
    atr = calculate_atr(symbol)
    if atr is None:
        atr = 1.0  # fallback
    
    # Calculate momentum values
    current_momentum = calculate_avg_momentum(symbol, MOMENTUM_PERIOD)
    historical_momentum = calculate_avg_momentum(symbol, SAMPLE_PERIOD)
    
    logging.info(f"Momentum values - Current: {current_momentum}, Historical: {historical_momentum}")
    
    # Get volume stats for event detection
    current_volume, avg_volume = get_volume_stats(symbol)
    volume_spike = current_volume and avg_volume and current_volume > avg_volume * EVENT_VOLUME_SPIKE_FACTOR
    
    # Check for breakout conditions
    bullish_breakout = current_close > upper_channel
    bearish_breakout = current_close < lower_channel
    momentum_filter = current_momentum > historical_momentum
    
    # Calculate normalized breakouts for event mode
    normalized_bullish_breakout = calculate_normalized_breakout(current_close, upper_channel, atr)
    normalized_bearish_breakout = calculate_normalized_breakout(current_close, lower_channel, atr)
    
    # Event-driven trading logic
    if event_state.mode in [TradingMode.EVENT_ACTIVE, TradingMode.EVENT_WAIT]:
        # In event mode, use different criteria
        event_bullish = bullish_breakout and normalized_bullish_breakout > EVENT_BREAKOUT_ATR_THRESHOLD
        event_bearish = bearish_breakout and normalized_bearish_breakout > EVENT_BREAKOUT_ATR_THRESHOLD
        
        logging.info(f"Event mode breakout conditions - Bullish: {event_bullish}, Bearish: {event_bearish}, Volume spike: {volume_spike}")
        
        if (event_bullish or event_bearish) and volume_spike:
            # Event-driven trade
            order_type = "BUY" if event_bullish else "SELL"
            
            # Calculate dynamic lot size
            account_info = mt5.account_info()  # type: ignore
            if account_info:
                balance = account_info.balance
                # For events, risk 1.5% of account
                risk_pct = 1.5
                
                # Calculate SL based on ATR
                sl_distance = atr * EVENT_SL_ATR_MULTIPLIER
                
                # Calculate TP (2x SL for 2:1 ratio)
                tp_distance = sl_distance * 2
                
                # Calculate lot size
                lots = compute_lots_from_risk(balance, risk_pct, sl_distance, symbol)
                
                # Convert distances to points
                symbol_info = mt5.symbol_info(symbol)  # type: ignore
                if symbol_info:
                    point = symbol_info.point
                    sl_points = sl_distance / point if point > 0 else STOP_LOSS_POINTS
                    tp_points = tp_distance / point if point > 0 else TAKE_PROFIT_POINTS
                    
                    logging.info(f"Event-driven {order_type} trade detected")
                    success = execute_trade(symbol, order_type, lots, sl_points, tp_points)
                    if success:
                        logging.info(f"Event-driven {order_type} trade executed successfully")
                        event_state.last_event_trade_at = datetime.now()
                    else:
                        logging.error(f"Failed to execute event-driven {order_type} trade")
            else:
                logging.error("Failed to get account info for event-driven trade")
    else:
        # Normal trading logic
        logging.info(f"Normal breakout conditions - Bullish: {bullish_breakout}, Bearish: {bearish_breakout}, Momentum filter: {momentum_filter}")
        
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