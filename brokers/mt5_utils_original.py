# mt5_utils.py
import logging
import time
from datetime import datetime, timedelta

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

# Import consolidated performance monitoring
from brokers.mt5_core import mt5_performance_monitor as performance_monitor

# Import consolidated MT5 utility functions
from brokers.mt5_core import normalize_volume, validate_and_adjust_stops

# Import error handling components
from services.error_handler import retry_with_exponential_backoff, safe_mt5_call

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED = True


class MT5Gateway:
    """Object-oriented wrapper around MT5 utility functions.
    Preserves existing behavior by delegating to module-level functions.
    """

    def initialize(self):
        """Initialize MT5 connection"""
        from brokers.mt5_core import initialize_mt5
        return initialize_mt5()

    def shutdown(self):
        """Shutdown MT5 connection"""
        import MetaTrader5 as mt5
        mt5.shutdown()  # type: ignore

    def build_and_send_order(
        self,
        symbol,
        side,
        volume,
        sl=None,
        tp=None,
        deviation=30,
        retries=1,
        magic=123456,
        mt5_module=None,
    ):
        return build_and_send_order(
            symbol, side, volume, sl, tp, deviation, retries, magic, mt5_module,
        )

    def place_pending_order(
        self,
        symbol,
        order_type,
        volume,
        price,
        sl=None,
        tp=None,
        deviation=30,
        expiration_hours=4,
        magic=123456,
        mt5_module=None,
    ):
        return place_pending_order(
            symbol,
            order_type,
            volume,
            price,
            sl,
            tp,
            deviation,
            expiration_hours,
            magic,
            mt5_module,
        )

    def cancel_expired_pending_orders(self, magic=123456, mt5_module=None):
        return cancel_expired_pending_orders(magic, mt5_module)

    def update_trailing_stops(self, mt5_module=None):
        return update_trailing_stops(mt5_module)

    def monitor_and_update_stops(self, mt5_module=None):
        return monitor_and_update_stops(mt5_module)

    def close_position_by_ticket(
        self, ticket, deviation=30, retries=1, mt5_module=None,
    ):
        return close_position_by_ticket(ticket, deviation, retries, mt5_module)

    def get_open_positions(self, mt5_module=None):
        """Get all open positions"""
        if mt5_module is None:
            mt5_module = mt5
        positions = mt5_module.positions_get()
        if positions is None:
            logging.error("Failed to get positions")
            return []
        return positions

    def close_all_positions(self, mt5_module=None):
        """Close all open positions. Returns (closed_count, error_count)"""
        if mt5_module is None:
            mt5_module = mt5

        positions = self.get_open_positions(mt5_module)
        if not positions:
            logging.info("No open positions to close")
            return 0, 0

        closed_count = 0
        error_count = 0

        for position in positions:
            ticket = position.ticket
            try:
                success = self.close_position_by_ticket(ticket, mt5_module=mt5_module)
                if success:
                    closed_count += 1
                else:
                    error_count += 1
            except Exception as e:
                logging.exception(f"Error closing position {ticket}: {e}")
                error_count += 1

        logging.info(f"Closed {closed_count} positions, {error_count} errors")
        return closed_count, error_count


# validate_and_adjust_stops function removed - using consolidated version from mt5_core.py

# performance_monitor function removed - using consolidated version from mt5_core.py

# get_filling_mode function removed - using consolidated version from mt5_core.py

# normalize_volume function removed - using consolidated version from mt5_core.py


@performance_monitor
def estimate_lots_by_risk(symbol, entry_price, stop_price, risk_pct, mt5_module=None):
    """Calculate position size based on risk percentage."""
    if mt5_module is None:
        mt5_module = mt5

    # Get account information
    account_info = _get_account_info(mt5_module)
    if not account_info:
        return _get_default_volume(symbol, mt5_module)

    # Calculate risk parameters
    balance = float(account_info.balance)
    risk_amount = balance * (risk_pct / 100.0)

    # Get symbol information
    sym_info = _get_symbol_info(symbol, mt5_module)
    if not sym_info:
        return 0.01

    # Calculate position size
    lots = _calculate_lots(risk_amount, entry_price, stop_price, symbol, sym_info)

    # Apply safety limits
    final_lots = _apply_safety_limits(lots, symbol, sym_info, mt5_module)

    _log_risk_calculation(balance, risk_amount, entry_price, stop_price, final_lots, sym_info)

    return final_lots


