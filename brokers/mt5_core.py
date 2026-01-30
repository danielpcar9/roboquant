# mt5_core.py
"""
Core MT5 functionality consolidated in one place to eliminate duplication.
"""

import logging
import time

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5

# Import security manager for credential handling
from services.security_manager import SecureCredentialManager, sanitize_error_message

# Initialize credential manager
credential_manager = SecureCredentialManager()


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
            if not mt5.initialize(login=login_int, password=password, server=server):  # type: ignore
                logging.error("Failed to initialize MT5 with credentials")
                error = mt5.last_error()  # type: ignore
                logging.error(f"MT5 initialization error: {error}")
                return False
        except ValueError as e:
            logging.exception(
                f"Invalid login format: {login}. Error: {sanitize_error_message(str(e))}",
            )
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
            logging.debug(
                f"Strategy Performance: {func.__name__} executed in {execution_time:.4f} seconds",
            )

            # Log average execution time every 10 executions
            if len(strategy_execution_times) % 10 == 0:
                avg_time = sum(strategy_execution_times[-10:]) / min(
                    10, len(strategy_execution_times),
                )
                logging.info(
                    f"Average execution time (last 10): {avg_time:.4f} seconds",
                )

            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.debug(
                f"Strategy Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {e}",
            )
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
            logging.debug(
                f"Performance: {func.__name__} executed in {execution_time:.4f} seconds",
            )
            return result
        except Exception as e:
            end_time = time.perf_counter()
            execution_time = end_time - start_time
            logging.debug(
                f"Performance: {func.__name__} failed after {execution_time:.4f} seconds with error: {e}",
            )
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
    symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
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


def _calculate_buy_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted stop loss for BUY orders."""
    if sl is not None:
        # Ensure SL is at least min_stop_distance below entry
        min_sl = entry_price - (min_stop_distance * point)
        # Make sure SL is not too close to current price
        current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
        safe_sl = min_sl
        if current_price - (min_stop_distance * point) < safe_sl:
            safe_sl = current_price - (min_stop_distance * point)
        return min(sl, safe_sl)  # SL further from entry is safer
    else:
        return None


def _calculate_buy_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted take profit for BUY orders."""
    if tp is not None:
        # Ensure TP is at least min_stop_distance above entry
        min_tp = entry_price + (min_stop_distance * point)
        # Make sure TP is not too close to current price
        current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
        safe_tp = min_tp
        if current_price + (min_stop_distance * point) > safe_tp:
            safe_tp = current_price + (min_stop_distance * point)
        return max(tp, safe_tp)  # TP further from entry is better
    else:
        return None


def _calculate_sell_stop_loss(sl, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted stop loss for SELL orders."""
    if sl is not None:
        # Ensure SL is at least min_stop_distance above entry
        min_sl = entry_price + (min_stop_distance * point)
        # Make sure SL is not too close to current price
        current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
        safe_sl = min_sl
        if current_price + (min_stop_distance * point) > safe_sl:
            safe_sl = current_price + (min_stop_distance * point)
        return max(sl, safe_sl)  # SL further from entry is safer
    else:
        return None


def _calculate_sell_take_profit(tp, entry_price, symbol, min_stop_distance, point, mt5_module):
    """Calculate adjusted take profit for SELL orders."""
    if tp is not None:
        # Ensure TP is at least min_stop_distance below entry
        min_tp = entry_price - (min_stop_distance * point)
        # Make sure TP is not too close to current price
        current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
        safe_tp = min_tp
        if current_price - (min_stop_distance * point) < safe_tp:
            safe_tp = current_price - (min_stop_distance * point)
        return min(tp, safe_tp)  # TP further from entry is better
    else:
        return None


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
        return mt5_module.ORDER_FILLING_RETURN  # type: ignore

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
    return hasattr(mt5_module, "ORDER_FILLING_RETURN")  # type: ignore


def _get_symbol_info_for_filling(symbol, mt5_module):
    """Get symbol information for filling mode determination."""
    sym = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym:
        logging.warning("Symbol %s info not available", symbol)
    return sym


def _get_default_filling_mode(mt5_module):
    """Get default filling mode when symbol info is unavailable."""
    return (
        mt5_module.ORDER_FILLING_RETURN
        if hasattr(mt5_module, "ORDER_FILLING_RETURN")
        else 0
    )  # type: ignore


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
            return mt5_module.ORDER_FILLING_FOK  # type: ignore

        # Try IOC next (Immediate or Cancel)
        if _supports_filling_mode(mt5_module, "ORDER_FILLING_IOC", filling_mode):
            return mt5_module.ORDER_FILLING_IOC  # type: ignore

        # Try RETURN as fallback (Return if not filled)
        if _supports_filling_mode(mt5_module, "ORDER_FILLING_RETURN", filling_mode):
            return mt5_module.ORDER_FILLING_RETURN  # type: ignore

    except Exception as e:
        logging.debug("Error checking filling mode: %s", e)

    # Default fallback
    logging.warning("Using default ORDER_FILLING_RETURN")
    return _get_default_filling_mode(mt5_module)


def _supports_filling_mode(mt5_module, mode_attr, filling_mode):
    """Check if a specific filling mode is supported."""
    if hasattr(mt5_module, mode_attr):  # type: ignore
        mode_value = getattr(mt5_module, mode_attr)  # type: ignore
        return filling_mode & mode_value  # type: ignore
    return False


def normalize_volume(symbol, requested_volume, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5

    info = mt5_module.symbol_info(symbol)  # type: ignore
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
