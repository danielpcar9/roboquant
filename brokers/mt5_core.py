# mt5_core.py
"""
Core MT5 functionality consolidated in one place to eliminate duplication.
"""

import logging
import time

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5
from services.security_manager import SecureCredentialManager, sanitize_error_message

# Initialize credential manager
credential_manager = SecureCredentialManager()


class MT5InitializationError(Exception):
    """Custom exception for MT5 initialization errors."""
    pass


def initialize_mt5():
    """Initialize MT5 connection with credentials from secure credential manager"""
    # Add more detailed initialization info
    logging.info("Attempting to initialize MT5...")

    # Get credentials from secure credential manager
    login = credential_manager.get_credential("MT5_LOGIN")
    password = credential_manager.get_credential("MT5_PASSWORD")
    server = credential_manager.get_credential("MT5_SERVER")

    # Initialize with credentials if available
    if login and password and server:
        try:
            login_int = int(login)
            logging.info(
                f"Initializing MT5 with credentials for account {login_int} on server {server}",
            )
            if not mt5.initialize(login=login_int, password=password, server=server):
                return _extracted_from_initialize_mt5_19(
                    "Failed to initialize MT5 with credentials"
                )
        except ValueError as e:
            logging.exception(
                f"Invalid login format: {login}. Error: {sanitize_error_message(str(e))}",
            )
            return False
    else:
        # Initialize without credentials
        logging.info("Initializing MT5 without credentials")
        if not mt5.initialize():
            return _extracted_from_initialize_mt5_19("Failed to initialize MT5")
    logging.info("MT5 initialized successfully")
    return True


# TODO Rename this here and in `initialize_mt5`
def _extracted_from_initialize_mt5_19(arg0):
    logging.error(arg0)
    error = mt5.last_error()
    logging.error(f"MT5 initialization error: {error}")
    return False


def initialize_mt5_connection(login: str, password: str, server: str, mt5_module=None):
    """
    Initialize MT5 connection with provided credentials.

    Args:
        login: MT5 account login
        password: MT5 account password
        server: MT5 server name
        mt5_module: MT5 module instance (for testing)
    """
    if mt5_module is None:
        mt5_module = mt5

    # Convert login to integer if it's a string
    try:
        login_int = int(login)
    except ValueError:
        raise ValueError(f"Invalid login format: {login}") from None

    # Attempt connection
    if not mt5_module.initialize(
        login=login_int, password=password, server=server,
    ):
        error = mt5_module.last_error()
        raise MT5InitializationError(f"MT5 initialization failed: {error}")


def timeframe_to_string(timeframe):
    """Convert MT5 timeframe constant to string representation"""
    timeframe_map = {
        mt5.TIMEFRAME_M1: "M1",
        mt5.TIMEFRAME_M5: "M5",
        mt5.TIMEFRAME_M15: "M15",
        mt5.TIMEFRAME_M30: "M30",
        mt5.TIMEFRAME_H1: "H1",
        mt5.TIMEFRAME_H4: "H4",
        mt5.TIMEFRAME_D1: "D1",
        mt5.TIMEFRAME_W1: "W1",
        mt5.TIMEFRAME_MN1: "MN1",
    }
    return timeframe_map.get(timeframe, "H1")  # Default to H1 if not found


# Performance monitoring for strategy functions
STRATEGY_PERFORMANCE_MONITORING = True
strategy_execution_times = []


def _execute_with_performance_monitoring(func, *args, **kwargs):
    """
    Execute a function with performance monitoring.

    Args:
        func: Function to execute
        *args: Arguments to pass to the function
        **kwargs: Keyword arguments to pass to the function

    Returns:
        Result of the function execution
    """
    start_time = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        return result, execution_time, None
    except Exception as e:
        end_time = time.perf_counter()
        execution_time = end_time - start_time
        return None, execution_time, e


def strategy_performance_monitor(func):
    """Decorator to monitor strategy performance."""

    def wrapper(*args, **kwargs):
        if not STRATEGY_PERFORMANCE_MONITORING:
            return func(*args, **kwargs)

        result, execution_time, error = _execute_with_performance_monitoring(func, *args, **kwargs)

        # Log execution time
        logging.debug(
            f"Strategy Performance: {func.__name__} executed in {execution_time:.4f} seconds",
        )

        # Log average execution time every 10 executions
        if result is not None:  # Only log if successful
            strategy_execution_times.append(execution_time)
            if len(strategy_execution_times) % 10 == 0:
                avg_time = sum(strategy_execution_times[-10:]) / min(
                    10, len(strategy_execution_times),
                )
                logging.info(
                    f"Average execution time (last 10): {avg_time:.4f} seconds",
                )

        # Handle errors if they occurred
        if error is not None:
            logging.debug(
                f"Strategy Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {error}",
            )
            raise error

        return result

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

        result, execution_time, error = _execute_with_performance_monitoring(func, *args, **kwargs)

        # Log execution time
        logging.debug(
            f"Performance: {func.__name__} executed in {execution_time:.4f} seconds",
        )

        # Handle errors if they occurred
        if error is not None:
            logging.debug(
                f"Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {error}",
            )
            raise error

        return result

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

    # Get symbol information and validation parameters
    symbol_info = _get_symbol_info_for_validation(symbol, mt5_module)
    if not symbol_info:
        return sl, tp

    point, digits, min_stop_distance = _extract_symbol_parameters(symbol_info)

    # Round input prices to correct decimal places
    sl, tp = _round_input_prices(sl, tp, digits)

    # Adjust stops based on order side
    adjusted_sl, adjusted_tp = _adjust_stops_by_side(
        side, entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module
    )

    # Round final values and log results
    final_sl, final_tp = _finalize_adjusted_stops(adjusted_sl, adjusted_tp, digits, sl, tp)

    return final_sl, final_tp


