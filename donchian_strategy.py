import time
import logging
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# Import caching system

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore


from mt5_utils import build_and_send_order, normalize_volume, monitor_and_update_stops, place_pending_order, cancel_expired_pending_orders, update_trailing_stops
from safety import Safety
# Import security manager
from security_manager import SecureCredentialManager, InputValidator, sanitize_error_message, RateLimiter
# Import config manager
from config_manager import config_manager
# Import set file manager
from set_file_manager import get_set_manager
# Import error handler
from error_handler import handle_exception, retry_with_exponential_backoff, MT5ConnectionError, OrderExecutionError
# Import news filter
from news_filter import news_filter

# Import consolidated performance monitoring
from mt5_core import strategy_performance_monitor as performance_monitor

# Set up logging with more detailed level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables and initialize security manager
load_dotenv()
credential_manager = SecureCredentialManager()

# Configuration parameters - OPTIMIZED VALUES (now managed by config_manager)
DONCHIAN_PERIOD = config_manager.get('DONCHIAN_PERIOD')
MOMENTUM_PERIOD = config_manager.get('MOMENTUM_PERIOD')
SAMPLE_PERIOD = config_manager.get('SAMPLE_PERIOD')
RISK_PERCENT = config_manager.get('RISK_PERCENT')
USE_RISK_MANAGEMENT = config_manager.get('USE_RISK_MANAGEMENT')
LOTS = config_manager.get('LOTS')
STOP_LOSS_POINTS = config_manager.get('STOP_LOSS_POINTS')
TAKE_PROFIT_POINTS = config_manager.get('TAKE_PROFIT_POINTS')
TIMEFRAME_NAME = config_manager.get('TIMEFRAME')
BREAKOUT_THRESHOLD = config_manager.get('BREAKOUT_THRESHOLD')  # New breakout parameter

# Convert timeframe name to MT5 constant
TIMEFRAME_MAP = {
    'M1': mt5.TIMEFRAME_M1,
    'M5': mt5.TIMEFRAME_M5,
    'M15': mt5.TIMEFRAME_M15,
    'M30': mt5.TIMEFRAME_M30,
    'H1': mt5.TIMEFRAME_H1,
    'H4': mt5.TIMEFRAME_H4,
    'D1': mt5.TIMEFRAME_D1,
    'W1': mt5.TIMEFRAME_W1,
    'MN1': mt5.TIMEFRAME_MN1
}
TIMEFRAME = TIMEFRAME_MAP.get(TIMEFRAME_NAME.upper(), mt5.TIMEFRAME_M5)  # Default to M5

# Initialize with default values from config_manager
TRADING_HOUR_START = config_manager.get('TRADING_HOUR_START')
TRADING_HOUR_END = config_manager.get('TRADING_HOUR_END')
MAGIC_NUMBER = config_manager.get('MAGIC_NUMBER')

# Override with set file configuration if available
try:
    cfg = get_set_manager()
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    if set_file:
        try:
            cfg.load_set_file(set_file)
            logging.info(f"Loaded configuration set: {set_file}")
            
            # Risk management
            RISK_PERCENT = cfg.get('risk_management.risk_per_trade_pct', RISK_PERCENT)
            
            # Strategy parameters
            DONCHIAN_PERIOD = cfg.get('strategy.donchian_period', DONCHIAN_PERIOD)
            
            # Trading hours
            TRADING_HOUR_START = cfg.get('trading_hours.start', TRADING_HOUR_START)
            TRADING_HOUR_END = cfg.get('trading_hours.end', TRADING_HOUR_END)
            
            logging.info(f"Configuration overridden with set file values")
        except Exception as e:
            logging.warning(f"Failed to load configuration set {set_file}: {e}. Using default values.")
except Exception as e:
    logging.debug(f"No set file configuration loaded: {e}")

# Event-driven trading parameters
EVENT_SIZE_FACTOR = config_manager.get('EVENT_SIZE_FACTOR')
EVENT_SL_ATR_MULTIPLIER = config_manager.get('EVENT_SL_ATR_MULTIPLIER')
EVENT_BREAKOUT_ATR_THRESHOLD = config_manager.get('EVENT_BREAKOUT_ATR_THRESHOLD')
EVENT_VOLUME_SPIKE_FACTOR = config_manager.get('EVENT_VOLUME_SPIKE_FACTOR')  # Default 1.5, consider 1.2 for more signals
MAX_SPREAD_POINTS = config_manager.get('MAX_SPREAD_POINTS')

# Performance monitoring
STRATEGY_PERFORMANCE_MONITORING = True
strategy_execution_times = []

# Session tracking for breakout strategy
session_pending_orders = {}  # Track pending orders by session
last_session = None  # Track the last session

# Load news filter configuration
try:
    cfg = get_set_manager()
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    if set_file:
        cfg.load_set_file(set_file)
        news_filter.load_config(cfg.current_config)
except Exception as e:
    logging.warning(f"Failed to load news filter configuration: {e}")

# performance_monitor function removed - using consolidated version from mt5_core.py

@handle_exception
def initialize_mt5():
    """Initialize MT5 connection"""
    # Add more detailed initialization info
    logging.info("Attempting to initialize MT5...")
    
    # Get credentials from secure credential manager
    login = credential_manager.get_credential('MT5_LOGIN')
    password = credential_manager.get_credential('MT5_PASSWORD')
    server = credential_manager.get_credential('MT5_SERVER')
    
    # Initialize with credentials if available
    if login and password and server:
        try:
            login_int = int(login)
            logging.info(f"Initializing MT5 with credentials for account {login_int} on server {server}")
            if not mt5.initialize(login=login_int, password=password, server=server):  # type: ignore
                logging.error("Failed to initialize MT5 with credentials")
                error = mt5.last_error()  # type: ignore
                logging.error(f"MT5 initialization error: {error}")
                return False
        except ValueError as e:
            logging.error(f"Invalid login format: {login}. Error: {sanitize_error_message(str(e))}")
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

@handle_exception
def in_trading_hours():
    """Check if current time is within trading hours (GMT)"""
    # Obtener hora UTC correctamente
    current_hour_utc = datetime.now(timezone.utc).hour
    current_hour_local = datetime.now().hour
    
    in_hours = TRADING_HOUR_START <= current_hour_utc <= TRADING_HOUR_END
    
    logging.debug(f"México: {current_hour_local}:00 | UTC: {current_hour_utc}:00 | Trading: {TRADING_HOUR_START}-{TRADING_HOUR_END} UTC | Active: {in_hours}")
    
    return in_hours

