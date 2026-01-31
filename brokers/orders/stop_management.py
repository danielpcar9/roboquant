"""
MT5 Stop Management
Handles trailing stops and stop loss/take profit updates
"""

import logging
from typing import Any

import MetaTrader5 as mt5  # type: ignore

from brokers.mt5_core import (
    mt5_performance_monitor as performance_monitor,
)
from brokers.mt5_core import (
    validate_and_adjust_stops,
)
from services.error_handler import safe_mt5_call


@performance_monitor
@safe_mt5_call
def update_trailing_stops(mt5_module: Any = None) -> None:
    """
    Update trailing stops for all open positions.

    Args:
        mt5_module: MT5 module instance
    """
    if mt5_module is None:
        mt5_module = mt5

    positions = _get_open_positions(mt5_module)
    if not positions:
        return

    _process_positions_for_trailing_stops(positions, mt5_module)


def _get_open_positions(mt5_module):
    """Get all open positions from MT5."""
    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return None
    return positions


def _process_positions_for_trailing_stops(positions, mt5_module):
    """Process each position for trailing stop updates."""
    for pos in positions:
        try:
            _update_single_position_trailing_stop(pos, mt5_module)
        except Exception as e:
            logging.exception(f"Error updating trailing stop for position {pos.ticket}: {e}")


def _update_single_position_trailing_stop(pos, mt5_module):
    """Update trailing stop for a single position."""
    # Get symbol information
    symbol_info = _get_symbol_info_for_position(pos.symbol, mt5_module)
    if not symbol_info:
        return

    point = _calculate_point_value(pos.symbol, symbol_info)

    # Calculate trailing stop distance
    trailing_distance = 50 * point

    # Get current market price
    current_price = _get_current_price(pos, mt5_module)

    # Calculate and update stop loss
    _calculate_and_update_stop_loss(pos, current_price, trailing_distance, mt5_module)


def _get_symbol_info_for_position(symbol, mt5_module):
    """Get symbol information for a position."""
    symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        return None
    return symbol_info


def _calculate_point_value(symbol, symbol_info):
    """Calculate point value for the symbol."""
    point = symbol_info.point
    # Adjust point value for NASDAQ
    if "NASDAQ" in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    return point


def _get_current_price(pos, mt5_module):
    """Get current market price for the position."""
    return (
        mt5_module.symbol_info_tick(pos.symbol).bid  # type: ignore
        if pos.type == mt5_module.POSITION_TYPE_BUY  # type: ignore
        else mt5_module.symbol_info_tick(pos.symbol).ask  # type: ignore
    )


def _calculate_and_update_stop_loss(pos, current_price, trailing_distance, mt5_module):
    """Calculate new stop loss and update if better than current."""
    if pos.type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
        new_sl = current_price - trailing_distance
        # Only update if new SL is better than current SL
        if pos.sl == 0 or new_sl > pos.sl:
            _modify_position_sl(pos.ticket, new_sl, mt5_module)
    elif pos.type == mt5_module.POSITION_TYPE_SELL:  # type: ignore
        new_sl = current_price + trailing_distance
        # Only update if new SL is better than current SL
        if pos.sl == 0 or new_sl < pos.sl:
            _modify_position_sl(pos.ticket, new_sl, mt5_module)


@performance_monitor
@safe_mt5_call
def monitor_and_update_stops(mt5_module: Any = None) -> None:
    """
    Monitor and update stops for all positions.
    This is a more comprehensive version that handles various stop scenarios.

    Args:
        mt5_module: MT5 module instance

    """
    if mt5_module is None:
        mt5_module = mt5

    # Get all open positions
    positions = _get_open_positions_for_monitoring(mt5_module)
    if not positions:
        logging.info("No positions to monitor")
        return

    # Process positions for stop updates
    updated_count, error_count = _process_positions_for_stop_updates(positions, mt5_module)

    # Log monitoring results
    _log_monitoring_results(updated_count, error_count)


def _get_open_positions_for_monitoring(mt5_module):
    """Get all open positions from MT5 for monitoring."""
    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return None
    return positions


def _process_positions_for_stop_updates(positions, mt5_module):
    """Process each position for stop loss updates."""
    updated_count = 0
    error_count = 0

    for pos in positions:
        try:
            position_updated, position_error = _process_single_position_stop_update(pos, mt5_module)
            updated_count += position_updated
            error_count += position_error
        except Exception as e:
            logging.exception(f"Error monitoring position {pos.ticket}: {e}")
            error_count += 1

    return updated_count, error_count