def _get_symbol_info_for_validation(symbol, mt5_module):
    """Get symbol information for stop validation."""
    symbol_info = mt5_module.symbol_info(symbol)
    if not symbol_info:
        logging.warning(
            f"Could not get symbol info for {symbol}, returning original SL/TP",
        )
    return symbol_info


def _extract_symbol_parameters(symbol_info):
    """Extract point, digits, and minimum stop distance from symbol info."""
    point = symbol_info.point
    digits = symbol_info.digits

    # Get minimum stop distance (in points)
    # For Exness, this is typically available as freeze_level or distance fields
    min_stop_distance = getattr(symbol_info, "freeze_level", 0)
    if min_stop_distance == 0:
        min_stop_distance = getattr(symbol_info, "distance", 0)

    # If we still don't have a minimum distance, use a safe default
    # For XAUUSD, 400 points should be sufficient based on your config
    if min_stop_distance == 0:
        min_stop_distance = 400  # Default safe value

    logging.debug(
        f"Symbol min stop distance: {min_stop_distance} points, point: {point}, digits: {digits}",
    )

    return point, digits, min_stop_distance


def _round_input_prices(sl, tp, digits):
    """Round input stop levels to correct decimal places."""
    if sl is not None:
        sl = round(sl, digits)
    if tp is not None:
        tp = round(tp, digits)
    return sl, tp


def _adjust_stops_by_side(side, entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module):
    """Adjust stop levels based on order side (BUY/SELL)."""
    if side == "BUY":
        return _adjust_buy_stops(entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module)
    else:  # SELL
        return _adjust_sell_stops(entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module)


def _adjust_buy_stops(entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module):
    """Adjust stop levels for BUY orders."""
    # For BUY orders: SL must be below entry, TP must be above entry
    adjusted_sl = _calculate_buy_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module)
    adjusted_tp = _calculate_buy_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module)

    return adjusted_sl, adjusted_tp


def _adjust_sell_stops(entry_price, sl, tp, symbol, min_stop_distance, point, mt5_module):
    """Adjust stop levels for SELL orders."""
    # For SELL orders: SL must be above entry, TP must be below entry
    adjusted_sl = _calculate_sell_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module)
    adjusted_tp = _calculate_sell_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module)

    return adjusted_sl, adjusted_tp


def _calculate_generic_stop_level(stop_level, entry_price, symbol, min_stop_distance, point, mt5_module,
                                 is_buy_order, is_take_profit):
    """
    Generic function to calculate adjusted stop levels (SL or TP) for BUY or SELL orders.

    Args:
        stop_level: The stop level (SL or TP) to adjust
        entry_price: Entry price for the order
        symbol: Trading symbol
        min_stop_distance: Minimum stop distance in points
        point: Point size for the symbol
        mt5_module: MT5 module instance
        is_buy_order: True if it's a BUY order, False if SELL
        is_take_profit: True if calculating TP, False if calculating SL

    Returns:
        Adjusted stop level or None if input was None
    """
    if stop_level is not None:
        # Determine price type (ask for BUY, bid for SELL) and comparison operator
        tick_info = mt5_module.symbol_info_tick(symbol)
        current_price = tick_info.ask if is_buy_order else tick_info.bid

        # Calculate minimum stop distance based on order type and whether it's SL or TP
        if (
            is_buy_order
            and is_take_profit
            or not is_buy_order
            and not is_take_profit
        ):  # BUY TP: must be above entry
            min_level = entry_price + (min_stop_distance * point)
            safe_level = min_level
            if current_price + (min_stop_distance * point) > safe_level:
                safe_level = current_price + (min_stop_distance * point)
            return max(stop_level, safe_level)  # TP further from entry is better
        else:  # BUY SL: must be below entry
            min_level = entry_price - (min_stop_distance * point)
            safe_level = min_level
            if current_price - (min_stop_distance * point) < safe_level:
                safe_level = current_price - (min_stop_distance * point)
            return min(stop_level, safe_level)  # SL further from entry is safer
    else:
        return None


