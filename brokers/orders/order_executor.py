"""
MT5 Order Executor
Handles order placement and execution with proper error handling
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import MetaTrader5 as mt5  # type: ignore

from brokers.mt5_core import (
    mt5_performance_monitor as performance_monitor,
)
from brokers.mt5_core import (
    validate_and_adjust_stops,
)
from services.error_handler import retry_with_exponential_backoff, safe_mt5_call


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def build_and_send_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 30,
    retries: int = 1,
    magic: int = 123456,
    mt5_module: Any = None,
) -> Any:
    """
    Build and send an order with SL/TP, with retry logic and error handling.

    Args:
        symbol: Trading symbol
        side: "BUY" or "SELL"
        volume: Lot size
        sl: Stop loss price (optional)
        tp: Take profit price (optional)
        deviation: Price deviation in points
        retries: Number of retry attempts
        magic: Magic number for order identification
        mt5_module: MT5 module instance

    Returns:
        Order result or None if failed

    """
    if mt5_module is None:
        mt5_module = mt5

    # Validate inputs
    if not symbol or not side or volume <= 0:
        logging.error(
            f"Invalid parameters for order: symbol={symbol}, side={side}, volume={volume}",
        )
        return None

    # Select symbol
    if not mt5_module.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol}")
        return None

    # Determine order type
    if side == "BUY":
        order_type = mt5_module.ORDER_TYPE_BUY  # type: ignore
    elif side == "SELL":
        order_type = mt5_module.ORDER_TYPE_SELL  # type: ignore
    else:
        logging.error(f"Invalid order side: {side}")
        return None

    # Get current price
    tick = mt5_module.symbol_info_tick(symbol)  # type: ignore
    if tick is None:
        logging.error(f"Failed to get tick data for {symbol}")
        return None

    price = tick.ask if side == "BUY" else tick.bid

    # Try different filling modes
    filling_modes_to_try = [
        mt5_module.ORDER_FILLING_FOK,  # type: ignore
        mt5_module.ORDER_FILLING_IOC,  # type: ignore
        mt5_module.ORDER_FILLING_RETURN,  # type: ignore
    ]

    last_result = None
    attempts_made = 0
    max_total_attempts = retries * len(filling_modes_to_try)

    # Try each filling mode
    for _filling_mode in filling_modes_to_try:
        if attempts_made >= max_total_attempts:
            break

        # Try with SL/TP first
        request = {
            "action": mt5_module.TRADE_ACTION_DEAL,  # type: ignore
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": deviation,
            "magic": magic,
            "comment": "bot_order",
            "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
            "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
        }

        # Add SL/TP if provided
        if sl is not None:
            request["sl"] = float(sl)
        if tp is not None:
            request["tp"] = float(tp)

        # Try this filling mode for the specified number of retries
        for attempt_in_mode in range(1, retries + 1):
            attempts_made += 1
            if attempts_made > max_total_attempts:
                break

            try:
                result = mt5_module.order_send(request)  # type: ignore
            except Exception:
                logging.exception(
                    "Exception en order_send (modo=%s, intento %d)",
                    _filling_mode,
                    attempt_in_mode,
                )
                result = None

            if (
                result
                and getattr(result, "retcode", None) == mt5_module.TRADE_RETCODE_DONE
            ):  # type: ignore
                logging.info(
                    "Orden enviada exitosamente. Ticket: %s",
                    getattr(result, "order", "N/A"),
                )
                return result

            last_result = result
            retcode = getattr(result, "retcode", "N/A") if result else "N/A"
            comment = getattr(result, "comment", "N/A") if result else "N/A"
            logging.warning(
                "Intento %d/%d (modo=%s) fallo: retcode=%s, comment=%s",
                attempts_made,
                max_total_attempts,
                _filling_mode,
                retcode,
                comment,
            )

            # If we get "Invalid stops" error, try a different approach
            if retcode == 10016:  # Invalid stops
                logging.warning("Invalid stops detected, trying alternative approach")

                # Approach 1: Place order without SL/TP first, then modify
                request_no_stops = request.copy()
                request_no_stops.pop("sl", None)
                request_no_stops.pop("tp", None)

                try:
                    result_no_stops = mt5_module.order_send(request_no_stops)  # type: ignore
                    if (
                        result_no_stops
                        and getattr(result_no_stops, "retcode", None)
                        == mt5_module.TRADE_RETCODE_DONE
                    ):  # type: ignore
                        order_ticket = getattr(result_no_stops, "order", None)
                        if order_ticket:
                            logging.info(
                                "Orden enviada sin SL/TP. Ticket: %s", order_ticket,
                            )

                            # Now try to modify the order to add SL/TP
                            if sl is not None or tp is not None:
                                # Try multiple attempts to set SL/TP
                                max_modification_attempts = 3
                                for mod_attempt in range(
                                    1, max_modification_attempts + 1,
                                ):
                                    modification_request = {
                                        "action": mt5_module.TRADE_ACTION_SLTP,  # type: ignore
                                        "symbol": symbol,
                                        "position": int(order_ticket),
                                        "deviation": deviation,
                                        "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
                                        "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
                                    }

                                    # Use potentially adjusted SL/TP values
                                    current_sl = sl
                                    current_tp = tp

                                    # For subsequent attempts, use adjusted values
                                    if mod_attempt > 1:
                                        current_sl, current_tp = (
                                            validate_and_adjust_stops(
                                                symbol, price, sl, tp, side, mt5_module,
                                            )
                                        )
                                        logging.info(
                                            "Attempt %d with adjusted SL/TP: SL=%s, TP=%s",
                                            mod_attempt,
                                            current_sl,
                                            current_tp,
                                        )

                                    if current_sl is not None:
                                        modification_request["sl"] = float(current_sl)
                                    if current_tp is not None:
                                        modification_request["tp"] = float(current_tp)

                                    modification_result = mt5_module.order_send(
                                        modification_request,
                                    )  # type: ignore
                                    if (
                                        modification_result
                                        and getattr(
                                            modification_result, "retcode", None,
                                        )
                                        == mt5_module.TRADE_RETCODE_DONE
                                    ):  # type: ignore
                                        logging.info(
                                            "SL/TP modificados exitosamente para orden %s",
                                            order_ticket,
                                        )
                                        break  # Success, exit retry loop
                                    else:
                                        mod_retcode = (
                                            getattr(
                                                modification_result, "retcode", "N/A",
                                            )
                                            if modification_result
                                            else "N/A"
                                        )
                                        mod_comment = (
                                            getattr(
                                                modification_result, "comment", "N/A",
                                            )
                                            if modification_result
                                            else "N/A"
                                        )
                                        logging.warning(
                                            "Attempt %d failed to modify SL/TP: retcode=%s, comment=%s",
                                            mod_attempt,
                                            mod_retcode,
                                            mod_comment,
                                        )

                                        # Wait before retrying
                                        if mod_attempt < max_modification_attempts:
                                            time.sleep(
                                                0.5 * (2 ** (mod_attempt - 1)),
                                            )  # Exponential backoff
                                else:
                                    # All modification attempts failed
                                    logging.warning(
                                        "La orden %s se ejecutó sin SL/TP después de %d intentos. Deberás gestionarla manualmente.",
                                        order_ticket,
                                        max_modification_attempts,
                                    )

                            return result_no_stops
                        logging.warning("No se pudo obtener el ticket de la orden")
                    else:
                        retcode_no_stops = (
                            getattr(result_no_stops, "retcode", "N/A")
                            if result_no_stops
                            else "N/A"
                        )
                        comment_no_stops = (
                            getattr(result_no_stops, "comment", "N/A")
                            if result_no_stops
                            else "N/A"
                        )
                        logging.warning(
                            "Intento sin SL/TP fallo: retcode=%s, comment=%s",
                            retcode_no_stops,
                            comment_no_stops,
                        )
                except Exception:
                    logging.exception("Exception en order_send sin SL/TP o modificando")

            # Wait before retrying with different filling mode
            if attempt_in_mode < retries:
                time.sleep(0.5 * (2 ** (attempt_in_mode - 1)))  # Exponential backoff

    logging.error(
        "Error al enviar orden %s %s despues de %d intentos. Ultimo resultado: %s",
        side,
        symbol,
        attempts_made,
        last_result,
    )
    return last_result


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def place_pending_order(
    symbol: str,
    order_type: str,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 30,
    expiration_hours: int = 4,
    magic: int = 123456,
    mt5_module: Any = None,
) -> Any:
    """
    Place a pending order (Buy Stop or Sell Stop) with optional SL/TP and expiration.

    Args:
        symbol: Trading symbol
        order_type: "BUY_STOP" or "SELL_STOP"
        volume: Lot size
        price: Order price
        sl: Stop loss price (optional)
        tp: Take profit price (optional)
        deviation: Price deviation in points
        expiration_hours: Hours until order expires (default 4 hours)
        magic: Magic number for order identification
        mt5_module: MT5 module instance

    Returns:
        Order result or None if failed

    """
    if mt5_module is None:
        mt5_module = mt5

    # Validate inputs
    if not symbol or not order_type or volume <= 0 or price <= 0:
        logging.error(
            f"Invalid parameters for pending order: symbol={symbol}, type={order_type}, volume={volume}, price={price}",
        )
        return None

    # Select symbol
    if not mt5_module.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol} for pending order")
        return None

    # Determine order type
    if order_type == "BUY_STOP":
        order_type_mt5 = mt5_module.ORDER_TYPE_BUY_STOP  # type: ignore
    elif order_type == "SELL_STOP":
        order_type_mt5 = mt5_module.ORDER_TYPE_SELL_STOP  # type: ignore
    else:
        logging.error(f"Invalid order type for pending order: {order_type}")
        return None

    # Calculate expiration time (4 hours from now)
    expiration_time = int(
        (datetime.now() + timedelta(hours=expiration_hours)).timestamp(),
    )

    # Prepare order request
    request = {
        "action": mt5_module.TRADE_ACTION_PENDING,  # type: ignore
        "symbol": symbol,
        "volume": float(volume),
        "type": order_type_mt5,
        "price": float(price),
        "deviation": deviation,
        "magic": magic,
        "comment": f"pending_{order_type.lower()}",
        "type_time": mt5_module.ORDER_TIME_SPECIFIED,  # type: ignore
        "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
        "expiration": expiration_time,
    }

    # Add SL/TP if provided
    if sl is not None and sl > 0:
        request["sl"] = float(sl)
    if tp is not None and tp > 0:
        request["tp"] = float(tp)

    # Send order
    try:
        result = mt5_module.order_send(request)  # type: ignore

        if result and getattr(result, "retcode", None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
            logging.info(
                f"Pending order placed successfully: {order_type} {symbol} @ {price}",
            )
            logging.info(f"Order ticket: {getattr(result, 'order', 'N/A')}")
            return result
        retcode = getattr(result, "retcode", "N/A") if result else "N/A"
        comment = getattr(result, "comment", "N/A") if result else "N/A"
        logging.error(
            f"Failed to place pending order: retcode={retcode}, comment={comment}",
        )
        return None
    except Exception as e:
        logging.exception(f"Exception placing pending order: {e!s}")
        return None


@performance_monitor
@safe_mt5_call
def cancel_expired_pending_orders(magic: int = 123456, mt5_module: Any = None) -> None:
    """
    Cancel pending orders that have expired (older than 4 hours).

    Args:
        magic: Magic number to filter orders
        mt5_module: MT5 module instance

    """
    if mt5_module is None:
        mt5_module = mt5

    # Get all pending orders
    orders = mt5_module.orders_get()  # type: ignore
    if not orders:
        return

    # Current time for comparison
    current_time = datetime.now().timestamp()

    for order in orders:
        # Check if order matches our magic number
        if getattr(order, "magic", 0) == magic:
            # Check if order has expiration time
            expiration = getattr(order, "expiration", 0)
            if expiration > 0 and current_time > expiration:
                # Cancel expired order
                request = {
                    "action": mt5_module.TRADE_ACTION_REMOVE,  # type: ignore
                    "order": int(order.ticket),
                    "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
                    "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
                }

                try:
                    result = mt5_module.order_send(request)  # type: ignore
                    if (
                        result
                        and getattr(result, "retcode", None)
                        == mt5_module.TRADE_RETCODE_DONE
                    ):  # type: ignore
                        logging.info(
                            f"Expired pending order {order.ticket} cancelled successfully",
                        )
                    else:
                        retcode = getattr(result, "retcode", "N/A") if result else "N/A"
                        comment = getattr(result, "comment", "N/A") if result else "N/A"
                        logging.warning(
                            f"Failed to cancel expired order {order.ticket}: retcode={retcode}, comment={comment}",
                        )
                except Exception as e:
                    logging.exception(
                        f"Exception cancelling expired order {order.ticket}: {e!s}",
                    )