def _process_single_position_stop_update(pos, mt5_module):
    """Process stop update logic for a single position."""
    # Skip if no SL set initially
    if pos.sl == 0:
        return 0, 0

    # Get symbol information
    symbol_info = _get_symbol_info_for_position(pos.symbol, mt5_module)
    if not symbol_info:
        return 0, 0

    # Get current market data
    tick = _get_tick_data_for_position(pos.symbol, mt5_module)
    if not tick:
        return 0, 0

    # Calculate point value
    point = _calculate_point_value(pos.symbol, symbol_info)

    # Get current price based on position type
    current_price = _get_current_price_by_position_type(pos, tick, mt5_module)

    # Determine if stop should be updated
    should_update, new_sl = _should_update_stop_loss(pos, current_price, point, mt5_module)

    if should_update:
        success = _modify_position_sl(pos.ticket, new_sl, mt5_module)
        if success:
            logging.info(
                f"Updated SL for position {pos.ticket}: {pos.sl:.5f} -> {new_sl:.5f}",
            )
            return 1, 0
        else:
            return 0, 1
    else:
        return 0, 0


def _get_symbol_info_for_position(symbol, mt5_module):
    """Get symbol information for a position."""
    symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        return None
    return symbol_info


def _get_tick_data_for_position(symbol, mt5_module):
    """Get tick data for a position."""
    tick = mt5_module.symbol_info_tick(symbol)  # type: ignore
    if not tick:
        return None
    return tick


def _calculate_point_value(symbol, symbol_info):
    """Calculate point value for the symbol."""
    point = symbol_info.point
    # Adjust point value for NASDAQ
    if "NASDAQ" in symbol.upper():
        point = 1.0
    return point


def _get_current_price_by_position_type(pos, tick, mt5_module):
    """Get current price based on position type."""
    return tick.bid if pos.type == mt5_module.POSITION_TYPE_BUY else tick.ask  # type: ignore


def _should_update_stop_loss(pos, current_price, point, mt5_module):
    """Determine if stop loss should be updated and calculate new value."""
    # Calculate required move for trailing stop update
    min_move = 20 * point  # Minimum 20 points move

    should_update = False
    new_sl = pos.sl

    if pos.type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
        # For long positions, update SL if price moved up significantly
        should_update, new_sl = _evaluate_buy_position_stop_update(
            pos, current_price, min_move, point
        )
    else:  # SELL position
        # For short positions, update SL if price moved down significantly
        should_update, new_sl = _evaluate_sell_position_stop_update(
            pos, current_price, min_move, point
        )

    return should_update, new_sl


def _evaluate_buy_position_stop_update(pos, current_price, min_move, point):
    """Evaluate stop update for BUY positions."""
    should_update = False
    new_sl = pos.sl

    if current_price > pos.price_current + min_move:
        # Move SL to breakeven plus buffer
        breakeven = pos.price_open
        buffer = 10 * point
        new_sl = max(pos.sl, breakeven + buffer)
        should_update = new_sl > pos.sl

    return should_update, new_sl


def _evaluate_sell_position_stop_update(pos, current_price, min_move, point):
    """Evaluate stop update for SELL positions."""
    should_update = False
    new_sl = pos.sl

    if current_price < pos.price_current - min_move:
        # Move SL to breakeven minus buffer
        breakeven = pos.price_open
        buffer = 10 * point
        new_sl = min(pos.sl, breakeven - buffer)
        should_update = new_sl < pos.sl

    return should_update, new_sl


def _log_monitoring_results(updated_count, error_count):
    """Log monitoring completion results."""
    if updated_count > 0 or error_count > 0:
        logging.info(
            f"Stop monitoring complete: {updated_count} updated, {error_count} errors",
        )


def _modify_position_sl(
    ticket: int, new_sl: float, mt5_module: Any = None,
) -> bool:
    """
    Modify position stop loss.

    Args:
        ticket: Position ticket number
        new_sl: New stop loss price
        mt5_module: MT5 module instance

    Returns:
        bool: True if successful, False otherwise

    """
    if mt5_module is None:
        mt5_module = mt5

    request = {
        "action": mt5_module.TRADE_ACTION_SLTP,  # type: ignore
        "position": int(ticket),
        "sl": float(new_sl),
        "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
        "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
    }

    try:
        result = mt5_module.order_send(request)  # type: ignore
        if (
            result
            and getattr(result, "retcode", None) == mt5_module.TRADE_RETCODE_DONE
        ):  # type: ignore
            return True
        retcode = getattr(result, "retcode", "N/A") if result else "N/A"
        comment = getattr(result, "comment", "N/A") if result else "N/A"
        logging.warning(
            f"Failed to modify SL for position {ticket}: retcode={retcode}, comment={comment}",
        )
        return False
    except Exception as e:
        logging.exception(f"Exception modifying SL for position {ticket}: {e}")
        return False