def _calculate_buy_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted stop loss for BUY orders."""
    return _calculate_generic_stop_level(sl, entry_price, symbol, min_stop_distance, point, mt5_module,
                                        is_buy_order=True, is_take_profit=False)


def _calculate_buy_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted take profit for BUY orders."""
    return _calculate_generic_stop_level(tp, entry_price, symbol, min_stop_distance, point, mt5_module,
                                        is_buy_order=True, is_take_profit=True)


def _calculate_sell_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted stop loss for SELL orders."""
    return _calculate_generic_stop_level(sl, entry_price, symbol, min_stop_distance, point, mt5_module,
                                        is_buy_order=False, is_take_profit=False)


def _calculate_sell_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted take profit for SELL orders."""
    return _calculate_generic_stop_level(tp, entry_price, symbol, min_stop_distance, point, mt5_module,
                                        is_buy_order=False, is_take_profit=True)


def _finalize_adjusted_stops(adjusted_sl, adjusted_tp, digits, original_sl, original_tp):
    """Round final values and log adjustment results."""
    # Round final values to correct decimal places
    if adjusted_sl is not None:
        adjusted_sl = round(adjusted_sl, digits)
    if adjusted_tp is not None:
        adjusted_tp = round(adjusted_tp, digits)

    logging.debug(
        f"SL/TP adjustment - Original: SL={original_sl}, TP={original_tp} | "
        f"Adjusted: SL={adjusted_sl}, TP={adjusted_tp}",
    )

    return adjusted_sl, adjusted_tp


def get_filling_mode(symbol, mt5_module=None):
    """Get appropriate filling mode for the symbol."""
    if mt5_module is None:
        mt5_module = mt5

    # Check for Exness-specific handling first
    if _is_exness_account(mt5_module):
        return mt5_module.ORDER_FILLING_RETURN

    # Get symbol information
    sym_info = _get_symbol_info_for_filling(symbol, mt5_module)
    if not sym_info:
        return _get_default_filling_mode(mt5_module)

    # Get filling mode from symbol info
    filling_mode = _extract_filling_mode(sym_info)
    if filling_mode is None:
        return _get_default_filling_mode(mt5_module)

    # Determine best available filling mode
    return _determine_best_filling_mode(filling_mode, mt5_module)


def _is_exness_account(mt5_module):
    """Check if this is an Exness account that requires specific handling."""
    # For Exness accounts, use ORDER_FILLING_RETURN as the primary mode
    # Exness typically uses RETURN mode (mode 0) for most operations
    return hasattr(mt5_module, "ORDER_FILLING_RETURN")


def _get_symbol_info_for_filling(symbol, mt5_module):
    """Get symbol information for filling mode determination."""
    sym = mt5_module.symbol_info(symbol)
    if not sym:
        logging.warning("Symbol %s info not available", symbol)
    return sym


def _get_default_filling_mode(mt5_module):
    """Get default filling mode when symbol info is unavailable."""
    return (
        mt5_module.ORDER_FILLING_RETURN
        if hasattr(mt5_module, "ORDER_FILLING_RETURN")
        else 0
    )


def _extract_filling_mode(sym_info):
    """Extract filling mode from symbol information."""
    try:
        return getattr(sym_info, "filling_mode", None)
    except AttributeError:
        return None


def _determine_best_filling_mode(filling_mode, mt5_module):
    """Determine the best available filling mode based on symbol capabilities."""
    try:
        # Try FOK first (Fill or Kill)
        if _supports_filling_mode(mt5_module, "ORDER_FILLING_FOK", filling_mode):
            return mt5_module.ORDER_FILLING_FOK

        # Try IOC next (Immediate or Cancel)
        if _supports_filling_mode(mt5_module, "ORDER_FILLING_IOC", filling_mode):
            return mt5_module.ORDER_FILLING_IOC

        # Try RETURN as fallback (Return if not filled)
        if _supports_filling_mode(mt5_module, "ORDER_FILLING_RETURN", filling_mode):
            return mt5_module.ORDER_FILLING_RETURN

    except Exception as e:
        logging.debug("Error checking filling mode: %s", e)

    # Default fallback
    logging.warning("Using default ORDER_FILLING_RETURN")
    return _get_default_filling_mode(mt5_module)


def _supports_filling_mode(mt5_module, mode_attr, filling_mode):
    """Check if a specific filling mode is supported."""
    if hasattr(mt5_module, mode_attr):
        mode_value = getattr(mt5_module, mode_attr)
        return filling_mode & mode_value
    return False


def normalize_volume(symbol, requested_volume, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5

    info = mt5_module.symbol_info(symbol)
    if not info:
        logging.error("Symbol %s info not available", symbol)
        return requested_volume

    volume_min = getattr(info, "volume_min", 0.01) or 0.01
    volume_step = getattr(info, "volume_step", 0.01) or 0.01
    volume_max = getattr(info, "volume_max", 100.0)

    normalized = max(volume_min, round(requested_volume / volume_step) * volume_step)

    if volume_max and normalized > volume_max:
        normalized = volume_max

    return float(normalized)