@handle_exception
@performance_monitor
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

@handle_exception
@performance_monitor
def calculate_avg_momentum(symbol, lookback):
    """Calculate average momentum over a lookback period"""
    logging.debug(f"Calculating momentum for {symbol} with lookback {lookback}")
    # UPDATED: Use configurable timeframe
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, lookback)  # type: ignore  # type: ignore
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

@handle_exception
@performance_monitor
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


@handle_exception
@performance_monitor
def calculate_dynamic_stops(symbol, entry_price, order_type, atr):
    """
    Calculate dynamic SL/TP based on ATR and risk profile.
    
    Args:
        symbol: Trading symbol
        entry_price: Entry price
        order_type: "BUY" or "SELL"
        atr: Average True Range value
    
    Returns:
        tuple: (sl_price, tp_price)
    """
    # Get symbol info
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        logging.error(f"Failed to get symbol info for {symbol}")
        # Fallback to ATR-based values with default multipliers
        point = 0.01 if 'JPY' not in symbol else 0.001
        # For NASDAQ, adjust point value
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        # Use default ATR multipliers for fallback
        sl_multiplier = 3.0  # LOW RISK profile default
        tp_multiplier = 6.0  # LOW RISK profile default
        # Estimate ATR if we can't get it
        estimated_atr = 5.0  # Default ATR estimate
        sl_distance = sl_multiplier * estimated_atr
        tp_distance = tp_multiplier * estimated_atr
        
        if order_type == "BUY":
            sl_price = entry_price - (sl_distance * point)
            tp_price = entry_price + (tp_distance * point)
        else:
            sl_price = entry_price + (sl_distance * point)
            tp_price = entry_price - (tp_distance * point)
        return sl_price, tp_price
    
    point = symbol_info.point
    
    # Adjust point value for NASDAQ
    if 'NASDAQ' in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    
    # Determine if we're using LOW RISK (default) or HIGH RISK (aggressive) profile
    # Based on the risk_per_trade_pct in the current configuration
    risk_profile = "HIGH" if RISK_PERCENT > 1.0 else "LOW"
    
    # Get ATR multipliers from configuration
    cfg = get_set_manager()
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    
    try:
        if set_file:
            cfg.load_set_file(set_file)
            
        if risk_profile == "LOW":  # Default profile
            sl_multiplier = cfg.get('strategy.sl_atr_multiplier', 3.0)
            tp_multiplier = cfg.get('strategy.tp_atr_multiplier', 6.0)
        else:  # HIGH RISK (aggressive)
            sl_multiplier = cfg.get('strategy.sl_atr_multiplier', 2.0)
            tp_multiplier = cfg.get('strategy.tp_atr_multiplier', 1.5)
    except Exception as e:
        logging.warning(f"Failed to load ATR multipliers from config, using defaults: {e}")
        # Fallback to configuration-based defaults
        if risk_profile == "LOW":
            sl_multiplier = config_manager.get('SL_ATR_MULTIPLIER', 3.0)
            tp_multiplier = config_manager.get('TP_ATR_MULTIPLIER', 6.0)
        else:
            sl_multiplier = config_manager.get('SL_ATR_MULTIPLIER', 2.0)
            tp_multiplier = config_manager.get('TP_ATR_MULTIPLIER', 1.5)
    
    # Calculate SL/TP distances based on ATR multipliers
    sl_distance = sl_multiplier * atr
    tp_distance = tp_multiplier * atr
    
    sl_price = entry_price - sl_distance if order_type == "BUY" else entry_price + sl_distance
    tp_price = entry_price + tp_distance if order_type == "BUY" else entry_price - tp_distance
    
    logging.info(f"Dynamic stops calculated - Profile: {risk_profile}, SL: {sl_price:.5f}, TP: {tp_price:.5f}")
    return sl_price, tp_price

@handle_exception
@performance_monitor
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
    # Adjust point value for NASDAQ
    if 'NASDAQ' in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    spread_points = (tick.ask - tick.bid) / point if point > 0 else 0
    logging.debug(f"Spread for {symbol}: {spread_points:.2f} points")
    return spread_points

@handle_exception
@performance_monitor
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

@handle_exception
@performance_monitor
def calculate_normalized_breakout(price, channel, atr):
    """Calculate normalized breakout distance (price-channel)/atr"""
    if atr is None or atr == 0:
        return 0
    distance = abs(price - channel)
    normalized = distance / atr
    return normalized

@handle_exception
@performance_monitor
def get_volume_breakout(symbol, lookback=20):
    """Detect volume spike confirming breakout validity"""
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, lookback)  # type: ignore
    if rates is None or len(rates) < lookback:
        return False, 0
    
    volumes = [rate['tick_volume'] for rate in rates]
    current_vol = volumes[-1]
    avg_vol = sum(volumes[:-1]) / (len(volumes) - 1)
    
    # Volume spike = current > 1.5x average
    is_spike = current_vol > (avg_vol * 1.5)
    ratio = current_vol / avg_vol if avg_vol > 0 else 0
    
    return is_spike, ratio

@handle_exception
@performance_monitor
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


@handle_exception
@performance_monitor
def detect_engulfing(symbol):
    """Detect bullish and bearish engulfing patterns"""
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, 3)  # type: ignore
    if rates is None or len(rates) < 2:
        logging.error(f"Failed to get rate data for engulfing pattern detection. Rates: {rates}, Length: {len(rates) if rates else 0}")
        return False, False
    
    prev, current = rates[-2], rates[-1]
    
    # Envolvente alcista (bullish)
    bullish = (prev['close'] < prev['open'] and 
               current['close'] > current['open'] and
               current['open'] < prev['close'] and
               current['close'] > prev['open'])
    
    # Envolvente bajista (bearish)
    bearish = (prev['close'] > prev['open'] and
               current['close'] < current['open'] and
               current['open'] > prev['close'] and
               current['close'] < prev['open'])
    
    return bullish, bearish


