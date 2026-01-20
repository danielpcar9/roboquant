# mt5_core.py
"""
Core MT5 functionality consolidated in one place to eliminate duplication.
"""
import time
import logging

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

# Import security manager for credential handling
from services.security_manager import SecureCredentialManager, sanitize_error_message

# Initialize credential manager
credential_manager = SecureCredentialManager()

def initialize_mt5():
    """Initialize MT5 connection with credentials from secure credential manager"""
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

def timeframe_to_string(timeframe):
    """Convert MT5 timeframe constant to string representation"""
    timeframe_map = {
        mt5.TIMEFRAME_M1: 'M1',
        mt5.TIMEFRAME_M5: 'M5',
        mt5.TIMEFRAME_M15: 'M15',
        mt5.TIMEFRAME_M30: 'M30',
        mt5.TIMEFRAME_H1: 'H1',
        mt5.TIMEFRAME_H4: 'H4',
        mt5.TIMEFRAME_D1: 'D1',
        mt5.TIMEFRAME_W1: 'W1',
        mt5.TIMEFRAME_MN1: 'MN1'
    }
    return timeframe_map.get(timeframe, 'H1')  # Default to H1 if not found

# Performance monitoring for strategy functions
STRATEGY_PERFORMANCE_MONITORING = True
strategy_execution_times = []

def strategy_performance_monitor(func):
    """Decorator to monitor strategy performance."""
    def wrapper(*args, **kwargs):
        if not STRATEGY_PERFORMANCE_MONITORING:
            return func(*args, **kwargs)

        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            strategy_execution_times.append(execution_time)
            logging.debug(f"Strategy Performance: {func.__name__} executed in {execution_time:.4f} seconds")

            # Log average execution time every 10 executions
            if len(strategy_execution_times) % 10 == 0:
                avg_time = sum(strategy_execution_times[-10:]) / min(10, len(strategy_execution_times))
                logging.info(f"Average execution time (last 10): {avg_time:.4f} seconds")

            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.debug(f"Strategy Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {e}")
            raise
    return wrapper

# Performance monitoring for MT5 utility functions
PERFORMANCE_MONITORING_ENABLED = True

