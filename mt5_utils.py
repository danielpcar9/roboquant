# mt5_utils.py
import time
import logging
import functools
from datetime import datetime, timedelta
from typing import Callable, Any
# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

# Import error handling components
from error_handler import safe_mt5_call, MT5ConnectionError, OrderExecutionError, MT5_ERROR_CODES, retry_with_exponential_backoff

# Import consolidated performance monitoring
from mt5_core import mt5_performance_monitor as performance_monitor

# Import consolidated MT5 utility functions
from mt5_core import validate_and_adjust_stops, normalize_volume, get_filling_mode

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED = True


# validate_and_adjust_stops function removed - using consolidated version from mt5_core.py

# performance_monitor function removed - using consolidated version from mt5_core.py

# get_filling_mode function removed - using consolidated version from mt5_core.py

# normalize_volume function removed - using consolidated version from mt5_core.py

@performance_monitor
def estimate_lots_by_risk(symbol, entry_price, stop_price, risk_pct, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    account_info = mt5_module.account_info()  # type: ignore
    if not account_info:
        logging.error("No se pudo obtener informacion de cuenta")
        sym_info = mt5_module.symbol_info(symbol)  # type: ignore
        return sym_info.volume_min if sym_info else 0.01
    
    balance = float(account_info.balance)
    risk_amount = balance * (risk_pct / 100.0)
    
    sym_info = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym_info:
        logging.error("Symbol %s info not available", symbol)
        return 0.01
    
    point = sym_info.point
    # Adjust point value for NASDAQ
    if 'NASDAQ' in symbol.upper():
        point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
    volume_min = sym_info.volume_min
    
    stop_distance_points = abs(entry_price - stop_price) / point
    
    if stop_distance_points == 0:
        logging.error("Stop distance es cero")
        return volume_min
    
    # CORRECTION: More accurate tick values for different instruments
    # For XAU/USD, 1 lot = 100 oz troy, so point value is 100
    if 'XAU' in symbol or 'GOLD' in symbol:
        tick_value = 100.0
    else:
        tick_value = getattr(sym_info, 'trade_tick_value', None)
        if tick_value is None or tick_value == 0:
            logging.warning("tick_value no disponible del broker, usando valor por defecto")
            # Default values by instrument type
            if 'JPY' in symbol:
                # Pairs with JPY (ej: USDJPY)
                tick_value = 1000.0
            elif any(curr in symbol for curr in ['EUR', 'GBP', 'AUD', 'NZD']):
                # Major forex pairs
                tick_value = 10.0
            else:
                # Conservative default
                tick_value = 10.0
    
    logging.info("DEBUG: tick_value=%s, point=%s, contract_size=%s", 
                 tick_value, point, getattr(sym_info, 'trade_contract_size', 'N/A'))
    
    lots = risk_amount / (stop_distance_points * tick_value)
    
    # Limites de seguridad
    lots = max(volume_min, lots)
    lots = min(lots, volume_min * 10)
    
    result = normalize_volume(symbol, lots, mt5_module)
    
    logging.info("Risk calc: balance=%.2f, risk_amount=%.2f, stop_distance=%.1f points, lots=%.2f", 
                 balance, risk_amount, stop_distance_points, result)
    
    return result

@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def build_and_send_order(symbol, side, volume, sl=None, tp=None, 
                         deviation=30, retries=1, magic=123456, mt5_module=None):
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
    order_type = mt5_module.ORDER_TYPE_BUY if side == "BUY" else mt5_module.ORDER_TYPE_SELL  # type: ignore
    
    # For Exness accounts, use ORDER_FILLING_RETURN (mode 0) as the primary and only mode
    # This eliminates unnecessary retries and speeds up order execution
    filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore
    
    last_result = None
    attempts_made = 0
    max_total_attempts = retries * len(filling_modes_to_try)
    
    # Try each filling mode
    for filling_mode in filling_modes_to_try:
        if attempts_made >= max_total_attempts:
            break
            
        # Try with SL/TP first
        request = {
            'action': mt5_module.TRADE_ACTION_DEAL,  # type: ignore
            'symbol': symbol,
            'volume': volume,
            'type': order_type,
            'price': price,
            'deviation': deviation,
            'magic': magic,
            'comment': 'bot_order',
            'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
            'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
        }
        
        # Add SL/TP if provided
        if sl is not None:
            request['sl'] = float(sl)
        if tp is not None:
            request['tp'] = float(tp)
        
        # Try this filling mode for the specified number of retries
        for attempt_in_mode in range(1, retries + 1):
            attempts_made += 1
            if attempts_made > max_total_attempts:
                break
                
            try:
                result = mt5_module.order_send(request)  # type: ignore
            except Exception as e:
                logging.exception("Exception en order_send (modo=%s, intento %d)", filling_mode, attempt_in_mode)
                result = None
            
            if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                logging.info("Orden enviada exitosamente. Ticket: %s", getattr(result, 'order', 'N/A'))
                return result
            
            last_result = result
            retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
            comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
            logging.warning("Intento %d/%d (modo=%s) fallo: retcode=%s, comment=%s", 
                          attempts_made, max_total_attempts, filling_mode, retcode, comment)
            
            # If we get "Invalid stops" error, try a different approach
            if retcode == 10016:  # Invalid stops
                logging.warning("Invalid stops detected, trying alternative approach")
                
                # Approach 1: Place order without SL/TP first, then modify
                request_no_stops = request.copy()
                request_no_stops.pop('sl', None)
                request_no_stops.pop('tp', None)
                
                try:
                    result_no_stops = mt5_module.order_send(request_no_stops)  # type: ignore
                    if result_no_stops and getattr(result_no_stops, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                        order_ticket = getattr(result_no_stops, 'order', None)
                        if order_ticket:
                            logging.info("Orden enviada sin SL/TP. Ticket: %s", order_ticket)
                            
                            # Now try to modify the order to add SL/TP
                            if sl is not None or tp is not None:
                                # Try multiple attempts to set SL/TP
                                max_modification_attempts = 3
                                for mod_attempt in range(1, max_modification_attempts + 1):
                                    modification_request = {
                                        'action': mt5_module.TRADE_ACTION_SLTP,  # type: ignore
                                        'symbol': symbol,
                                        'position': int(order_ticket),
                                        'deviation': deviation,
                                        'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
                                        'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
                                    }
                                    
                                    # Use potentially adjusted SL/TP values
                                    current_sl = sl
                                    current_tp = tp
                                    
                                    # For subsequent attempts, use adjusted values
                                    if mod_attempt > 1:
                                        current_sl, current_tp = validate_and_adjust_stops(symbol, price, sl, tp, side, mt5_module)
                                        logging.info("Attempt %d with adjusted SL/TP: SL=%s, TP=%s", mod_attempt, current_sl, current_tp)
                                    
                                    if current_sl is not None:
                                        modification_request['sl'] = float(current_sl)
                                    if current_tp is not None:
                                        modification_request['tp'] = float(current_tp)
                                    
                                    modification_result = mt5_module.order_send(modification_request)  # type: ignore
                                    if modification_result and getattr(modification_result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                                        logging.info("SL/TP modificados exitosamente para orden %s", order_ticket)
                                        break  # Success, exit retry loop
                                    else:
                                        mod_retcode = getattr(modification_result, 'retcode', 'N/A') if modification_result else 'N/A'
                                        mod_comment = getattr(modification_result, 'comment', 'N/A') if modification_result else 'N/A'
                                        logging.warning("Attempt %d failed to modify SL/TP: retcode=%s, comment=%s", mod_attempt, mod_retcode, mod_comment)
                                        
                                        # Wait before retrying
                                        if mod_attempt < max_modification_attempts:
                                            time.sleep(0.5 * (2 ** (mod_attempt - 1)))  # Exponential backoff
                                else:
                                    # All modification attempts failed
                                    logging.warning("La orden %s se ejecutó sin SL/TP después de %d intentos. Deberás gestionarla manualmente.", order_ticket, max_modification_attempts)
                            
                            return result_no_stops
                        else:
                            logging.warning("No se pudo obtener el ticket de la orden")
                    else:
                        retcode_no_stops = getattr(result_no_stops, 'retcode', 'N/A') if result_no_stops else 'N/A'
                        comment_no_stops = getattr(result_no_stops, 'comment', 'N/A') if result_no_stops else 'N/A'
                        logging.warning("Intento sin SL/TP fallo: retcode=%s, comment=%s", retcode_no_stops, comment_no_stops)
                except Exception as e:
                    logging.exception("Exception en order_send sin SL/TP o modificando")
            
            if attempts_made < max_total_attempts:
                wait_time = 0.5 * (2 ** ((attempts_made - 1) // len(filling_modes_to_try)))
                time.sleep(wait_time)
    
    error_msg = "Orden fallo despues de " + str(attempts_made) + " intentos. Ultimo retcode: " + str(getattr(last_result, 'retcode', 'N/A'))
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
    for filling_mode in filling_modes_to_try:
        request = {
            'action': mt5_module.TRADE_ACTION_DEAL,  # type: ignore
            'symbol': symbol,
            'volume': volume,
            'type': close_type,
            'position': int(pos.ticket),
            'price': price,
            'deviation': deviation,
            'magic': int(getattr(pos, 'magic', 0)),
            'comment': 'close_by_bot',
            'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
            'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
        }
        
        try:
            result = mt5_module.order_send(request)  # type: ignore
            
            if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                logging.info("Posicion %s cerrada exitosamente", ticket)
                return True
            else:
                retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
                comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
                logging.warning("Intento con modo=%s fallo: retcode=%s, comment=%s", filling_mode, retcode, comment)
        except Exception as e:
            logging.exception("Exception al cerrar posicion %s con modo=%s", ticket, filling_mode)
    
    logging.error("Error al cerrar posicion %s despues de intentar todos los modos de llenado", ticket)
    return False


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def place_pending_order(symbol, order_type, volume, price, sl=None, tp=None, deviation=30, expiration_hours=4, magic=123456, mt5_module=None):
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
        logging.error(f"Invalid parameters for pending order: symbol={symbol}, type={order_type}, volume={volume}, price={price}")
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
    expiration_time = int((datetime.now() + timedelta(hours=expiration_hours)).timestamp())
    
    # Prepare order request
    request = {
        'action': mt5_module.TRADE_ACTION_PENDING,  # type: ignore
        'symbol': symbol,
        'volume': float(volume),
        'type': order_type_mt5,
        'price': float(price),
        'deviation': deviation,
        'magic': magic,
        'comment': f'pending_{order_type.lower()}',
        'type_time': mt5_module.ORDER_TIME_SPECIFIED,  # type: ignore
        'type_filling': mt5_module.ORDER_FILLING_FOK,  # type: ignore
        'expiration': expiration_time
    }
    
    # Add SL/TP if provided
    if sl is not None and sl > 0:
        request['sl'] = float(sl)
    if tp is not None and tp > 0:
        request['tp'] = float(tp)
    
    # Send order
    try:
        result = mt5_module.order_send(request)  # type: ignore
        
        if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
            logging.info(f"Pending order placed successfully: {order_type} {symbol} @ {price}")
            logging.info(f"Order ticket: {getattr(result, 'order', 'N/A')}")
            return result
        else:
            retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
            comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
            logging.error(f"Failed to place pending order: retcode={retcode}, comment={comment}")
            return None
    except Exception as e:
        logging.exception(f"Exception placing pending order: {str(e)}")
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
        if getattr(order, 'magic', 0) == magic:
            # Check if order has expiration time
            expiration = getattr(order, 'expiration', 0)
            if expiration > 0 and current_time > expiration:
                # Cancel expired order
                request = {
                    'action': mt5_module.TRADE_ACTION_REMOVE,  # type: ignore
                    'order': int(order.ticket),
                    'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
                    'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
                }
                
                try:
                    result = mt5_module.order_send(request)  # type: ignore
                    if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                        logging.info(f"Expired pending order {order.ticket} cancelled successfully")
                    else:
                        logging.warning(f"Failed to cancel expired pending order {order.ticket}")
                except Exception as e:
                    logging.exception(f"Exception cancelling expired pending order {order.ticket}: {str(e)}")


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
    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return
    
    # Get set file configuration for trailing stops
    try:
        from set_file_manager import get_set_manager
        cfg = get_set_manager()
        # Get trailing stop configuration with defaults
        trailing_enabled = cfg.get('trailing.enabled', True)
        trailing_start_pips = cfg.get('trailing.start_pips', 10)
        trailing_distance_pips = cfg.get('trailing.distance_pips', 15)
        break_even_enabled = cfg.get('trailing.break_even_enabled', True)
    except Exception as e:
        # Use default values if configuration cannot be loaded
        trailing_enabled = True
        trailing_start_pips = 10
        trailing_distance_pips = 15
        break_even_enabled = True
        logging.debug(f"Using default trailing stop settings: {e}")
    
    # If trailing stops are disabled, exit early
    if not trailing_enabled:
        return
    
    logging.debug(f"Trailing stops update - Enabled: {trailing_enabled}, Start: {trailing_start_pips} pips, Distance: {trailing_distance_pips} pips, BE: {break_even_enabled}")
    
    for pos in positions:
        try:
            symbol = pos.symbol
            ticket = pos.ticket
            profit = pos.profit
            price_open = pos.price_open
            sl = pos.sl
            order_type = pos.type
            
            # Get symbol information for point value
            symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
            if not symbol_info:
                logging.warning(f"Could not get symbol info for {symbol}")
                continue
                
            point = symbol_info.point
            # Adjust point value for NASDAQ
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            digits = symbol_info.digits
            
            # Convert pips to price units
            pip_value = point * 10  # Standard pip calculation
            trailing_start_price = trailing_start_pips * pip_value
            trailing_distance_price = trailing_distance_pips * pip_value
            
            # Calculate current profit in price units
            if order_type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
                current_price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
                profit_price = current_price - price_open
            else:  # SELL
                current_price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
                profit_price = price_open - current_price
            
            # Check if profit exceeds trailing start threshold
            if profit_price >= trailing_start_price:
                # Calculate new stop loss level based on trailing distance
                if order_type == mt5_module.POSITION_TYPE_BUY:  # type: ignore
                    new_sl = current_price - trailing_distance_price
                    # For break-even, ensure SL is at least at entry price
                    if break_even_enabled and new_sl < price_open:
                        new_sl = price_open
                else:  # SELL
                    new_sl = current_price + trailing_distance_price
                    # For break-even, ensure SL is at least at entry price
                    if break_even_enabled and new_sl > price_open:
                        new_sl = price_open
                
                # Only update if new SL is better than current SL
                should_update = False
                if order_type == mt5_module.POSITION_TYPE_BUY and (sl == 0 or new_sl > sl):  # type: ignore
                    should_update = True
                elif order_type == mt5_module.POSITION_TYPE_SELL and (sl == 0 or new_sl < sl):  # type: ignore
                    should_update = True
                
                if should_update:
                    # Prepare modification request
                    request = {
                        'action': mt5_module.TRADE_ACTION_SLTP,  # type: ignore
                        'symbol': symbol,
                        'position': int(ticket),
                        'sl': round(new_sl, digits),
                        'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
                        'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
                    }
                    
                    # Send modification request
                    try:
                        result = mt5_module.order_send(request)  # type: ignore
                        if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                            logging.info(f"Trailing stop updated for position {ticket}: SL moved to {new_sl:.{digits}f}")
                        else:
                            retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
                            comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
                            logging.warning(f"Failed to update trailing stop for position {ticket}: retcode={retcode}, comment={comment}")
                    except Exception as e:
                        logging.exception(f"Exception updating trailing stop for position {ticket}: {str(e)}")
            else:
                logging.debug(f"Position {ticket} profit ({profit_price/point:.1f} pips) below trailing start threshold ({trailing_start_pips} pips)")
                
        except Exception as e:
            logging.exception(f"Error processing position {pos.ticket if hasattr(pos, 'ticket') else 'unknown'}: {str(e)}")
            continue

@performance_monitor
@safe_mt5_call
def monitor_and_update_stops(mt5_module=None):
    """
    Monitor open positions and add SL/TP if missing.
    This function should be called periodically to ensure all positions have proper stops.
    """
    if mt5_module is None:
        mt5_module = mt5
    
    # Get all open positions
    positions = mt5_module.positions_get()  # type: ignore
    if not positions:
        return
    
    for pos in positions:
        # Check if position has SL/TP
        sl = getattr(pos, 'sl', 0)
        tp = getattr(pos, 'tp', 0)
        
        # If SL or TP is missing or zero, try to add them
        if sl == 0 or tp == 0:
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
                # Adjust point value for NASDAQ
                if 'NASDAQ' in symbol.upper():
                    point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
                # Use default ATR multipliers (LOW RISK profile)
                sl_distance = 3.0 * point  # 3.0 ATR multiplier
                tp_distance = 6.0 * point  # 6.0 ATR multiplier
                sl_price = entry_price - sl_distance
                tp_price = entry_price + tp_distance
            else:
                side = "SELL"
                entry_price = pos.price_open
                # Set reasonable SL/TP based on config - using ATR multipliers
                symbol_info = mt5_module.symbol_info(symbol)  # type: ignore
                point = symbol_info.point if symbol_info else 0.01
                # Adjust point value for NASDAQ
                if 'NASDAQ' in symbol.upper():
                    point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
                # Use default ATR multipliers (LOW RISK profile)
                sl_distance = 3.0 * point  # 3.0 ATR multiplier
                tp_distance = 6.0 * point  # 6.0 ATR multiplier
                sl_price = entry_price + sl_distance
                tp_price = entry_price - tp_distance
            
            # Validate stops
            sl_price, tp_price = validate_and_adjust_stops(symbol, entry_price, sl_price, tp_price, side, mt5_module)
            
            # For Exness accounts, use ORDER_FILLING_RETURN (mode 0) as the primary and only mode
            # This eliminates unnecessary retries and speeds up order execution
            filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]  # type: ignore
            
            # Try each filling mode with retries
            max_retries = 1
            for filling_mode in filling_modes_to_try:
                for attempt in range(1, max_retries + 1):
                    # Try to modify position
                    modification_request = {
                        'action': mt5_module.TRADE_ACTION_SLTP,  # type: ignore
                        'symbol': symbol,
                        'position': int(ticket),
                        'sl': float(sl_price) if sl_price is not None else 0,
                        'tp': float(tp_price) if tp_price is not None else 0,
                        'type_time': mt5_module.ORDER_TIME_GTC,  # type: ignore
                        'type_filling': mt5_module.ORDER_FILLING_FOK  # type: ignore
                    }
                    
                    # Remove zero values
                    if modification_request['sl'] == 0:
                        modification_request.pop('sl')
                    if modification_request['tp'] == 0:
                        modification_request.pop('tp')
                    
                    # If we still have something to set
                    if 'sl' in modification_request or 'tp' in modification_request:
                        try:
                            result = mt5_module.order_send(modification_request)  # type: ignore
                            if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:  # type: ignore
                                logging.info(f"SL/TP added successfully to position {ticket}")
                                break  # Success, exit retry loop
                            else:
                                retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
                                comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
                                logging.warning(f"Attempt {attempt} failed to add SL/TP to position {ticket}: retcode={retcode}, comment={comment}")
                                
                                # If we get "Invalid stops" error, try with adjusted stops
                                if retcode == 10016:  # Invalid stops
                                    logging.warning("Invalid stops detected for position %s, trying with adjusted levels", ticket)
                                    adjusted_sl, adjusted_tp = validate_and_adjust_stops(symbol, entry_price, sl_price, tp_price, side, mt5_module)
                                    if adjusted_sl != sl_price or adjusted_tp != tp_price:
                                        logging.info("Retrying with adjusted SL/TP: SL=%s, TP=%s", adjusted_sl, adjusted_tp)
                                        sl_price, tp_price = adjusted_sl, adjusted_tp
                        except Exception as e:
                            logging.exception(f"Exception while adding SL/TP to position {ticket} (attempt {attempt})")
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
                logging.error(f"Failed to add SL/TP to position {ticket} after all attempts")
