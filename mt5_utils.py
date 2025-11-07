# mt5_utils.py
import time
import logging
import functools
from typing import Callable, Any
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

# Import error handling components
from error_handler import safe_mt5_call, MT5ConnectionError, OrderExecutionError, MT5_ERROR_CODES, retry_with_exponential_backoff

# Performance monitoring
PERFORMANCE_MONITORING_ENABLED = True


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
    # For XAUUSD, 150 points should be sufficient based on your config
    if min_stop_distance == 0:
        min_stop_distance = 150  # Default safe value
    
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

def performance_monitor(func: Callable) -> Callable:
    """
    Decorator to monitor performance of MT5 functions.
    
    Args:
        func: Function to monitor
        
    Returns:
        Wrapped function with performance monitoring
    """
    @functools.wraps(func)
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

def get_filling_mode(symbol, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    sym = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym:
        logging.warning("Symbol %s info not available", symbol)
        return mt5_module.ORDER_FILLING_RETURN  # type: ignore
    
    try:
        filling_mode = getattr(sym, 'filling_mode', None)
    except AttributeError:
        return mt5_module.ORDER_FILLING_RETURN  # type: ignore
    
    if filling_mode is None:
        return mt5_module.ORDER_FILLING_RETURN  # type: ignore
    
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
    return mt5_module.ORDER_FILLING_RETURN  # type: ignore

@performance_monitor
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
                         deviation=30, retries=3, magic=123456, mt5_module=None):
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
    
    # List of filling modes to try
    filling_modes_to_try = [
        mt5_module.ORDER_FILLING_RETURN,  # type: ignore
    ]
    
    # Add other modes if they exist
    if hasattr(mt5_module, 'ORDER_FILLING_IOC'):  # type: ignore
        filling_modes_to_try.append(mt5_module.ORDER_FILLING_IOC)  # type: ignore
    if hasattr(mt5_module, 'ORDER_FILLING_FOK'):  # type: ignore
        filling_modes_to_try.append(mt5_module.ORDER_FILLING_FOK)  # type: ignore
    
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
            'type_filling': filling_mode
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
                                        'type_filling': filling_mode
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
def close_position_by_ticket(ticket, deviation=30, mt5_module=None):
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
    
    # List of filling modes to try
    filling_modes_to_try = [
        mt5_module.ORDER_FILLING_RETURN,  # type: ignore
    ]
    
    # Add other modes if they exist
    if hasattr(mt5_module, 'ORDER_FILLING_IOC'):  # type: ignore
        filling_modes_to_try.append(mt5_module.ORDER_FILLING_IOC)  # type: ignore
    if hasattr(mt5_module, 'ORDER_FILLING_FOK'):  # type: ignore
        filling_modes_to_try.append(mt5_module.ORDER_FILLING_FOK)  # type: ignore
    
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
            'type_filling': filling_mode
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
                # Set reasonable SL/TP based on config
                sl_price = entry_price - (150 * mt5_module.symbol_info(symbol).point)  # type: ignore
                tp_price = entry_price + (300 * mt5_module.symbol_info(symbol).point)  # type: ignore
            else:
                side = "SELL"
                entry_price = pos.price_open
                # Set reasonable SL/TP based on config
                sl_price = entry_price + (150 * mt5_module.symbol_info(symbol).point)  # type: ignore
                tp_price = entry_price - (300 * mt5_module.symbol_info(symbol).point)  # type: ignore
            
            # Validate stops
            sl_price, tp_price = validate_and_adjust_stops(symbol, entry_price, sl_price, tp_price, side, mt5_module)
            
            # Try different approaches to handle the filling mode issue
            filling_modes_to_try = [
                mt5_module.ORDER_FILLING_RETURN,  # type: ignore
            ]
            
            # Add other modes if they exist
            if hasattr(mt5_module, 'ORDER_FILLING_IOC'):  # type: ignore
                filling_modes_to_try.append(mt5_module.ORDER_FILLING_IOC)  # type: ignore
            if hasattr(mt5_module, 'ORDER_FILLING_FOK'):  # type: ignore
                filling_modes_to_try.append(mt5_module.ORDER_FILLING_FOK)  # type: ignore
            
            # Try each filling mode with retries
            max_retries = 3
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
                        'type_filling': filling_mode
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