@handle_exception
@performance_monitor
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
    
    # Calculate lots: risk_amount / (sl_distance * point_value)
    # For XAU/USD: sl_distance is already in price points, point_value is contract size (100 oz)
    # Risk per lot = sl_distance * point_value = points * ($ per point per lot)
    # So lots = risk_amount / (sl_distance * point_value)
    lots = risk_amount / (sl_distance * point_value)
    
    # Ensure minimum lot size
    min_lot = symbol_info.volume_min
    lots = max(lots, min_lot)
    
    # Ensure we don't exceed maximum lot size
    max_lot = symbol_info.volume_max or lots
    lots = min(lots, max_lot)
    
    # Normalize to broker requirements
    lots = normalize_volume(symbol, lots)
    
    logging.debug(f"Computed lots for {symbol}: {lots:.2f} (risk: {risk_amount:.2f}, SL: {sl_distance:.1f} points)")
    return lots

@handle_exception
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
@performance_monitor
def execute_trade(symbol, order_type, lots, sl_points, tp_points):
    """Execute a trade with given parameters"""
    # Validate inputs
    if not InputValidator.validate_symbol(symbol):
        logging.error(f"Invalid symbol: {symbol}")
        return False
        
    if not InputValidator.validate_order_type(order_type):
        logging.error(f"Invalid order type: {order_type}")
        return False
        
    if not InputValidator.validate_volume(lots):
        logging.error(f"Invalid volume: {lots}")
        return False
        
    if sl_points <= 0 or tp_points <= 0:
        logging.error(f"Invalid SL/TP points: SL={sl_points}, TP={tp_points}")
        return False
    
    logging.info(f"Attempting to execute {order_type} trade for {symbol}")
    price = get_current_price(symbol, order_type)
    if price is None:
        logging.error("Failed to get current price")
        return False
    
    # Validate price
    if not InputValidator.validate_price(price):
        logging.error(f"Invalid price: {price}")
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
    
    # Validate calculated prices
    if not InputValidator.validate_price(sl) or not InputValidator.validate_price(tp):
        logging.error(f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}")
        return False
    
    if USE_RISK_MANAGEMENT:
        account_info = mt5.account_info()  # type: ignore
        if account_info is None:
            logging.error("Failed to get account info")
            return False
        from mt5_utils import estimate_lots_by_risk
        calculated_lots = estimate_lots_by_risk(
            symbol=symbol,
            entry_price=price,
            stop_price=sl,
            risk_pct=RISK_PERCENT,
            mt5_module=mt5
        )
        logging.info(f"Risk: {RISK_PERCENT}% = ${account_info.balance * RISK_PERCENT / 100:.2f}, Lots: {calculated_lots}")
        lots = calculated_lots
    
    # Validate final volume
    if not InputValidator.validate_volume(lots):
        logging.error(f"Invalid final volume: {lots}")
        return False
    
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
        logging.error(f"Error executing trade: {sanitize_error_message(str(e))}", exc_info=True)
        return False



@handle_exception
@performance_monitor
def get_current_session():
    """
    Get current trading session based on UTC time
    
    Sessions:
    - Asia: 00:00-09:00 UTC
    - London: 08:00-17:00 UTC
    - New York: 13:00-22:00 UTC
    
    Returns:
        str: Current session name or None if no session
    """
    now = datetime.now(timezone.utc)
    current_hour = now.hour
    current_minute = now.minute
    
    # Convert to total minutes for easier comparison
    total_minutes = current_hour * 60 + current_minute
    
    # Define session time ranges in minutes (UTC)
    asia_start = 0 * 60      # 00:00 UTC
    asia_end = 9 * 60        # 09:00 UTC
    london_start = 8 * 60    # 08:00 UTC
    london_end = 17 * 60     # 17:00 UTC
    ny_start = 13 * 60       # 13:00 UTC
    ny_end = 22 * 60         # 22:00 UTC
    
    # Check which session we're in
    if asia_start <= total_minutes < asia_end:
        return "Asia"
    elif london_start <= total_minutes < london_end:
        return "London"
    elif ny_start <= total_minutes < ny_end:
        return "NewYork"
    else:
        return None  # Outside all sessions


@handle_exception
@performance_monitor
def get_session_high_low(symbol, session_name, days_back=1):
    """
    Get the high/low of the previous session with fallback mechanism
    
    Args:
        symbol: Trading symbol
        session_name: Session name ("Asia", "London", "NewYork")
        days_back: How many days back to look for session (default 1)
        
    Returns:
        tuple: (session_high, session_low) or (None, None) if failed
    """
    # Define session time ranges in UTC
    session_times = {
        "Asia": {"start_hour": 0, "end_hour": 9},
        "London": {"start_hour": 8, "end_hour": 17},
        "NewYork": {"start_hour": 13, "end_hour": 22}
    }
    
    if session_name not in session_times:
        logging.error(f"Unknown session: {session_name}")
        return None, None
    
    session_info = session_times[session_name]
    
    # Try up to 3 days back if initial lookup fails
    max_days_back = min(3, days_back + 2)  # Up to 3 days back total
    
    for days in range(days_back, max_days_back + 1):
        # Calculate the date for the session we want to analyze
        now = datetime.now(timezone.utc)
        target_date = now - timedelta(days=days)
        
        # Create datetime objects for session start and end
        session_start = target_date.replace(
            hour=session_info["start_hour"], 
            minute=0, 
            second=0, 
            microsecond=0
        )
        session_end = target_date.replace(
            hour=session_info["end_hour"], 
            minute=0, 
            second=0, 
            microsecond=0
        )
        
        # Convert to timestamps for MT5
        from_ts = int(session_start.timestamp())
        to_ts = int(session_end.timestamp())
        
        # Get rates for the session
        rates = mt5.copy_rates_range(symbol, TIMEFRAME, from_ts, to_ts)  # type: ignore
        if rates is not None and len(rates) > 0:
            # Calculate high and low
            session_high = max([rate['high'] for rate in rates])
            session_low = min([rate['low'] for rate in rates])
            
            logging.debug(f"{session_name} session {target_date.date()}: High={session_high:.5f}, Low={session_low:.5f}")
            return session_high, session_low
        else:
            logging.warning(f"Failed to get rate data for {session_name} session on {target_date.date()}, trying {days+1} days back")
    
    logging.error(f"Failed to get rate data for {session_name} session after trying up to {max_days_back} days back")
    return None, None


