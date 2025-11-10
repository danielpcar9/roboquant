import time
import logging
import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass
from typing import Optional

# Import caching system

# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore


from mt5_utils import build_and_send_order, normalize_volume, monitor_and_update_stops
from safety import Safety
# Import security manager
from security_manager import SecureCredentialManager, InputValidator, sanitize_error_message, RateLimiter
# Import config manager
from config_manager import config_manager
# Import set file manager
from set_file_manager import get_set_manager
# Import error handler
from error_handler import handle_exception, retry_with_exponential_backoff, MT5ConnectionError, OrderExecutionError

# Import trade scorer
from trade_scorer import TradeScorer

# Import consolidated performance monitoring
from mt5_core import strategy_performance_monitor as performance_monitor

# Add import for mt5 to ensure symbol_info is available
import metatrader5 as mt5

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
MIN_TRADE_QUALITY_SCORE = config_manager.get('MIN_TRADE_QUALITY_SCORE', 45)  # New parameter for evaluation period

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
            MIN_TRADE_QUALITY_SCORE = cfg.get('strategy.min_trade_quality_score', MIN_TRADE_QUALITY_SCORE)
            
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
EVENT_VOLUME_SPIKE_FACTOR = config_manager.get('EVENT_VOLUME_SPIKE_FACTOR')
MAX_SPREAD_POINTS = config_manager.get('MAX_SPREAD_POINTS')

# Performance monitoring
STRATEGY_PERFORMANCE_MONITORING = True
strategy_execution_times = []

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
def run_strategy(symbol="XAUUSD"):
    """Main strategy function"""
    
    logging.info(f"Running strategy for symbol: {symbol}")
    
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
    
    # Use last price for analysis (real market price) - FIXED FOR FTMO
    current_close = tick.last
    logging.info(f"Current close price (bid): {current_close}")
    logging.info(f"Upper channel: {upper_channel}, Lower channel: {lower_channel}")
    
    # Calculate ATR for event-driven trading
    atr = calculate_atr(symbol)
    if atr is None:
        logging.error("ATR failed")
        return
    
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
    # Reducir momentum_filter a 0.5x para FTMO
    momentum_filter = current_momentum > (historical_momentum * 0.5)
    
    # Add volume confirmation
    volume_spike, vol_ratio = get_volume_breakout(symbol)
    
    # Initialize trade scorer
    trade_scorer = TradeScorer()
    
    # Volume confirmation made optional for more signals during testing
    if bullish_breakout and momentum_filter:  # Removed volume_spike requirement
        logging.info(f"STRONG BUY signal: Volume {vol_ratio:.2f}x average")
        
        # Score the trade setup
        quality = trade_scorer.score_trade_setup(
            symbol=symbol,
            price=current_close,
            upper_channel=upper_channel,
            lower_channel=lower_channel,
            current_momentum=current_momentum,
            historical_momentum=historical_momentum,
            atr=atr,
            avg_atr=historical_momentum  # Using historical momentum as proxy for avg ATR
        )
        
        logging.info(f"Trade quality score: {quality['score']}/100, Grade: {quality['grade']}")
        
        # More flexible threshold for evaluation period - allow trades with score >= MIN_TRADE_QUALITY_SCORE
        # This will increase trade frequency while still filtering out the worst setups
        if quality['score'] < MIN_TRADE_QUALITY_SCORE:
            logging.info(f"Trade not recommended based on quality score ({quality['score']} < {MIN_TRADE_QUALITY_SCORE})")
            return
            
        # Adjust risk by quality - more granular adjustment for evaluation period
        score = quality['score']
        if score >= 80:
            risk_mult = 1.5  # High confidence - increase position size
        elif score >= 70:
            risk_mult = 1.2  # Good confidence - slight increase
        elif score >= 60:
            risk_mult = 1.0  # Normal confidence - standard position size
        elif score >= 50:
            risk_mult = 0.8  # Lower confidence - reduced position size
        else:
            risk_mult = 0.6  # Minimum confidence - much reduced position size
            
        adjusted_lots = LOTS * risk_mult
        
        logging.info(f"Quality-based lot adjustment: {LOTS:.2f} -> {adjusted_lots:.2f} (score: {score})")
        
        # Use market structure analysis for TP in normal mode as well
        tp_price = calculate_take_profit_level(symbol, current_close, "BUY", atr)
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        tp_points = abs(tp_price - current_close) / symbol_info.point if symbol_info else 300
        
        execute_trade(symbol, "BUY", adjusted_lots, STOP_LOSS_POINTS, tp_points)
    elif bearish_breakout and momentum_filter:  # Removed volume_spike requirement
        logging.info(f"STRONG SELL signal: Volume {vol_ratio:.2f}x average")
        
        # Score the trade setup
        quality = trade_scorer.score_trade_setup(
            symbol=symbol,
            price=current_close,
            upper_channel=upper_channel,
            lower_channel=lower_channel,
            current_momentum=current_momentum,
            historical_momentum=historical_momentum,
            atr=atr,
            avg_atr=historical_momentum  # Using historical momentum as proxy for avg ATR
        )
        
        logging.info(f"Trade quality score: {quality['score']}/100, Grade: {quality['grade']}")
        
        # More flexible threshold for evaluation period - allow trades with score >= MIN_TRADE_QUALITY_SCORE
        # This will increase trade frequency while still filtering out the worst setups
        if quality['score'] < MIN_TRADE_QUALITY_SCORE:
            logging.info(f"Trade not recommended based on quality score ({quality['score']} < {MIN_TRADE_QUALITY_SCORE})")
            return
            
        # Adjust risk by quality - more granular adjustment for evaluation period
        score = quality['score']
        if score >= 80:
            risk_mult = 1.5  # High confidence - increase position size
        elif score >= 70:
            risk_mult = 1.2  # Good confidence - slight increase
        elif score >= 60:
            risk_mult = 1.0  # Normal confidence - standard position size
        elif score >= 50:
            risk_mult = 0.8  # Lower confidence - reduced position size
        else:
            risk_mult = 0.6  # Minimum confidence - much reduced position size
            
        adjusted_lots = LOTS * risk_mult
        
        logging.info(f"Quality-based lot adjustment: {LOTS:.2f} -> {adjusted_lots:.2f} (score: {score})")
        
        # Use market structure analysis for TP in normal mode as well
        tp_price = calculate_take_profit_level(symbol, current_close, "SELL", atr)
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        tp_points = abs(tp_price - current_close) / symbol_info.point if symbol_info else 300
        
        execute_trade(symbol, "SELL", adjusted_lots, STOP_LOSS_POINTS, tp_points)

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
    symbol = "XAUUSD"
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
            
            # Update trailing stops for open positions
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
        point = mt5.symbol_info(symbol).point  # type: ignore
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
            point = mt5.symbol_info(symbol).point  # type: ignore
            tp_points = tp_distance / point
            if order_type == "BUY":
                tp_level = entry_price + (tp_points * point)
            else:
                tp_level = entry_price - (tp_points * point)
        else:
            # Fallback to fixed TP
            point = mt5.symbol_info(symbol).point  # type: ignore
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