def mt5_performance_monitor(func):
    """
    Decorator to monitor performance of MT5 functions.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with performance monitoring
    """
    def wrapper(*args, **kwargs):
        if not PERFORMANCE_MONITORING_ENABLED:
            return func(*args, **kwargs)

        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.debug(f"Performance: {func.__name__} executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.debug(f"Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {e}")
            raise
    return wrapper

def validate_and_adjust_stops(symbol, entry_price, sl, tp, side, mt5_module=None):
    """
    Validate and adjust SL/TP levels to meet broker requirements.
    Ensures minimum stop distance and correct direction.
    
    Args:
        symbol: Trading symbol
        entry_price: Entry price
        sl: Stop loss level
        tp: Take profit level
        side: Order side ("BUY" or "SELL")
        mt5_module: MT5 module instance
    
    Returns:
        tuple: (adjusted_sl, adjusted_tp)
    """
    if mt5_module is None:
        mt5_module = mt5

    # Get symbol info
    symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        logging.warning(f"Could not get symbol info for {symbol}, returning original SL/TP")
        return sl, tp

    point = symbol_info.point
    digits = symbol_info.digits

    # Get minimum stop distance (in points)
    # For Exness, this is typically available as freeze_level or distance fields
    min_stop_distance = getattr(symbol_info, 'freeze_level', 0)
    if min_stop_distance == 0:
        min_stop_distance = getattr(symbol_info, 'distance', 0)

    # If we still don't have a minimum distance, use a safe default
    # For XAUUSD, 400 points should be sufficient based on your config
    if min_stop_distance == 0:
        min_stop_distance = 400  # Default safe value

    logging.debug(f"Symbol {symbol} min stop distance: {min_stop_distance} points, point: {point}, digits: {digits}")

    # Round prices to correct number of decimal places
    if sl is not None:
        sl = round(sl, digits)
    if tp is not None:
        tp = round(tp, digits)

    # Adjust SL/TP based on order side and minimum distance requirements
    if side == "BUY":
        # For BUY orders: SL must be below entry, TP must be above entry
        if sl is not None:
            # Ensure SL is at least min_stop_distance below entry
            min_sl = entry_price - (min_stop_distance * point)
            # Make sure SL is not too close to current price
            current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
            safe_sl = min_sl
            if current_price - (min_stop_distance * point) < safe_sl:
                safe_sl = current_price - (min_stop_distance * point)
            adjusted_sl = min(sl, safe_sl)  # SL further from entry is safer
        else:
            adjusted_sl = None

        if tp is not None:
            # Ensure TP is at least min_stop_distance above entry
            min_tp = entry_price + (min_stop_distance * point)
            # Make sure TP is not too close to current price
            current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
            safe_tp = min_tp
            if current_price + (min_stop_distance * point) > safe_tp:
                safe_tp = current_price + (min_stop_distance * point)
            adjusted_tp = max(tp, safe_tp)  # TP further from entry is better
        else:
            adjusted_tp = None
    else:  # SELL
        # For SELL orders: SL must be above entry, TP must be below entry
        if sl is not None:
            # Ensure SL is at least min_stop_distance above entry
            min_sl = entry_price + (min_stop_distance * point)
            # Make sure SL is not too close to current price
            current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
            safe_sl = min_sl
            if current_price + (min_stop_distance * point) > safe_sl:
                safe_sl = current_price + (min_stop_distance * point)
            adjusted_sl = max(sl, safe_sl)  # SL further from entry is safer
        else:
            adjusted_sl = None

        if tp is not None:
            # Ensure TP is at least min_stop_distance below entry
            min_tp = entry_price - (min_stop_distance * point)
            # Make sure TP is not too close to current price
            current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
            safe_tp = min_tp
            if current_price - (min_stop_distance * point) < safe_tp:
                safe_tp = current_price - (min_stop_distance * point)
            adjusted_tp = min(tp, safe_tp)  # TP further from entry is better
        else:
            adjusted_tp = None

    # Round final values to correct decimal places
    if adjusted_sl is not None:
        adjusted_sl = round(adjusted_sl, digits)
    if adjusted_tp is not None:
        adjusted_tp = round(adjusted_tp, digits)

    logging.debug(f"SL/TP adjustment - Original: SL={sl}, TP={tp} | Adjusted: SL={adjusted_sl}, TP={adjusted_tp}")
    return adjusted_sl, adjusted_tp

def get_filling_mode(symbol, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5

    # For Exness accounts, use ORDER_FILLING_RETURN as the primary mode
    # Exness typically uses RETURN mode (mode 0) for most operations
    if hasattr(mt5_module, 'ORDER_FILLING_RETURN'):  # type: ignore
        return mt5_module.ORDER_FILLING_RETURN  # type: ignore

    # Fallback to symbol-specific filling mode if available
    sym = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym:
        logging.warning("Symbol %s info not available", symbol)
        return mt5_module.ORDER_FILLING_RETURN if hasattr(mt5_module, 'ORDER_FILLING_RETURN') else 0  # type: ignore

    try:
        filling_mode = getattr(sym, 'filling_mode', None)
    except AttributeError:
        return mt5_module.ORDER_FILLING_RETURN if hasattr(mt5_module, 'ORDER_FILLING_RETURN') else 0  # type: ignore

    if filling_mode is None:
        return mt5_module.ORDER_FILLING_RETURN if hasattr(mt5_module, 'ORDER_FILLING_RETURN') else 0  # type: ignore

    try:
        # Try FOK first (Fill or Kill)
        if hasattr(mt5_module, 'ORDER_FILLING_FOK'):  # type: ignore
            if filling_mode & mt5_module.ORDER_FILLING_FOK:  # type: ignore
                return mt5_module.ORDER_FILLING_FOK  # type: ignore

        # Try IOC next (Immediate or Cancel)
        if hasattr(mt5_module, 'ORDER_FILLING_IOC'):  # type: ignore
            if filling_mode & mt5_module.ORDER_FILLING_IOC:  # type: ignore
                return mt5_module.ORDER_FILLING_IOC  # type: ignore

        # Try RETURN as fallback (Return if not filled)
        if hasattr(mt5_module, 'ORDER_FILLING_RETURN'):  # type: ignore
            if filling_mode & mt5_module.ORDER_FILLING_RETURN:  # type: ignore
                return mt5_module.ORDER_FILLING_RETURN  # type: ignore
    except Exception as e:
        logging.debug("Error checking filling mode: %s", e)

    # Default fallback
    logging.warning("Using default ORDER_FILLING_RETURN for %s", symbol)
    return mt5_module.ORDER_FILLING_RETURN if hasattr(mt5_module, 'ORDER_FILLING_RETURN') else 0  # type: ignore

def normalize_volume(symbol, requested_volume, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5

    info = mt5_module.symbol_info(symbol)  # type: ignore
    if not info:
        logging.error("Symbol %s info not available", symbol)
        return requested_volume

    volume_min = getattr(info, 'volume_min', 0.01) or 0.01
    volume_step = getattr(info, 'volume_step', 0.01) or 0.01
    volume_max = getattr(info, 'volume_max', 100.0)

    normalized = max(volume_min, round(requested_volume / volume_step) * volume_step)

    if volume_max and normalized > volume_max:
        normalized = volume_max

    return float(normalized)