@handle_exception
@performance_monitor
def place_session_breakout_orders(symbol, session_name):
    """
    Place breakout orders based on previous session high/low
    
    Args:
        symbol: Trading symbol
        session_name: Session name ("Asia", "London", "NewYork")
    """
    global session_pending_orders
    
    # Get session high/low from previous day with fallback
    session_high, session_low = get_session_high_low(symbol, session_name, days_back=1)
    
    if session_high is None or session_low is None:
        logging.warning(f"Failed to get {session_name} session high/low, skipping breakout orders")
        return False
    
    # Check existing positions to avoid placing opposite orders
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    logging.info(f"Checking positions for {symbol} - Found {len(positions) if positions else 0} positions")
    if positions:
        # Count positions by direction
        buy_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_BUY)  # type: ignore
        sell_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_SELL)  # type: ignore
        
        logging.info(f"Existing positions - BUY: {buy_positions}, SELL: {sell_positions}")
        
        # If we have positions in both directions, don't place any new orders
        if buy_positions > 0 and sell_positions > 0:
            logging.info("Both BUY and SELL positions exist, skipping session breakout orders to avoid conflict")
            return False
        
        # If we have a BUY position, don't place a SELL order
        if buy_positions > 0:
            logging.info("BUY position exists, will only place BUY_STOP order for session breakout")
            place_sell_order = False
        else:
            place_sell_order = True
            
        # If we have a SELL position, don't place a BUY order
        if sell_positions > 0:
            logging.info("SELL position exists, will only place SELL_STOP order for session breakout")
            place_buy_order = False
        else:
            place_buy_order = True
        
        logging.info(f"Order placement flags - BUY: {place_buy_order}, SELL: {place_sell_order}")
    else:
        # No existing positions, place both orders
        place_buy_order = True
        place_sell_order = True
        logging.info("No existing positions, will place both BUY_STOP and SELL_STOP orders")
    
    # Get symbol info for point value
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        logging.error(f"Failed to get symbol info for {symbol}")
        return False
    
    point = symbol_info.point
    
    # Adjust point value for NASDAQ
    if 'NASDAQ' in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    
    # Calculate dynamic SL/TP using ATR
    atr = calculate_atr(symbol, 14)
    if atr is None:
        atr = 5.0  # Default fallback
    
    # Calculate pending order prices (closer distance based on ATR to avoid error 10015)
    # For XAU/USD, 1 pip = 0.1 points, so 10 pips = 1 point
    pip_value = point * 10  # Standard pip calculation
    # Use distance based on ATR (more conservative) to keep orders closer to market price
    breakout_distance = min(10 * pip_value, atr * 0.5)
    
    # Get current market price to ensure orders are placed at valid distances
    current_tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if current_tick is None:
        logging.error(f"Failed to get current tick data for {symbol}")
        return False
    
    current_ask = current_tick.ask
    current_bid = current_tick.bid
    
    # Calculate buy and sell prices ensuring they are at valid distances from current market
    # BUY_STOP orders must be placed above current ask price
    # SELL_STOP orders must be placed below current bid price
    min_buy_price = current_ask + (20 * pip_value)  # Minimum 20 pips above current ask
    max_buy_price = current_ask + (50 * pip_value)  # Maximum 50 pips above current ask
    
    min_sell_price = current_bid - (50 * pip_value)  # Maximum 50 pips below current bid
    max_sell_price = current_bid - (20 * pip_value)  # Minimum 20 pips below current bid
    
    # Calculate initial breakout prices
    raw_buy_price = session_high + breakout_distance
    raw_sell_price = session_low - breakout_distance
    
    # Adjust prices to be within valid ranges
    buy_price = max(min_buy_price, min(max_buy_price, raw_buy_price))
    sell_price = max(min_sell_price, min(max_sell_price, raw_sell_price))

    # Enforce a minimum gap between pending orders to avoid opposite triggers near market
    gap_points = buy_price - sell_price
    min_gap_points = 40 * pip_value  # Ensure at least 40 pips gap between orders
    if gap_points < min_gap_points:
        logging.info(f"Pending order gap too small ({gap_points:.5f} pts). Applying single-side placement to avoid opposite triggers.")
        # Choose the side farther from current price to reduce immediate whipsaw
        buy_dist = abs(buy_price - current_ask)
        sell_dist = abs(current_bid - sell_price)
        if buy_dist >= sell_dist:
            place_sell_order = False
            logging.info("Selecting BUY_STOP only due to gap constraint")
        else:
            place_buy_order = False
            logging.info("Selecting SELL_STOP only due to gap constraint")
    
    logging.info(f"Session breakout prices - BUY: {raw_buy_price:.5f}, SELL: {raw_sell_price:.5f}")
    logging.info(f"Adjusted prices - BUY: {buy_price:.5f}, SELL: {sell_price:.5f}")
    logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
    
    # Calculate SL/TP distances based on ATR
    sl_distance = 3.0 * atr  # Using default LOW RISK profile
    tp_distance = 6.0 * atr
    
    # Calculate SL/TP for buy order using adjusted price
    buy_sl = buy_price - sl_distance
    buy_tp = buy_price + tp_distance
    
    # Calculate SL/TP for sell order using adjusted price
    sell_sl = sell_price + sl_distance
    sell_tp = sell_price - tp_distance
    
    # Calculate lot size based on risk management
    buy_volume = LOTS  # Default to fixed lot size
    if USE_RISK_MANAGEMENT:
        try:
            # Calculate lot size based on 1% risk rule
            buy_sl_distance = abs(buy_price - buy_sl)
            account_info = mt5.account_info()  # type: ignore
            balance = account_info.balance if account_info else 10000.0  # Default $10k account
            buy_volume = compute_lots_from_risk(
                balance=balance,
                risk_pct=RISK_PERCENT,
                sl_distance=buy_sl_distance,
                symbol=symbol
            )
            logging.info(f"Calculated lot size for BUY order: {buy_volume:.2f}")
        except Exception as e:
            logging.warning(f"Failed to calculate dynamic lot size for BUY order, using default: {e}")
            buy_volume = LOTS
    
    # Place buy stop order only if allowed
    buy_result = None
    if place_buy_order:
        buy_result = place_pending_order(
            symbol=symbol,
            order_type="BUY_STOP",
            volume=buy_volume,
            price=buy_price,
            sl=buy_sl,
            tp=buy_tp,
            magic=MAGIC_NUMBER,
            expiration_hours=8  # Expire after 8 hours
        )
    else:
        logging.info("Skipping BUY_STOP order placement due to existing opposite position")
    
    # Calculate lot size for sell order
    sell_volume = LOTS  # Default to fixed lot size
    if USE_RISK_MANAGEMENT:
        try:
            # Calculate lot size based on 1% risk rule
            sell_sl_distance = abs(sell_price - sell_sl)
            account_info = mt5.account_info()  # type: ignore
            balance = account_info.balance if account_info else 10000.0  # Default $10k account
            sell_volume = compute_lots_from_risk(
                balance=balance,
                risk_pct=RISK_PERCENT,
                sl_distance=sell_sl_distance,
                symbol=symbol
            )
            logging.info(f"Calculated lot size for SELL order: {sell_volume:.2f}")
        except Exception as e:
            logging.warning(f"Failed to calculate dynamic lot size for SELL order, using default: {e}")
            sell_volume = LOTS
    
    # Place sell stop order only if allowed
    sell_result = None
    if place_sell_order:
        sell_result = place_pending_order(
            symbol=symbol,
            order_type="SELL_STOP",
            volume=sell_volume,
            price=sell_price,
            sl=sell_sl,
            tp=sell_tp,
            magic=MAGIC_NUMBER,
            expiration_hours=8  # Expire after 8 hours
        )
    else:
        logging.info("Skipping SELL_STOP order placement due to existing opposite position")
    
    # Track pending orders by session
    if buy_result or sell_result:
        session_pending_orders[session_name] = {
            "buy_order": buy_result.order if buy_result else None,
            "sell_order": sell_result.order if sell_result else None,
            "timestamp": datetime.now(timezone.utc)
        }
        buy_info = f"BUY @ {buy_price:.5f}" if place_buy_order else "BUY skipped"
        sell_info = f"SELL @ {sell_price:.5f}" if place_sell_order else "SELL skipped"
        logging.info(f"Placed session breakout orders for {session_name}: {buy_info}, {sell_info}")
        return True
    elif place_buy_order or place_sell_order:
        # We intended to place orders but failed
        logging.error(f"Failed to place session breakout orders for {session_name}")
        return False
    else:
        # No orders were intended to be placed
        logging.info(f"No session breakout orders placed for {session_name} due to existing positions")
        return True


