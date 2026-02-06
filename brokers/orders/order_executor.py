"""
MT5 Order Executor
Handles order placement and execution with proper error handling
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from brokers.mt5_core import (
    mt5_performance_monitor as performance_monitor,
)
from core.mt5_compat import mt5
from services.error_handler import retry_with_exponential_backoff, safe_mt5_call


def _build_base_order_request(symbol: str, volume: float, order_type: Any, price: float, deviation: int, magic: int, mt5_module: Any):
    """Build base order request dictionary."""
    return {
        "action": mt5_module.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": "bot_order",
        "type_time": mt5_module.ORDER_TIME_GTC,
        "type_filling": mt5_module.ORDER_FILLING_FOK,
    }


def _add_stop_levels_to_request(request: dict, sl: float | None, tp: float | None):
    """Add stop loss and take profit to request if provided."""
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp


def _execute_order_with_retry_strategy(request: dict, symbol: str, side: str, price: float, sl: float | None, tp: float | None, retries: int, mt5_module: Any):
    """Execute order with retry strategy."""
    # Try different filling modes
    filling_modes_to_try = [
        mt5_module.ORDER_FILLING_FOK,
        mt5_module.ORDER_FILLING_IOC,
        mt5_module.ORDER_FILLING_RETURN,
    ]

    last_result = None
    attempts_made = 0
    max_total_attempts = retries * len(filling_modes_to_try)

    # Try each filling mode
    for _filling_mode in filling_modes_to_try:
        if attempts_made >= max_total_attempts:
            break

        # Update filling mode in request
        request["type_filling"] = _filling_mode

        try:
            result = mt5_module.order_send(request)
        except Exception:
            logging.exception(
                "Exception en order_send (modo=%s, intento %d)",
                _filling_mode,
                attempts_made + 1,
            )
            result = None

        if result is not None:
            if result.retcode == mt5_module.TRADE_RETCODE_DONE:
                logging.info(f"Orden ejecutada: {side} {symbol} @ {price}")

                # If we have SL/TP to add, do it separately
                if sl is not None or tp is not None:
                    # Get the ticket from the result
                    ticket = result.order
                    if ticket:
                        # Add SL/TP separately if they weren't included in the original order
                        from .stop_management import add_sl_tp_to_position
                        success = add_sl_tp_to_position(
                            ticket, symbol, price, sl, tp, side, mt5_module
                        )
                        if success:
                            logging.info(f"SL/TP agregados a la posición {ticket}")

                return result

            # Log failure
            retcode = getattr(result, "retcode", "N/A")
            comment = getattr(result, "comment", "N/A")
            logging.warning(
                "Intento %d/%d (modo=%s) fallo: retcode=%s, comment=%s",
                attempts_made + 1,
                max_total_attempts,
                _filling_mode,
                retcode,
                comment,
            )

            attempts_made += 1
        else:
            logging.error(f"Result is None for order {symbol}")
            attempts_made += 1

    logging.error(
        f"Fallo al enviar orden {side} {symbol} despues de {attempts_made} intentos. Ultimo resultado: {last_result}"
    )
    return last_result


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

    # Determine order type
    if side == "BUY":
        order_type = mt5_module.ORDER_TYPE_BUY
    elif side == "SELL":
        order_type = mt5_module.ORDER_TYPE_SELL
    else:
        logging.error(f"Invalid side: {side}")
        return None

    # Get current price
    tick = mt5_module.symbol_info_tick(symbol)
    if tick is None:
        logging.error(f"Failed to get tick data for {symbol}")
        return None

    if side == "BUY":
        price = tick.ask
    else:
        price = tick.bid

    # Build order request
    request = _build_base_order_request(
        symbol, volume, order_type, price, deviation, magic, mt5_module
    )

    # Add stop levels if provided
    _add_stop_levels_to_request(request, sl, tp)

    # Execute with retry strategy
    return _execute_order_with_retry_strategy(
        request, symbol, side, price, sl, tp, retries, mt5_module
    )


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def place_pending_order(
    symbol: str,
    order_type: Any,
    volume: float,
    price: float,
    sl: float | None = None,
    tp: float | None = None,
    deviation: int = 30,
    expiration_hours: int = 4,
    magic: int = 123456,
    mt5_module: Any = None,
) -> Any:
    """Place a pending order with optional SL/TP."""
    if mt5_module is None:
        mt5_module = mt5

    # Determine MT5 order type based on string
    if order_type == "BUY_LIMIT":
        mt5_order_type = mt5_module.ORDER_TYPE_BUY_LIMIT
    elif order_type == "SELL_LIMIT":
        mt5_order_type = mt5_module.ORDER_TYPE_SELL_LIMIT
    elif order_type == "BUY_STOP":
        mt5_order_type = mt5_module.ORDER_TYPE_BUY_STOP
    elif order_type == "SELL_STOP":
        mt5_order_type = mt5_module.ORDER_TYPE_SELL_STOP
    else:
        logging.error(f"Invalid order type: {order_type}")
        return None

    # Calculate expiration time
    expiration = datetime.now() + timedelta(hours=expiration_hours)

    # Build request
    request = {
        "action": mt5_module.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": mt5_order_type,
        "price": price,
        "deviation": deviation,
        "magic": magic,
        "comment": "bot_pending_order",
        "type_time": mt5_module.ORDER_TIME_SPECIFIED,
        "expiration": expiration,
        "type_filling": mt5_module.ORDER_FILLING_FOK,
    }

    # Add stop levels if provided
    if sl is not None:
        request["sl"] = sl
    if tp is not None:
        request["tp"] = tp

    # Send order
    result = mt5_module.order_send(request)
    if result is not None and result.retcode == mt5_module.TRADE_RETCODE_DONE:
        logging.info(f"Pending order placed: {order_type} {symbol} @ {price}")
        return result
    else:
        logging.error(f"Failed to place pending order: {result}")
        return result


@performance_monitor
@safe_mt5_call
def cancel_expired_pending_orders(magic: int = 123456, mt5_module: Any = None) -> int:
    """Cancel pending orders that have expired."""
    if mt5_module is None:
        mt5_module = mt5

    # Get all pending orders
    pending_orders = mt5_module.orders_get()
    if pending_orders is None:
        return 0

    cancelled_count = 0
    current_time = datetime.now()

    for order in pending_orders:
        # Check if it's our magic number
        if order.magic != magic:
            continue

        # Check if order has expiration and if it's expired
        if order.expiration != 0:  # 0 means no expiration
            expiration_time = datetime.fromtimestamp(order.expiration)
            if current_time > expiration_time:
                # Cancel the order
                cancel_request = {
                    "action": mt5_module.TRADE_ACTION_REMOVE,
                    "symbol": order.symbol,
                    "ticket": order.ticket,
                    "type": order.type,
                    "position": order.ticket,
                }

                result = mt5_module.order_send(cancel_request)
                if result is not None and result.retcode == mt5_module.TRADE_RETCODE_DONE:
                    logging.info(f"Cancelled expired pending order: {order.ticket}")
                    cancelled_count += 1
                else:
                    logging.error(f"Failed to cancel order {order.ticket}: {result}")

    return cancelled_count
