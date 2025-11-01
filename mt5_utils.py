# mt5_utils.py
import time
import logging
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore


def get_filling_mode(symbol, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    sym = mt5_module.symbol_info(symbol)  # type: ignore
    if not sym:
        logging.warning("Symbol %s info not available", symbol)
        return mt5_module.ORDER_FILLING_RETURN
    
    try:
        filling_mode = getattr(sym, 'filling_mode', None)
    except AttributeError:
        return mt5_module.ORDER_FILLING_RETURN
    
    if filling_mode is None:
        return mt5_module.ORDER_FILLING_RETURN
    
    try:
        if hasattr(mt5_module, 'ORDER_FILLING_FOK'):
            if filling_mode & mt5_module.ORDER_FILLING_FOK:
                return mt5_module.ORDER_FILLING_FOK
        
        if hasattr(mt5_module, 'ORDER_FILLING_IOC'):
            if filling_mode & mt5_module.ORDER_FILLING_IOC:
                return mt5_module.ORDER_FILLING_IOC
    except Exception as e:
        logging.debug("Error checking filling mode: %s", e)
    
    return mt5_module.ORDER_FILLING_RETURN


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


def estimate_lots_by_risk(symbol, entry_price, stop_price, risk_pct, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    account_info = mt5_module.account_info()  # type: ignore  # type: ignore
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
    
    tick_value = getattr(sym_info, 'trade_tick_value', None)
    
    # DEBUG
    logging.info("DEBUG: tick_value=%s, point=%s, contract_size=%s", 
                 tick_value, point, getattr(sym_info, 'trade_contract_size', 'N/A'))
    
    if tick_value is None or tick_value == 0:
        logging.warning("tick_value no disponible, usando estimacion conservadora")
        
        if 'XAU' in symbol or 'GOLD' in symbol:
            tick_value = 1.0
        else:
            tick_value = 1.0
    
    lots = risk_amount / (stop_distance_points * tick_value)
    
    # Limites de seguridad
    lots = max(volume_min, lots)
    lots = min(lots, volume_min * 10)
    
    result = normalize_volume(symbol, lots, mt5_module)
    
    logging.info("Risk calc: balance=%.2f, risk_amount=%.2f, stop_distance=%.1f points, lots=%.2f", 
                 balance, risk_amount, stop_distance_points, result)
    
    return result


def build_and_send_order(symbol, side, volume, sl=None, tp=None, 
                         deviation=30, retries=3, magic=123456, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    if not mt5_module.symbol_select(symbol, True):  # type: ignore  # type: ignore
        raise RuntimeError("No se pudo seleccionar simbolo " + symbol)
    
    info = mt5_module.symbol_info(symbol)  # type: ignore
    tick = mt5_module.symbol_info_tick(symbol)  # type: ignore  # type: ignore
    
    if not info or not tick:
        raise RuntimeError("No se pudo obtener info/tick de " + symbol)
    
    volume = normalize_volume(symbol, volume, mt5_module)
    
    price = tick.ask if side == "BUY" else tick.bid
    
    filling = get_filling_mode(symbol, mt5_module)
    
    order_type = mt5_module.ORDER_TYPE_BUY if side == "BUY" else mt5_module.ORDER_TYPE_SELL
    
    request = {
        'action': mt5_module.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': order_type,
        'price': price,
        'deviation': deviation,
        'magic': magic,
        'comment': 'bot_order',
        'type_time': mt5_module.ORDER_TIME_GTC,
        'type_filling': filling
    }
    
    if sl is not None:
        request['sl'] = float(sl)
    if tp is not None:
        request['tp'] = float(tp)
    
    last_result = None
    for attempt in range(1, retries + 1):
        try:
            result = mt5_module.order_send(request)  # type: ignore  # type: ignore
        except Exception as e:
            logging.exception("Exception en order_send (intento %d)", attempt)
            result = None
        
        if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:
            logging.info("Orden enviada exitosamente. Ticket: %s", getattr(result, 'order', 'N/A'))
            return result
        
        last_result = result
        retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
        comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
        logging.warning("Intento %d/%d fallo: retcode=%s, comment=%s", attempt, retries, retcode, comment)
        
        if attempt < retries:
            wait_time = 0.5 * (2 ** (attempt - 1))
            time.sleep(wait_time)
    
    error_msg = "Orden fallo despues de " + str(retries) + " intentos. Ultimo retcode: " + str(getattr(last_result, 'retcode', 'N/A'))
    logging.error(error_msg)
    raise RuntimeError(error_msg)


def close_position_by_ticket(ticket, deviation=30, mt5_module=None):
    if mt5_module is None:
        mt5_module = mt5
    
    positions = mt5_module.positions_get(ticket=ticket)  # type: ignore  # type: ignore
    if not positions:
        logging.warning("Posicion %s no encontrada o ya cerrada", ticket)
        return False
    
    pos = positions[0]
    symbol = pos.symbol
    volume = float(pos.volume)
    
    if pos.type == mt5_module.POSITION_TYPE_BUY:
        close_type = mt5_module.ORDER_TYPE_SELL
        price = mt5_module.symbol_info_tick(symbol).bid  # type: ignore
    else:
        close_type = mt5_module.ORDER_TYPE_BUY
        price = mt5_module.symbol_info_tick(symbol).ask  # type: ignore
    
    request = {
        'action': mt5_module.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': close_type,
        'position': int(pos.ticket),
        'price': price,
        'deviation': deviation,
        'magic': int(getattr(pos, 'magic', 0)),
        'comment': 'close_by_bot',
        'type_time': mt5_module.ORDER_TIME_GTC,
        'type_filling': get_filling_mode(symbol, mt5_module)
    }
    
    result = mt5_module.order_send(request)  # type: ignore
    
    if result and getattr(result, 'retcode', None) == mt5_module.TRADE_RETCODE_DONE:
        logging.info("Posicion %s cerrada exitosamente", ticket)
        return True
    else:
        retcode = getattr(result, 'retcode', 'N/A') if result else 'N/A'
        comment = getattr(result, 'comment', 'N/A') if result else 'N/A'
        logging.error("Error al cerrar posicion %s: retcode=%s, comment=%s", ticket, retcode, comment)
        return False