@handle_exception
@performance_monitor
def cancel_session_orders(session_name):
    """
    Cancel pending orders for a specific session
    
    Args:
        session_name: Session name ("Asia", "London", "NewYork")
    """
    global session_pending_orders
    
    if session_name not in session_pending_orders:
        logging.debug(f"No pending orders found for session {session_name}")
        return True
    
    session_orders = session_pending_orders[session_name]
    
    # Cancel buy order if it exists
    if session_orders.get("buy_order"):
        try:
            # Prepare cancel request
            request = {
                'action': mt5.TRADE_ACTION_REMOVE,  # type: ignore
                'order': int(session_orders["buy_order"]),
                'type_time': mt5.ORDER_TIME_GTC,  # type: ignore
                'type_filling': mt5.ORDER_FILLING_FOK  # type: ignore
            }
            
            result = mt5.order_send(request)  # type: ignore
            if result and getattr(result, 'retcode', None) == mt5.TRADE_RETCODE_DONE:  # type: ignore
                logging.info(f"Cancelled buy order {session_orders['buy_order']} for session {session_name}")
            else:
                logging.warning(f"Failed to cancel buy order {session_orders['buy_order']} for session {session_name}")
        except Exception as e:
            logging.error(f"Error cancelling buy order for session {session_name}: {e}")
    
    # Cancel sell order if it exists
    if session_orders.get("sell_order"):
        try:
            # Prepare cancel request
            request = {
                'action': mt5.TRADE_ACTION_REMOVE,  # type: ignore
                'order': int(session_orders["sell_order"]),
                'type_time': mt5.ORDER_TIME_GTC,  # type: ignore
                'type_filling': mt5.ORDER_FILLING_FOK  # type: ignore
            }
            
            result = mt5.order_send(request)  # type: ignore
            if result and getattr(result, 'retcode', None) == mt5.TRADE_RETCODE_DONE:  # type: ignore
                logging.info(f"Cancelled sell order {session_orders['sell_order']} for session {session_name}")
            else:
                logging.warning(f"Failed to cancel sell order {session_orders['sell_order']} for session {session_name}")
        except Exception as e:
            logging.error(f"Error cancelling sell order for session {session_name}: {e}")
    
    # Remove from tracking
    del session_pending_orders[session_name]
    logging.info(f"Cancelled all pending orders for session {session_name}")
    return True


@handle_exception
@performance_monitor
def check_existing_session_orders(session_name):
    """
    Check if there are already pending orders for a session
    
    Args:
        session_name: Session name ("Asia", "London", "NewYork")
        
    Returns:
        bool: True if orders exist, False otherwise
    """
    global session_pending_orders
    
    # Check our tracking dictionary
    if session_name in session_pending_orders:
        session_orders = session_pending_orders[session_name]
        # Check if orders are still active
        if session_orders.get("buy_order") or session_orders.get("sell_order"):
            # Verify with MT5 that orders still exist
            orders = mt5.orders_get()  # type: ignore
            if orders:
                for order in orders:
                    if (getattr(order, 'magic', 0) == MAGIC_NUMBER and 
                        (order.ticket == session_orders.get("buy_order") or 
                         order.ticket == session_orders.get("sell_order"))):
                        return True
            # If we get here, orders may have been filled or cancelled
            del session_pending_orders[session_name]
    
    return False