def _get_account_info(mt5_module):
    """Get MT5 account information."""
    account_info = mt5_module.account_info()  # type: ignore
    if not account_info:
        logging.error("No se pudo obtener informacion de cuenta")
    return account_info


def _get_default_volume(symbol, mt5_module):
    """Get default volume when account info is unavailable."""
    sym_info = mt5_module.symbol_info(symbol)  # type: ignore
    return sym_info.volume_min if sym_info else 0.01


def _get_symbol_info(symbol, mt5_module):
    """Get symbol information from MT5."""
    sym_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym_info:
        logging.error("Symbol %s info not available", symbol)
    return sym_info


def _calculate_lots(risk_amount, entry_price, stop_price, symbol, sym_info):
    """Calculate raw lot size based on risk parameters."""
    point = sym_info.point
    # Adjust point value for NASDAQ
    if "NASDAQ" in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices

    stop_distance_points = abs(entry_price - stop_price) / point

    if stop_distance_points == 0:
        logging.error("Stop distance es cero")
        return sym_info.volume_min

    tick_value = _get_tick_value(symbol, sym_info)

    return risk_amount / (stop_distance_points * tick_value)


def _get_tick_value(symbol, sym_info):
    """Get tick value for the symbol."""
    # CORRECTION: More accurate tick values for different instruments
    # For XAU/USD, 1 lot = 100 oz troy, so point value is 100
    if "XAU" in symbol or "GOLD" in symbol:
        return 100.0
    else:
        tick_value = getattr(sym_info, "trade_tick_value", None)
        if tick_value is None or tick_value == 0:
            logging.warning(
                "tick_value no disponible del broker, usando valor por defecto",
            )
            return _get_default_tick_value(symbol)
        return tick_value


def _get_default_tick_value(symbol):
    """Get default tick value based on symbol characteristics."""
    if "JPY" in symbol:
        # Pairs with JPY (ej: USDJPY)
        return 1000.0
    elif any(curr in symbol for curr in ["EUR", "GBP", "AUD", "NZD"]):
        # Major forex pairs
        return 10.0
    else:
        # Conservative default
        return 10.0


def _apply_safety_limits(lots, symbol, sym_info, mt5_module):
    """Apply strict safety limits to protect capital."""
    volume_min = sym_info.volume_min

    # Limites de seguridad ESTRICTOS para proteger capital
    # Límite ultra conservador: máximo 0.30 lotes para protección extrema
    max_allowed_lots = 0.30
    lots = max(volume_min, lots)
    lots = min(lots, max_allowed_lots)  # NUNCA exceder límite absoluto

    result = normalize_volume(symbol, lots, mt5_module)

    # Validación final: Si el resultado normalizado es > límite, forzar al límite
    if result > max_allowed_lots:
        logging.warning(
            f"SEGURIDAD: Lotaje calculado {result:.2f} excede límite {max_allowed_lots:.2f}, forzando a límite",
        )
        result = max_allowed_lots

    return result


