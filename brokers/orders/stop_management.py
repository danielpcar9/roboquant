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

    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return

    for pos in positions:
        try:
            # Get symbol info
            symbol_info = mt5_module.symbol_info(pos.symbol)  # type: ignore
            if not symbol_info:
                continue

            point = symbol_info.point

            # Adjust point value for NASDAQ
            if "NASDAQ" in pos.symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices

            # Calculate trailing stop distance (example: 50 points)
            trailing_distance = 50 * point

            current_price = (
                mt5_module.symbol_info_tick(pos.symbol).bid  # type: ignore
                if pos.type == mt5_module.POSITION_TYPE_BUY  # type: ignore
                else mt5_module.symbol_info_tick(pos.symbol).ask  # type: ignore
            )

            # Calculate new stop loss based on position type
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

        except Exception as e:
            logging.exception(f"Error updating trailing stop for position {pos.ticket}: {e}")


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

    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        logging.info("No positions to monitor")
        return

    updated_count = 0
    error_count = 0

    for pos in positions:
        try:
            # Skip if no SL set initially
            if pos.sl == 0:
                continue

            symbol_info = mt5_module.symbol_info(pos.symbol)  # type: ignore
            if not symbol_info:
                continue

            point = symbol_info.point
            # Adjust point value for NASDAQ
            if "NASDAQ" in pos.symbol.upper():
                point = 1.0

            tick = mt5_module.symbol_info_tick(pos.symbol)  # type: ignore
            if not tick:
                continue

            current_price = tick.bid if pos.type == mt5_module.POSITION_TYPE_BUY else tick.ask  # type: ignore

            # Calculate required move for trailing stop update
            min_move = 20 * point  # Minimum 20 points move

            should_update = False
            new_sl = pos.sl

            if pos.type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
                # For long positions, update SL if price moved up significantly
                if current_price > pos.price_current + min_move:
                    # Move SL to breakeven plus buffer
                    breakeven = pos.price_open
                    buffer = 10 * point
                    new_sl = max(pos.sl, breakeven + buffer)
                    should_update = new_sl > pos.sl
            else:  # SELL position
                # For short positions, update SL if price moved down significantly
                if current_price < pos.price_current - min_move:
                    # Move SL to breakeven minus buffer
                    breakeven = pos.price_open
                    buffer = 10 * point
                    new_sl = min(pos.sl, breakeven - buffer)
                    should_update = new_sl < pos.sl

            if should_update:
                success = _modify_position_sl(pos.ticket, new_sl, mt5_module)
                if success:
                    updated_count += 1
                    logging.info(
                        f"Updated SL for position {pos.ticket}: {pos.sl:.5f} -> {new_sl:.5f}",
                    )
                else:
                    error_count += 1

        except Exception as e:
            logging.exception(f"Error monitoring position {pos.ticket}: {e}")
            error_count += 1

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
                # Try to modify position
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

                # If we still have something to set
                if "sl" in modification_request or "tp" in modification_request:
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
                            return True
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
                            logging.warning(
                                "Invalid stops detected for position %s, trying with adjusted levels",
                                ticket,
                            )
                            adjusted_sl, adjusted_tp = (
                                validate_and_adjust_stops(
                                    symbol,
                                    entry_price,
                                    sl_price,
                                    tp_price,
                                    side,
                                    mt5_module,
                                )
                            )
                            if (
                                adjusted_sl != sl_price
                                or adjusted_tp != tp_price
                            ):
                                logging.info(
                                    "Retrying with adjusted SL/TP: SL=%s, TP=%s",
                                    adjusted_sl,
                                    adjusted_tp,
                                )
                                sl_price, tp_price = adjusted_sl, adjusted_tp
                    except Exception:
                        logging.exception(
                            f"Exception while adding SL/TP to position {ticket} (attempt {attempt})",
                        )
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