@handle_exception
@performance_monitor
def run_strategy(symbol="XAUUSD"):
    """Main strategy function with pending orders"""
    global last_session, session_pending_orders
    
    logging.info(f"Running strategy for symbol: {symbol}")
    
    # Check if we're in trading hours
    if not in_trading_hours():
        logging.info("Outside trading hours")
        return
    
    # Check for news events that might affect trading
    if news_filter.is_news_time():
        logging.info("News event detected, skipping trade execution")
        return
    
    # Check spread first
    spread = get_current_spread(symbol)
    if spread is None:
        logging.error("Failed to get current spread")
        return
    
    if spread > MAX_SPREAD_POINTS:
        logging.info(f"Spread too high: {spread:.2f} points > {MAX_SPREAD_POINTS} points, skipping")
        return
    
    # Cancel expired pending orders
    cancel_expired_pending_orders(MAGIC_NUMBER)
    
    # Initialize breakout variables
    bullish_breakout = False
    bearish_breakout = False
    
    # Get Donchian channels early for position management
    upper_channel, lower_channel = get_donchian_channels(symbol, DONCHIAN_PERIOD)
    if upper_channel is None or lower_channel is None:
        logging.error("Failed to calculate Donchian channels")
        return
    
    # Get current price early for breakout detection
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error("Failed to get current tick data")
        return
    
    # Use bid price for analysis (real market price) - FIXED FOR FTMO
    current_close = tick.bid
    
    # Calculate ATR for breakout detection
    atr = calculate_atr(symbol)
    if atr is None:
        logging.error("ATR failed")
        return
    
    # Check for breakout conditions early for position management
    # Enhanced breakout detection with configurable threshold
    if BREAKOUT_THRESHOLD > 0:
        # Use threshold for stronger breakout confirmation
        bullish_breakout = current_close > (upper_channel + (BREAKOUT_THRESHOLD * atr))
        bearish_breakout = current_close < (lower_channel - (BREAKOUT_THRESHOLD * atr))
    else:
        # Standard breakout detection
        bullish_breakout = current_close > upper_channel
        bearish_breakout = current_close < lower_channel
    
    # Check existing positions and limits
    positions = mt5.positions_get(symbol=symbol)  # type: ignore
    
    # Get max positions from config, default to 2 if not specified
    try:
        max_positions = cfg.get('position_limits.max_positions', 2)
    except:
        max_positions = 2
    
    if positions:
        # Count positions by direction
        buy_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_BUY)  # type: ignore
        sell_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_SELL)  # type: ignore
        total_positions = len(positions)
        
        # Block if max total positions reached
        if total_positions >= max_positions:
            logging.info(f"Max positions reached ({total_positions}/{max_positions}), skipping")
            return
        
        # Block opposite direction trades
        if bullish_breakout and sell_positions > 0:
            logging.info(f"Opposite SELL position exists, cannot open BUY")
            return
        if bearish_breakout and buy_positions > 0:
            logging.info(f"Opposite BUY position exists, cannot open SELL")
            return
        
        # Allow same-direction trades if under max_positions
        if bullish_breakout and buy_positions >= max_positions:
            logging.info(f"Max BUY positions reached ({buy_positions}/{max_positions})")
            return
        if bearish_breakout and sell_positions >= max_positions:
            logging.info(f"Max SELL positions reached ({sell_positions}/{max_positions})")
            return
        
        logging.info(f"Positions: {buy_positions} BUY, {sell_positions} SELL. Allowing same-direction trade")
    
    # SESSION BREAKOUT LOGIC
    # Get current session
    current_session = get_current_session()
    
    # Check if we're at the start of a new session
    if current_session and current_session != last_session:
        logging.info(f"New session started: {current_session}")
        
        # Cancel previous session orders if they exist
        if last_session and last_session in session_pending_orders:
            cancel_session_orders(last_session)
        
        # Check if we already have session orders for this session
        if not check_existing_session_orders(current_session):
            # Place new session breakout orders
            place_session_breakout_orders(symbol, current_session)
        
        # Update last session
        last_session = current_session
        # Continue with Donchian strategy even after placing session orders
    
    # Continue with existing Donchian strategy logic if no session change
    # Check for existing pending orders
    orders = mt5.orders_get(symbol=symbol)  # type: ignore
    pending_orders = [order for order in orders if getattr(order, 'magic', 0) == MAGIC_NUMBER] if orders else []
    if pending_orders:
        logging.info(f"Pending order already exists for {symbol}, skipping")
        return
    
    # Calculate momentum values
    current_momentum = calculate_avg_momentum(symbol, MOMENTUM_PERIOD)
    historical_momentum = calculate_avg_momentum(symbol, SAMPLE_PERIOD)
    
    logging.info(f"Momentum values - Current: {current_momentum}, Historical: {historical_momentum}")
    
    # Get volume stats for event detection
    current_volume, avg_volume = get_volume_stats(symbol)
    volume_spike = current_volume and avg_volume and current_volume > avg_volume * EVENT_VOLUME_SPIKE_FACTOR
    
    # Use bid price for analysis (real market price) - FIXED FOR FTMO
    logging.info(f"Current close price (bid): {current_close}")
    logging.info(f"Upper channel: {upper_channel}, Lower channel: {lower_channel}")
    
    # Calculate ATR for dynamic SL/TP
    if atr is None:
        logging.error("ATR failed")
        return
    
    # Momentum filter: current > historical * 0.3 (less restrictive)
    momentum_filter = current_momentum > (historical_momentum * 0.3)
    
    # Add volume confirmation
    volume_spike, vol_ratio = get_volume_breakout(symbol)
    
    # Detect engulfing patterns
    bullish_engulfing, bearish_engulfing = detect_engulfing(symbol)
    
    # Volume confirmation made optional for more signals during testing
    if bullish_breakout and momentum_filter:  # Removed engulfing confirmation for more signals
        logging.info(f"STRONG BUY signal: Volume {vol_ratio:.2f}x average")
        
        # Calculate pending order price (0.5 * ATR above upper channel)
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if not symbol_info:
            logging.error(f"Failed to get symbol info for {symbol}")
            return
        point = symbol_info.point
        
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        
        # Calculate breakout distance
        breakout_distance = 0.5 * atr
        raw_pending_price = upper_channel + breakout_distance
        
        # Get current market price to ensure orders are placed at valid distances
        current_tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if current_tick is None:
            logging.error(f"Failed to get current tick data for {symbol}")
            return
        
        current_ask = current_tick.ask
        current_bid = current_tick.bid
        
        # For BUY_STOP orders, they must be placed above current ask price
        # But not too far above to avoid error 10015
        pip_value = point * 10  # Standard pip calculation
        min_buy_price = current_ask + (5 * pip_value)   # Minimum 5 pips above current ask
        max_buy_price = current_ask + (50 * pip_value)  # Maximum 50 pips above current ask
        
        # Adjust price to be within valid range
        pending_price = max(min_buy_price, min(max_buy_price, raw_pending_price))
        
        logging.info(f"Raw BUY_STOP price: {raw_pending_price:.5f}, Adjusted price: {pending_price:.5f}")
        logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
        
        # Calculate dynamic SL/TP based on ATR and risk profile using adjusted price
        sl_price, tp_price = calculate_dynamic_stops(symbol, pending_price, "BUY", atr)
        
        # Calculate lot size based on risk management
        buy_volume = LOTS  # Default to fixed lot size
        if USE_RISK_MANAGEMENT:
            try:
                # Calculate lot size based on 1% risk rule
                buy_sl_distance = abs(pending_price - sl_price)
                account_info = mt5.account_info()  # type: ignore
                balance = account_info.balance if account_info else 10000.0  # Default $10k account
                buy_volume = compute_lots_from_risk(
                    balance=balance,
                    risk_pct=RISK_PERCENT,
                    sl_distance=buy_sl_distance,
                    symbol=symbol
                )
                logging.info(f"Calculated lot size for BUY pending order: {buy_volume:.2f}")
            except Exception as e:
                logging.warning(f"Failed to calculate dynamic lot size for BUY pending order, using default: {e}")
                buy_volume = LOTS
        
        # Place pending order
        result = place_pending_order(
            symbol=symbol,
            order_type="BUY_STOP",
            volume=buy_volume,
            price=pending_price,
            sl=sl_price,
            tp=tp_price,
            magic=MAGIC_NUMBER
        )
        
        if result:
            logging.info(f"BUY_STOP order placed: Price={pending_price:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}")
        else:
            logging.error("Failed to place BUY_STOP order")
            
    elif bearish_breakout and momentum_filter:  # Removed engulfing confirmation for more signals
        logging.info(f"STRONG SELL signal: Volume {vol_ratio:.2f}x average")
        
        # Calculate pending order price (0.5 * ATR below lower channel)
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if not symbol_info:
            logging.error(f"Failed to get symbol info for {symbol}")
            return
        point = symbol_info.point
        
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        
        # Calculate breakout distance
        breakout_distance = 0.5 * atr
        raw_pending_price = lower_channel - breakout_distance
        
        # Get current market price to ensure orders are placed at valid distances
        current_tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if current_tick is None:
            logging.error(f"Failed to get current tick data for {symbol}")
            return
        
        current_ask = current_tick.ask
        current_bid = current_tick.bid
        
        # For SELL_STOP orders, they must be placed below current bid price
        # But not too far below to avoid error 10015
        pip_value = point * 10  # Standard pip calculation
        min_sell_price = current_bid - (50 * pip_value)  # Maximum 50 pips below current bid
        max_sell_price = current_bid - (5 * pip_value)   # Minimum 5 pips below current bid
        
        # Adjust price to be within valid range
        pending_price = max(min_sell_price, min(max_sell_price, raw_pending_price))
        
        logging.info(f"Raw SELL_STOP price: {raw_pending_price:.5f}, Adjusted price: {pending_price:.5f}")
        logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
        
        # Calculate dynamic SL/TP based on ATR and risk profile using adjusted price
        sl_price, tp_price = calculate_dynamic_stops(symbol, pending_price, "SELL", atr)
        
        # Calculate lot size based on risk management
        sell_volume = LOTS  # Default to fixed lot size
        if USE_RISK_MANAGEMENT:
            try:
                # Calculate lot size based on 1% risk rule
                sell_sl_distance = abs(pending_price - sl_price)
                account_info = mt5.account_info()  # type: ignore
                balance = account_info.balance if account_info else 10000.0  # Default $10k account
                sell_volume = compute_lots_from_risk(
                    balance=balance,
                    risk_pct=RISK_PERCENT,
                    sl_distance=sell_sl_distance,
                    symbol=symbol
                )
                logging.info(f"Calculated lot size for SELL pending order: {sell_volume:.2f}")
            except Exception as e:
                logging.warning(f"Failed to calculate dynamic lot size for SELL pending order, using default: {e}")
                sell_volume = LOTS
        
        # Place pending order
        result = place_pending_order(
            symbol=symbol,
            order_type="SELL_STOP",
            volume=sell_volume,
            price=pending_price,
            sl=sl_price,
            tp=tp_price,
            magic=MAGIC_NUMBER
        )
        
        if result:
            logging.info(f"SELL_STOP order placed: Price={pending_price:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}")
        else:
            logging.error("Failed to place SELL_STOP order")