def update_trailing_stops():
    """
    Update trailing stops for all open positions.
    Moves stop loss closer to current price as it moves in favor of the position.
    """
    # Get all open positions
    positions = mt5.positions_get()  # type: ignore
    if not positions:
        return
    
    for pos in positions:
        symbol = pos.symbol
        ticket = pos.ticket
        pos_type = pos.type
        entry_price = pos.price_open
        current_sl = pos.sl
        
        # Get current market price
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if not tick:
            continue
        
        # Get symbol information for point value
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if not symbol_info:
            continue
        
        point = symbol_info.point
        
        # Calculate trailing distance (25% of original SL distance)
        if pos_type == mt5.POSITION_TYPE_BUY:  # type: ignore
            # For BUY positions, trailing stop moves up
            original_distance = abs(entry_price - current_sl) if current_sl > 0 else (150 * point)
            trailing_distance = original_distance * 0.25  # 25% of original distance
            
            # Calculate new SL level based on current price
            current_price = tick.bid
            new_sl = current_price - trailing_distance
            
            # Only update if new SL is better than current SL and above entry price
            if (current_sl == 0 or new_sl > current_sl) and new_sl > entry_price:
                # Update the position with new SL
                request = {
                    'action': mt5.TRADE_ACTION_SLTP,  # type: ignore
                    'symbol': symbol,
                    'position': int(ticket),
                    'sl': new_sl,
                    'type_time': mt5.ORDER_TIME_GTC,  # type: ignore
                    'type_filling': mt5.ORDER_FILLING_RETURN  # type: ignore
                }
                
                result = mt5.order_send(request)  # type: ignore
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:  # type: ignore
                    logging.info(f"Trailing stop updated for BUY position {ticket}: SL moved to {new_sl:.5f}")
                else:
                    logging.warning(f"Failed to update trailing stop for BUY position {ticket}: {getattr(result, 'comment', 'N/A')}")
        else:  # SELL position
            # For SELL positions, trailing stop moves down
            original_distance = abs(entry_price - current_sl) if current_sl > 0 else (150 * point)
            trailing_distance = original_distance * 0.25  # 25% of original distance
            
            # Calculate new SL level based on current price
            current_price = tick.ask
            new_sl = current_price + trailing_distance
            
            # Only update if new SL is better than current SL and below entry price
            if (current_sl == 0 or new_sl < current_sl) and new_sl < entry_price:
                # Update the position with new SL
                request = {
                    'action': mt5.TRADE_ACTION_SLTP,  # type: ignore
                    'symbol': symbol,
                    'position': int(ticket),
                    'sl': new_sl,
                    'type_time': mt5.ORDER_TIME_GTC,  # type: ignore
                    'type_filling': mt5.ORDER_FILLING_RETURN  # type: ignore
                }
                
                result = mt5.order_send(request)  # type: ignore
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:  # type: ignore
                    logging.info(f"Trailing stop updated for SELL position {ticket}: SL moved to {new_sl:.5f}")
                else:
                    logging.warning(f"Failed to update trailing stop for SELL position {ticket}: {getattr(result, 'comment', 'N/A')}")


if __name__ == "__main__":
    main()