@performance_monitor
@safe_mt5_call
def _create_modification_request(ticket: int, symbol: str, sl_price: float | None, tp_price: float | None, mt5_module: Any) -> dict:
    """Create the modification request for adding SL/TP to position"""
    modification_request = {
        "action": mt5_module.TRADE_ACTION_SLTP,  # type: ignore
        "symbol": symbol,
        "position": int(ticket),
        "sl": float(sl_price) if sl_price is not None else 0,
        "tp": float(tp_price) if tp_price is not None else 0,
        "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
        "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
    }

    # Remove zero values
    if modification_request["sl"] == 0:
        modification_request.pop("sl")
    if modification_request["tp"] == 0:
        modification_request.pop("tp")

    return modification_request


def _handle_invalid_stops_error(
    symbol: str,
    entry_price: float,
    sl_price: float | None,
    tp_price: float | None,
    side: str,
    ticket: int,
    mt5_module: Any
) -> tuple[float | None, float | None]:
    """Handle invalid stops error by adjusting the stops"""
    logging.warning(
        "Invalid stops detected for position %s, trying with adjusted levels",
        ticket,
    )
    adjusted_sl, adjusted_tp = validate_and_adjust_stops(
        symbol,
        entry_price,
        sl_price,
        tp_price,
        side,
        mt5_module,
    )
    if adjusted_sl != sl_price or adjusted_tp != tp_price:
        logging.info(
            "Retrying with adjusted SL/TP: SL=%s, TP=%s",
            adjusted_sl,
            adjusted_tp,
        )
    return adjusted_sl, adjusted_tp


def _process_add_sl_tp_attempt(
    modification_request: dict,
    ticket: int,
    attempt: int,
    symbol: str,
    entry_price: float,
    sl_price: float | None,
    tp_price: float | None,
    side: str,
    mt5_module: Any
) -> tuple[bool, float | None, float | None]:
    """Process a single attempt to add SL/TP to position"""
    try:
        result = mt5_module.order_send(modification_request)  # type: ignore
        if (
            result
            and getattr(result, "retcode", None)
            == mt5_module.TRADE_RETCODE_DONE
        ):  # type: ignore
            logging.info(
                f"SL/TP added successfully to position {ticket}",
            )
            return True, sl_price, tp_price
        retcode = (
            getattr(result, "retcode", "N/A")
            if result
            else "N/A"
        )
        comment = (
            getattr(result, "comment", "N/A")
            if result
            else "N/A"
        )
        logging.warning(
            f"Attempt {attempt} failed to add SL/TP to position {ticket}: retcode={retcode}, comment={comment}",
        )

        # If we get "Invalid stops" error, try with adjusted stops
        if retcode == 10016:  # Invalid stops
            adjusted_sl, adjusted_tp = _handle_invalid_stops_error(
                symbol, entry_price, sl_price, tp_price, side, ticket, mt5_module
            )
            return False, adjusted_sl, adjusted_tp

        return False, sl_price, tp_price
    except Exception:
        logging.exception(
            f"Exception while adding SL/TP to position {ticket} (attempt {attempt})",
        )
        return False, sl_price, tp_price


def add_sl_tp_to_position(
    ticket: int,
    symbol: str,
    entry_price: float,
    sl_price: float | None,
    tp_price: float | None,
    side: str,
    mt5_module: Any = None,
) -> bool:
    """
    Add SL/TP to an existing position that was opened without them.

    Args:
        ticket: Position ticket
        symbol: Trading symbol
        entry_price: Entry price
        sl_price: Stop loss price (optional)
        tp_price: Take profit price (optional)
        side: "BUY" or "SELL"
        mt5_module: MT5 module instance

    Returns:
        bool: True if successful, False otherwise

    """
    if mt5_module is None:
        mt5_module = mt5

    # Validate inputs
    if sl_price is None and tp_price is None:
        logging.warning(f"No SL/TP to add to position {ticket}")
        return False

    try:
        # Try each filling mode with retries
        filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore
        max_retries = 1

        for _filling_mode in filling_modes_to_try:
            for attempt in range(1, max_retries + 1):
                # Create modification request
                modification_request = _create_modification_request(
                    ticket, symbol, sl_price, tp_price, mt5_module
                )

                # If we still have something to set
                if "sl" in modification_request or "tp" in modification_request:
                    success, sl_price, tp_price = _process_add_sl_tp_attempt(
                        modification_request,
                        ticket,
                        attempt,
                        symbol,
                        entry_price,
                        sl_price,
                        tp_price,
                        side,
                        mt5_module
                    )

                    if success:
                        return True
                else:
                    logging.warning(f"No valid SL/TP to add to position {ticket}")
                    return False

                # Wait before retrying
                if attempt < max_retries:
                    import time
                    time.sleep(0.5 * (2 ** (attempt - 1)))  # Exponential backoff

        logging.error(
            f"Failed to add SL/TP to position {ticket} after all attempts",
        )
        return False

    except Exception as e:
        logging.exception(f"Exception in add_sl_tp_to_position: {e}")
        return False