@handle_exception
@performance_monitor
def main():
    """Main function to run the strategy"""
    logging.info("Starting Donchian Breakout Strategy")
    
    # Load configuration set file if specified
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    if set_file:
        try:
            cfg = get_set_manager()
            cfg.load_set_file(set_file)
            logging.info(f"Loaded configuration set: {set_file}")
        except Exception as e:
            logging.warning(f"Failed to load configuration set {set_file}: {e}. Using default values.")
    
    # Initialize MT5
    if not initialize_mt5():
        return
    
    # Select symbol
    symbol = os.getenv('TRADING_SYMBOL', 'XAUUSD')
    logging.info(f"Selecting symbol: {symbol}")
    if not mt5.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()  # type: ignore
        return
    
    # Initialize FTMO safety module
    from safety import FTMOSafety
    safety = FTMOSafety(mt5_module=mt5)
    
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
            # Show FTMO dashboard
            try:
                from ftmo_manager import ftmo_manager
                logging.info(ftmo_manager.get_ftmo_dashboard())
            except Exception as e:
                logging.debug(f"Failed to show FTMO dashboard: {e}")
            run_strategy(symbol)
        
        # Import the monitoring function
        from mt5_utils import monitor_and_update_stops
        
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
                # Show FTMO dashboard every 10 iterations
                import random
                if random.randint(1, 10) == 1:  # Roughly every 50 minutes
                    try:
                        from ftmo_manager import ftmo_manager
                        logging.info(ftmo_manager.get_ftmo_dashboard())
                    except Exception as e:
                        logging.debug(f"Failed to show FTMO dashboard: {e}")
                run_strategy(symbol)
            
            # Monitor positions and add SL/TP if missing
            try:
                monitor_and_update_stops()
            except Exception as e:
                logging.error(f"Error monitoring positions: {e}", exc_info=True)
            
            # Update trailing stops
            try:
                update_trailing_stops()
            except Exception as e:
                logging.error(f"Error updating trailing stops: {e}", exc_info=True)
            
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