def _log_risk_calculation(balance, risk_amount, entry_price, stop_price, lots, sym_info):
    """Log risk calculation details."""
    point = sym_info.point
    stop_distance_points = abs(entry_price - stop_price) / point

    logging.info(
        "Risk calc: balance=%.2f, risk_amount=%.2f, stop_distance=%.1f points, lots=%.2f",
        balance,
        risk_amount,
        stop_distance_points,
        lots,
    )
    logging.info(
        "DEBUG: tick_value=%s, point=%s, contract_size=%s",
        _get_tick_value(sym_info._symbol, sym_info),
        point,
        getattr(sym_info, "trade_contract_size", "N/A"),
    )


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def build_and_send_order(
    symbol,
    side,
    volume,
    sl=None,
    tp=None,
    deviation=30,
    retries=1,
    magic=123456,
    mt5_module=None,
):
    if mt5_module is None:
        mt5_module = mt5

    if not mt5_module.symbol_select(symbol, True):  # type: ignore
        raise RuntimeError("No se pudo seleccionar simbolo " + symbol)

    info = mt5_module.symbol_info(symbol)  # type: ignore
    tick = mt5_module.symbol_info_tick(symbol)  # type: ignore

    if not info or not tick:
        raise RuntimeError("No se pudo obtener info/tick de " + symbol)

    volume = normalize_volume(symbol, volume, mt5_module)

    price = tick.ask if side == "BUY" else tick.bid

    # Validate and adjust SL/TP levels to meet broker requirements
    sl, tp = validate_and_adjust_stops(symbol, price, sl, tp, side, mt5_module)

    # Try different approaches to handle the filling mode issue
    order_type = (
        mt5_module.ORDER_TYPE_BUY if side == "BUY" else mt5_module.ORDER_TYPE_SELL
    )  # type: ignore

    # For Exness accounts, use ORDER_FILLING_RETURN (mode 0) as the primary and only mode
    # This eliminates unnecessary retries and speeds up order execution
    filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore

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

            if attempts_made < max_total_attempts:
                wait_time = 0.5 * (
                    2 ** ((attempts_made - 1) // len(filling_modes_to_try))
                )
                time.sleep(wait_time)

    error_msg = (
        "Orden fallo despues de "
        + str(attempts_made)
        + " intentos. Ultimo retcode: "
        + str(getattr(last_result, "retcode", "N/A"))
    )
    logging.error(error_msg)
    raise RuntimeError(error_msg)


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def close_position_by_ticket(ticket, deviation=30, retries=1, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5

    positions = mt5_module.positions_get(ticket=ticket)  # type: ignore
    if not positions:
        logging.warning("Posicion %s no encontrada o ya cerrada", ticket)
        return False

    pos = positions[0]
    symbol = pos.symbol
    volume = float(pos.volume)

    if pos.type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
        close_type = mt5_module.ORDER_TYPE_SELL  # type: ignore
        price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
    else:
        close_type = mt5_module.ORDER_TYPE_BUY  # type: ignore
        price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore

    # For Exness accounts, use ORDER_FILLING_RETURN (mode 0) as the primary and only mode
    # This eliminates unnecessary retries and speeds up order execution
    filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore

    # Try each filling mode
    for _filling_mode in filling_modes_to_try:
        request = {
            "action": mt5_module.TRADE_ACTION_DEAL,  # type: ignore
            "symbol": symbol,
            "volume": volume,
            "type": close_type,
            "position": int(pos.ticket),
            "price": price,
            "deviation": deviation,
            "magic": int(getattr(pos, "magic", 0)),
            "comment": "close_by_bot",
            "type_time": mt5_module.ORDER_TIME_GTC,  # type: ignore
            "type_filling": mt5_module.ORDER_FILLING_FOK,  # type: ignore
        }

        try:
            result = mt5_module.order_send(request)  # type: ignore

            if (
                result
                and getattr(result, "retcode", None) == mt5_module.TRADE_RETCODE_DONE
            ):  # type: ignore
                logging.info("Posicion %s cerrada exitosamente", ticket)
                return True
            retcode = getattr(result, "retcode", "N/A") if result else "N/A"
            comment = getattr(result, "comment", "N/A") if result else "N/A"
            logging.warning(
                "Intento con modo=%s fallo: retcode=%s, comment=%s",
                _filling_mode,
                retcode,
                comment,
            )
        except Exception:
            logging.exception(
                "Exception al cerrar posicion %s con modo=%s", ticket, _filling_mode,
            )

    logging.error(
        "Error al cerrar posicion %s despues de intentar todos los modos de llenado",
        ticket,
    )
    return False


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def place_pending_order(
    symbol,
    order_type,
    volume,
    price,
    sl=None,
    tp=None,
    deviation=30,
    expiration_hours=4,
    magic=123456,
    mt5_module=None,
):
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
def cancel_expired_pending_orders(magic=123456, mt5_module=None):
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
                        logging.warning(
                            f"Failed to cancel expired pending order {order.ticket}",
                        )
                except Exception as e:
                    logging.exception(
                        f"Exception cancelling expired pending order {order.ticket}: {e!s}",
                    )


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def update_trailing_stops(mt5_module=None):
    """
    Update trailing stops for all open positions based on configuration.
    Implements smarter trade management with break-even and trailing stops.

    Default settings:
    - Volatility feature off
    - Trailing start at 10 pips
    - Trailing distance at 15 pips
    - Trailing mode enabled by default

    Configuration can be overridden via set files in the "trailing" section.
    """
    if mt5_module is None:
        mt5_module = mt5

    # Get all open positions
    positions = _get_open_positions_for_trailing(mt5_module)
    if not positions:
        return

    # Get configuration settings
    config = _get_trailing_config()

    # If trailing stops are disabled, exit early
    if not config['enabled']:
        return

    _log_trailing_config(config)

    # Process each position
    _process_positions_for_trailing(positions, config, mt5_module)


def _get_open_positions_for_trailing(mt5_module):
    """Get all open positions from MT5 for trailing stop processing."""
    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return None
    return positions


def _get_trailing_config():
    """Get trailing stop configuration with defaults."""
    try:
        from config.set_file_manager import get_set_manager
        cfg = get_set_manager()

        return {
            'enabled': cfg.get("trailing.enabled", True),
            'start_pips': cfg.get("trailing.start_pips", 10),
            'distance_pips': cfg.get("trailing.distance_pips", 15),
            'break_even_enabled': cfg.get("trailing.break_even_enabled", True),
            'partial_tp_enabled': cfg.get("trailing.partial_tp_enabled", False),
            'partial_tp_percent': cfg.get("trailing.partial_tp_percent", 50.0),
            'partial_tp_at_r': cfg.get("trailing.partial_tp_at_r", 1.0),
            'use_atr': cfg.get("trailing.use_atr", True),
            'start_atr_mult': cfg.get("trailing.start_atr_mult", 1.0),
            'distance_atr_mult': cfg.get("trailing.distance_atr_mult", 1.5)
        }
    except Exception as e:
        # Use default values if configuration cannot be loaded
        logging.debug(f"Using default trailing stop settings: {e}")
        return {
            'enabled': True,
            'start_pips': 10,
            'distance_pips': 15,
            'break_even_enabled': True,
            'partial_tp_enabled': False,
            'partial_tp_percent': 50.0,
            'partial_tp_at_r': 1.0,
            'use_atr': True,
            'start_atr_mult': 1.0,
            'distance_atr_mult': 1.5
        }


def _log_trailing_config(config):
    """Log trailing stop configuration."""
    logging.debug(
        f"Trailing stops update - Enabled: {config['enabled']}, "
        f"Start: {config['start_pips']} pips, "
        f"Distance: {config['distance_pips']} pips, "
        f"BE: {config['break_even_enabled']}",
    )


def _process_positions_for_trailing(positions, config, mt5_module):
    """Process each position for trailing stop updates."""
    for pos in positions:
        try:
            _process_single_position_trailing(pos, config, mt5_module)
        except Exception as e:
            logging.exception(f"Error processing trailing stop for position {pos.ticket}: {e}")


def _process_single_position_trailing(pos, config, mt5_module):
    """Process trailing stop logic for a single position."""
    symbol = pos.symbol
    ticket = pos.ticket
    price_open = pos.price_open
    sl = pos.sl
    order_type = pos.type

    # Get symbol information
    symbol_info = _get_symbol_info_for_trailing(symbol, mt5_module)
    if not symbol_info:
        return

    # Calculate point and pip values
    point, pip_value, digits = _calculate_symbol_values(symbol, symbol_info)

    # Calculate trailing thresholds
    trailing_start_price, trailing_distance_price = _calculate_trailing_thresholds(
        symbol, config, pip_value, mt5_module
    )

    # Calculate current profit
    current_price, profit_price = _calculate_current_profit(
        order_type, symbol, price_open, mt5_module
    )

    # Check if profit exceeds trailing start threshold
    if profit_price >= trailing_start_price:
        # Handle partial take profit if enabled
        if config['partial_tp_enabled']:
            _handle_partial_take_profit(
                pos, symbol, ticket, price_open, sl, profit_price,
                config, symbol_info, current_price, order_type, mt5_module
            )

        # Calculate and update stop loss
        _calculate_and_update_stop_loss(
            pos, order_type, current_price, trailing_distance_price,
            price_open, sl, digits, config, mt5_module
        )


def _get_symbol_info_for_trailing(symbol, mt5_module):
    """Get symbol information for trailing stop calculations."""
    symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        logging.warning(f"Could not get symbol info for {symbol}")
        return None
    return symbol_info


def _calculate_symbol_values(symbol, symbol_info):
    """Calculate point, pip value and digits for the symbol."""
    point = symbol_info.point
    # Adjust point value for NASDAQ
    if "NASDAQ" in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    digits = symbol_info.digits
    pip_value = point * 10

    return point, pip_value, digits


def _calculate_trailing_thresholds(symbol, config, pip_value, mt5_module):
    """Calculate trailing start and distance thresholds."""
    # Determine trailing thresholds: ATR-based preferred
    atr = _get_atr_value(symbol, mt5_module)

    if config['use_atr'] and atr and atr > 0:
        trailing_start_price = float(config['start_atr_mult']) * float(atr)
        trailing_distance_price = float(config['distance_atr_mult']) * float(atr)
    else:
        trailing_start_price = config['start_pips'] * pip_value
        trailing_distance_price = config['distance_pips'] * pip_value

    return trailing_start_price, trailing_distance_price


def _get_atr_value(symbol, mt5_module):
    """Get ATR value for the symbol."""
    try:
        from core.donchian_components.calculators.technical_indicators import (
            TechnicalIndicatorsCalculator as MarketDataService,
        )
        market_data = MarketDataService(mt5_module)
        return market_data.calculate_atr(symbol)
    except Exception:
        return None


def _calculate_current_profit(order_type, symbol, price_open, mt5_module):
    """Calculate current profit for the position."""
    if order_type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
        current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
        profit_price = current_price - price_open
    else:  # SELL
        current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
        profit_price = price_open - current_price

    return current_price, profit_price


def _handle_partial_take_profit(pos, symbol, ticket, price_open, sl, profit_price,
                              config, symbol_info, current_price, order_type, mt5_module):
    """Handle partial take profit execution."""
    # Calculate 1R profit level (entry + SL distance)
    sl_distance = abs(price_open - sl) if sl > 0 else config['start_pips'] * symbol_info.point * 10
    one_r_profit = sl_distance * config['partial_tp_at_r']

    # If profit >= 1R and volume hasn't been reduced yet
    if profit_price >= one_r_profit and pos.volume == normalize_volume(
        symbol, pos.volume, mt5_module,
    ):
        _execute_partial_take_profit(pos, symbol, ticket, config, symbol_info,
                                   current_price, order_type, mt5_module)


def _execute_partial_take_profit(pos, symbol, ticket, config, symbol_info,
                               current_price, order_type, mt5_module):
    """Execute partial take profit order."""
    partial_volume = round(pos.volume * (config['partial_tp_percent'] / 100.0), 2)
    if partial_volume >= symbol_info.volume_min:
        try:
            close_request = {
                "action": mt5_module.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": partial_volume,
                "type": mt5_module.ORDER_TYPE_SELL
                if order_type == mt5_module.POSITION_TYPE_BUY
                else mt5_module.ORDER_TYPE_BUY,
                "position": int(ticket),
                "price": current_price,
                "deviation": 30,
                "magic": int(getattr(pos, "magic", 0)),
                "comment": "partial_tp",
                "type_time": mt5_module.ORDER_TIME_GTC,
                "type_filling": mt5_module.ORDER_FILLING_FOK,
            }
            result = mt5_module.order_send(close_request)
            if (
                result
                and getattr(result, "retcode", None)
                == mt5_module.TRADE_RETCODE_DONE
            ):
                logging.info(
                    f"Partial TP ({config['partial_tp_percent']}%) executed for position {ticket} at 1R profit",
                )
        except Exception as e:
            logging.exception(
                f"Error executing partial TP for position {ticket}: {e!s}",
            )


def _calculate_and_update_stop_loss(pos, order_type, current_price, trailing_distance_price,
                                  price_open, sl, digits, config, mt5_module):
    """Calculate new stop loss and update if better than current."""
    ticket = pos.ticket
    symbol = pos.symbol

    # Calculate new stop loss level based on trailing distance
    if order_type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
        new_sl = current_price - trailing_distance_price
        # For break-even, ensure SL is at least at entry price
        if config['break_even_enabled'] and new_sl < price_open:
            new_sl = price_open
        # CRITICAL: Never allow SL to move backwards (always lock in gains)
        if sl > 0 and new_sl < sl:
            new_sl = sl  # Keep current SL if calculated one would be worse
    else:  # SELL
        new_sl = current_price + trailing_distance_price
        # For break-even, ensure SL is at least at entry price
        if config['break_even_enabled'] and new_sl > price_open:
            new_sl = price_open
        # CRITICAL: Never allow SL to move backwards (always lock in gains)
        if sl > 0 and new_sl > sl:
            new_sl = sl  # Keep current SL if calculated one would be worse

    # Only update if new SL is better than current SL
    rounded_new_sl = round(new_sl, digits)
    rounded_sl = round(sl, digits) if sl > 0 else 0
    should_update = _should_update_stop_loss(order_type, sl, rounded_new_sl, rounded_sl)

    if should_update:
        _update_position_stop_loss(ticket, symbol, rounded_new_sl, mt5_module)


def _should_update_stop_loss(order_type, sl, rounded_new_sl, rounded_sl):
    """Determine if stop loss should be updated."""
    if order_type == mt5_module.POSITION_TYPE_BUY and (
        sl == 0 or rounded_new_sl > rounded_sl
    ):  # type: ignore
        return True
    elif order_type == mt5_module.POSITION_TYPE_SELL and (
        sl == 0 or rounded_new_sl < rounded_sl
    ):  # type: ignore
        return True
    return False


def _update_position_stop_loss(ticket, symbol, new_sl, mt5_module):
    """Update position stop loss."""
    # Debug log: show previous vs calculated SL
    logging.debug(
        f"Updating SL for {symbol} ticket {ticket}: new_sl={new_sl:.5f}"
    )
    # Prepare modification request
    request = {
        "action": mt5_module.TRADE_ACTION_SLTP,  # type: ignore
        "symbol": symbol,
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
            logging.info(f"Trailing stop updated for position {ticket}")
        else:
            retcode = getattr(result, "retcode", "N/A") if result else "N/A"
            comment = getattr(result, "comment", "N/A") if result else "N/A"
            logging.warning(
                f"Failed to update trailing stop for position {ticket}: "
                f"retcode={retcode}, comment={comment}",
            )
    except Exception as e:
        logging.exception(f"Exception updating trailing stop for position {ticket}: {e}")


# Global variable to track previous positions for trade closure detection
previous_positions = set()


def record_closed_trade_result(ticket, mt5_module=None):
    """
    Record trade result when a position is closed
    Calculate return_pct = (close_profit / initial_margin) * 100
    Find associated entry_score and call quant_engine.record_trade_result(return_pct, entry_score)
    """
    if mt5_module is None:
        mt5_module = mt5

    # Try to get trade history to find the closed trade details
    # First, look for closed trades in the history
    from datetime import datetime, timedelta

    # Calculate from trade history or other available data
    # For this implementation, we'll need to access the original entry score from the global dict
    try:
        # Import the global dict from donchian_strategy
        from core.donchian_strategy import TRADE_ENTRY_SCORES

        # Get the entry score associated with this ticket
        entry_score = TRADE_ENTRY_SCORES.get(ticket)

        if entry_score is not None:
            # Try to get the trade from deals (executions)
            # Get deals for the ticket
            from datetime import datetime

            # Calculate the profit percentage as requested: (close_profit / initial_margin) * 100
            # We'll get the position info before it was closed by using history_positions
            history_positions = mt5_module.history_positions_get(
                datetime.now() - timedelta(days=7),  # Last 7 days
                datetime.now(),
                ticket=ticket,
            )

            if history_positions:
                pos = history_positions[0]  # Get the closed position

                # Calculate return percentage as requested: (close_profit / initial_margin) * 100
                close_profit = pos.profit if hasattr(pos, "profit") else 0

                # Calculate initial margin based on volume and symbol-specific margin requirements
                volume = pos.volume if hasattr(pos, "volume") else 1
                symbol = pos.symbol

                # Get symbol info to determine margin requirements
                symbol_info = mt5_module.symbol_info(symbol)
                if symbol_info:
                    # Calculate initial margin based on volume and symbol requirements
                    # Use margin_initial if available, otherwise use fallback
                    if (
                        hasattr(symbol_info, "margin_initial")
                        and symbol_info.margin_initial > 0
                    ):
                        initial_margin = volume * symbol_info.margin_initial
                    else:
                        # For specific symbols like XAUUSD, adjust accordingly
                        if "XAU" in symbol or "GOLD" in symbol:
                            initial_margin = (
                                volume * 1000
                            )  # XAUUSD has specific margin requirements
                        elif "JPY" in symbol:
                            initial_margin = (
                                volume * 1000
                            )  # Adjust as needed for JPY pairs
                        else:
                            initial_margin = volume * 1000  # Default fallback
                else:
                    # Fallback if symbol info not available
                    initial_margin = volume * 1000

                if initial_margin != 0:
                    return_pct = (close_profit / initial_margin) * 100
                else:
                    return_pct = 0

                # Import quantitative engine and record the result
                from core.quant_engine import QuantitativeEngine

                quant_engine = QuantitativeEngine()  # Create instance
                quant_engine.record_trade_result(return_pct, entry_score)

                # Log the recorded trade
                total_quant_trades = len(quant_engine._load_quant_trades())
                logging.info(
                    f"📊 Quant trade recorded: {return_pct:.2f}%, score: {entry_score:.3f}, total: {total_quant_trades}",
                )
            else:
                logging.warning(f"Could not find history for closed position {ticket}")
        else:
            logging.debug(f"No entry score found for ticket {ticket}")
    except Exception as e:
        logging.error(
            f"Error recording closed trade result for ticket {ticket}: {e}",
            exc_info=True,
        )


@performance_monitor
@safe_mt5_call
def monitor_and_update_stops(mt5_module=None):
    """
    Monitor open positions and add SL/TP if missing.
    This function should be called periodically to ensure all positions have proper stops.
    """
    global previous_positions

    if mt5_module is None:
        mt5_module = mt5

    # Get all open positions
    positions = mt5_module.positions_get()  # type: ignore
    current_positions = set() if positions else set()
    if positions:
        for pos in positions:
            current_positions.add(pos.ticket)

    # Detect closed positions by comparing with previous positions
    if previous_positions:
        closed_tickets = previous_positions - current_positions
        for ticket in closed_tickets:
            # Record trade result when position is closed
            record_closed_trade_result(ticket, mt5_module)

    # Update previous positions for next call
    previous_positions = current_positions

    if not positions:
        return

    for pos in positions:
        # Check if position has SL
        sl = getattr(pos, "sl", 0)

        # Only add SL/TP if SL is missing (avoid overwriting trailing stops)
        # TP can be zero if trailing removed it, but we preserve SL
        if sl == 0:
            symbol = pos.symbol
            ticket = pos.ticket

            logging.info(f"Position {ticket} missing SL/TP, attempting to add them")

            # Get current market price
            tick = mt5_module.symbol_info_tick(symbol)  # type: ignore
            if not tick:
                logging.warning(f"Could not get tick data for {symbol}")
                continue

            # Determine order side
            if pos.type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
                side = "BUY"
                entry_price = pos.price_open
                # Set reasonable SL/TP based on config - using ATR multipliers
                symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
                point = symbol_info.point if symbol_info else 0.01
                if "NASDAQ" in symbol.upper():
                    point = 1.0
                # Use ATR-based SL/TP distances
                try:
                    from core.donchian_components.calculators.technical_indicators import (
                        TechnicalIndicatorsCalculator as MarketDataService,
                    )

                    market_data = MarketDataService(mt5_module)
                    atr = market_data.calculate_atr(symbol)
                except Exception:
                    atr = point * 50  # fallback
                # Multipliers from set file if available
                try:
                    from config.set_file_manager import get_set_manager

                    cfg = get_set_manager()
                    sl_mult = cfg.get("strategy.sl_atr_multiplier", 3.0)
                    tp_mult = cfg.get("strategy.tp_atr_multiplier", 6.0)
                except Exception:
                    sl_mult = 3.0
                    tp_mult = 6.0
                sl_distance = sl_mult * atr
                tp_distance = tp_mult * atr
                sl_price = entry_price - sl_distance
                tp_price = entry_price + tp_distance
            else:
                side = "SELL"
                entry_price = pos.price_open
                # Set reasonable SL/TP based on config - using ATR multipliers
                symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
                point = symbol_info.point if symbol_info else 0.01
                if "NASDAQ" in symbol.upper():
                    point = 1.0
                # Use ATR-based SL/TP distances
                try:
                    from core.donchian_components.calculators.technical_indicators import (
                        TechnicalIndicatorsCalculator as MarketDataService,
                    )

                    market_data = MarketDataService(mt5_module)
                    atr = market_data.calculate_atr(symbol)
                except Exception:
                    atr = point * 50  # fallback
                # Multipliers from set file if available
                try:
                    from config.set_file_manager import get_set_manager

                    cfg = get_set_manager()
                    sl_mult = cfg.get("strategy.sl_atr_multiplier", 3.0)
                    tp_mult = cfg.get("strategy.tp_atr_multiplier", 6.0)
                except Exception:
                    sl_mult = 3.0
                    tp_mult = 6.0
                sl_distance = sl_mult * atr
                tp_distance = tp_mult * atr
                sl_price = entry_price + sl_distance
                tp_price = entry_price - tp_distance

            # Validate stops
            sl_price, tp_price = validate_and_adjust_stops(
                symbol, entry_price, sl_price, tp_price, side, mt5_module,
            )

            # For Exness accounts, use ORDER_FILLING_RETURN (mode 0) as the primary and only mode
            # This eliminates unnecessary retries and speeds up order execution
            filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore

            # Try each filling mode with retries
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
                                break  # Success, exit retry loop
                            else:
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
                        break  # Nothing to set, exit retry loop

                    # Wait before retrying
                    if attempt < max_retries:
                        time.sleep(0.5 * (2 ** (attempt - 1)))  # Exponential backoff
                else:
                    # If we've tried all attempts for this filling mode, continue to next mode
                    continue
                # If we succeeded, break out of filling mode loop
                break
            else:
                logging.error(
                    f"Failed to add SL/TP to position {ticket} after all attempts",
                )