def calculate_take_profit_level(symbol, entry_price, order_type, atr=None):
    """
    Calculate take profit level based on market structure analysis.
    Looks for FVG (Fair Value Gaps), order blocks, equal highs/lows, and liquidity points.
    
    Args:
        symbol: Trading symbol
        entry_price: Entry price
        order_type: "BUY" or "SELL"
        atr: Average True Range (optional)
    
    Returns:
        float: Take profit price level
    """
    # Get historical data for market structure analysis (focus on recent intraday data)
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 1, 50)  # type: ignore
    if rates is None or len(rates) < 20:
        # Fallback to fixed TP if not enough data
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        point = symbol_info.point if symbol_info else 0.01
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        if order_type == "BUY":
            return entry_price + (300 * point)  # 300 points for BUY
        else:
            return entry_price - (300 * point)  # 300 points for SELL
    
    # Convert to list of dictionaries for easier handling
    candles = []
    for rate in rates:
        candles.append({
            'time': rate['time'],
            'open': rate['open'],
            'high': rate['high'],
            'low': rate['low'],
            'close': rate['close'],
            'volume': rate['tick_volume']
        })
    
    # Reverse to have most recent first
    candles.reverse()
    
    if order_type == "BUY":
        # For BUY orders, look for resistance levels above entry price
        tp_level = find_bullish_targets(candles, entry_price)
    else:
        # For SELL orders, look for support levels below entry price
        tp_level = find_bearish_targets(candles, entry_price)
    
    # If no market structure levels found, use ATR-based calculation
    if tp_level is None:
        if atr is not None:
            # Use 1.5x ATR as TP distance (more aggressive for intraday)
            tp_distance = atr * 1.5
            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            point = symbol_info.point if symbol_info else 0.01
            # Adjust point value for NASDAQ
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            tp_points = tp_distance / point
            if order_type == "BUY":
                tp_level = entry_price + (tp_points * point)
            else:
                tp_level = entry_price - (tp_points * point)
        else:
            # Fallback to fixed TP
            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            point = symbol_info.point if symbol_info else 0.01
            # Adjust point value for NASDAQ
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            if order_type == "BUY":
                tp_level = entry_price + (300 * point)
            else:
                tp_level = entry_price - (300 * point)
    
    return tp_level


def find_bullish_targets(candles, entry_price):
    """
    Find bullish targets based on market structure.
    Looks for FVG, order blocks, equal highs, and liquidity points above entry price.
    """
    # Look for resistance levels above entry price
    resistance_levels = []
    
    # Find swing highs in recent candles (more sensitive for intraday)
    for i in range(5, min(30, len(candles) - 5)):
        current = candles[i]
        is_swing_high = True
        
        # Check if current candle is higher high than surrounding candles (less strict)
        for j in range(i-3, i):
            if candles[j]['high'] >= current['high']:
                is_swing_high = False
                break
        
        for j in range(i+1, i+4):
            if candles[j]['high'] >= current['high']:
                is_swing_high = False
                break
        
        if is_swing_high and current['high'] > entry_price:
            resistance_levels.append(current['high'])
    
    # Find FVG (Fair Value Gaps) - gaps where price jumped up
    for i in range(3, len(candles) - 3):
        prev_candle = candles[i-1]
        current_candle = candles[i]
        
        # Look for significant gaps up (FVG) - more sensitive for intraday
        gap_size = current_candle['low'] - prev_candle['high']
        atr = calculate_candle_atr(candles, i)
        if gap_size > atr * 0.3:  # More sensitive gap detection
            fvg_level = (current_candle['low'] + prev_candle['high']) / 2
            if fvg_level > entry_price:
                resistance_levels.append(fvg_level)
    
    # Return the closest resistance level above entry price
    if resistance_levels:
        # Filter levels that are reasonably close (not too far) - more generous for intraday
        reasonable_levels = [level for level in resistance_levels if level <= entry_price * 1.10]  # Max 10% away
        if reasonable_levels:
            return min(reasonable_levels)  # Closest level
        else:
            return min(resistance_levels)  # Any level
    
    return None


def find_bearish_targets(candles, entry_price):
    """
    Find bearish targets based on market structure.
    Looks for FVG, order blocks, equal lows, and liquidity points below entry price.
    """
    # Look for support levels below entry price
    support_levels = []
    
    # Find swing lows in recent candles (more sensitive for intraday)
    for i in range(5, min(30, len(candles) - 5)):
        current = candles[i]
        is_swing_low = True
        
        # Check if current candle is lower low than surrounding candles (less strict)
        for j in range(i-3, i):
            if candles[j]['low'] <= current['low']:
                is_swing_low = False
                break
        
        for j in range(i+1, i+4):
            if candles[j]['low'] <= current['low']:
                is_swing_low = False
                break
        
        if is_swing_low and current['low'] < entry_price:
            support_levels.append(current['low'])
    
    # Find FVG (Fair Value Gaps) - gaps where price jumped down
    for i in range(3, len(candles) - 3):
        prev_candle = candles[i-1]
        current_candle = candles[i]
        
        # Look for significant gaps down (FVG) - more sensitive for intraday
        gap_size = prev_candle['low'] - current_candle['high']
        atr = calculate_candle_atr(candles, i)
        if gap_size > atr * 0.3:  # More sensitive gap detection
            fvg_level = (prev_candle['low'] + current_candle['high']) / 2
            if fvg_level < entry_price:
                support_levels.append(fvg_level)
    
    # Return the closest support level below entry price
    if support_levels:
        # Filter levels that are reasonably close (not too far) - more generous for intraday
        reasonable_levels = [level for level in support_levels if level >= entry_price * 0.90]  # Max 10% away
        if reasonable_levels:
            return max(reasonable_levels)  # Closest level
        else:
            return max(support_levels)  # Any level
    
    return None


def calculate_candle_atr(candles, index):
    """
    Calculate ATR for a specific candle.
    """
    if index >= len(candles) or index < 1:
        return 0
    
    candle = candles[index]
    prev_candle = candles[index-1]
    
    tr1 = candle['high'] - candle['low']
    tr2 = abs(candle['high'] - prev_candle['close'])
    tr3 = abs(candle['low'] - prev_candle['close'])
    
    return max(tr1, tr2, tr3)


if __name__ == "__main__":
    main()