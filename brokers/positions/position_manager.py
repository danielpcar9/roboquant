"""
MT5 Position Manager
Handles position closing and management operations
"""

import logging
from typing import Any

import MetaTrader5 as mt5

from brokers.mt5_core import (
    mt5_performance_monitor as performance_monitor,
)
from services.error_handler import retry_with_exponential_backoff, safe_mt5_call


@performance_monitor
@safe_mt5_call
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def close_position_by_ticket(
    ticket: int, deviation: int = 30, retries: int = 1, mt5_module: Any = None,
) -> bool:
    """
    Close a position by ticket number.

    Args:
        ticket: Position ticket number
        deviation: Price deviation in points
        retries: Number of retry attempts
        mt5_module: MT5 module instance

    Returns:
        bool: True if successful, False otherwise

    """
    if mt5_module is None:
        mt5_module = mt5

    # Get position info
    positions = mt5_module.positions_get(ticket=ticket)
    if not positions:
        logging.error(f"Position {ticket} not found")
        return False

    pos = positions[0]

    # Determine close type
    if pos.type == mt5_module.POSITION_TYPE_BUY:
        close_type = mt5_module.ORDER_TYPE_SELL
    elif pos.type == mt5_module.POSITION_TYPE_SELL:
        close_type = mt5_module.ORDER_TYPE_BUY
    else:
        logging.error(f"Unknown position type for ticket {ticket}")
        return False

    # Get current price
    tick = mt5_module.symbol_info_tick(pos.symbol)
    if tick is None:
        logging.error(f"Failed to get tick data for {pos.symbol}")
        return False

    price = tick.bid if pos.type == mt5_module.POSITION_TYPE_BUY else tick.ask

    # This eliminates unnecessary retries and speeds up order execution
    filling_modes_to_try = [mt5_module.ORDER_FILLING_FOK]

    # Try each filling mode
    for _filling_mode in filling_modes_to_try:
        request = {
            "action": mt5_module.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": int(pos.ticket),
            "price": price,
            "deviation": deviation,
            "magic": int(getattr(pos, "magic", 0)),
            "comment": "close_by_bot",
            "type_time": mt5_module.ORDER_TIME_GTC,
            "type_filling": mt5_module.ORDER_FILLING_FOK,
        }

        try:
            result = mt5_module.order_send(request)

            if (
                result
                and getattr(result, "retcode", None) == mt5_module.TRADE_RETCODE_DONE
            ):
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
def get_open_positions(mt5_module: Any = None) -> list:
    """
    Get all open positions.

    Args:
        mt5_module: MT5 module instance

    Returns:
        list: List of open positions

    """
    if mt5_module is None:
        mt5_module = mt5

    positions = mt5_module.positions_get()
    if positions is None:
        logging.error("Failed to get positions")
        return []
    return list(positions)


@performance_monitor
@safe_mt5_call
def close_all_positions(mt5_module: Any = None) -> tuple[int, int]:
    """
    Close all open positions.

    Args:
        mt5_module: MT5 module instance

    Returns:
        tuple: (closed_count, error_count)

    """
    if mt5_module is None:
        mt5_module = mt5

    positions = get_open_positions(mt5_module)
    if not positions:
        logging.info("No open positions to close")
        return 0, 0

    closed_count = 0
    error_count = 0

    for position in positions:
        ticket = position.ticket
        try:
            success = close_position_by_ticket(ticket, mt5_module=mt5_module)
            if success:
                closed_count += 1
            else:
                error_count += 1
        except Exception as e:
            logging.exception(f"Error closing position {ticket}: {e}")
            error_count += 1

    logging.info(f"Closed {closed_count} positions, {error_count} errors")
    return closed_count, error_count


@performance_monitor
@safe_mt5_call
def get_position_pnl(ticket: int, mt5_module: Any = None) -> float:
    """
    Get P&L for a specific position.

    Args:
        ticket: Position ticket number
        mt5_module: MT5 module instance

    Returns:
        float: Position P&L

    """
    if mt5_module is None:
        mt5_module = mt5

    positions = mt5_module.positions_get(ticket=ticket)
    if not positions:
        return 0.0

    pos = positions[0]
    return float(getattr(pos, "profit", 0.0))


@performance_monitor
@safe_mt5_call
def get_total_exposure(mt5_module: Any = None) -> float:
    """
    Calculate total exposure across all positions.

    Args:
        mt5_module: MT5 module instance

    Returns:
        float: Total exposure in lots

    """
    if mt5_module is None:
        mt5_module = mt5

    positions = get_open_positions(mt5_module)
    if not positions:
        return 0.0

    total_exposure = 0.0
    for pos in positions:
        total_exposure += float(getattr(pos, "volume", 0.0))

    return total_exposure


@performance_monitor
@safe_mt5_call
def get_net_position_by_symbol(symbol: str, mt5_module: Any = None) -> float:
    """
    Get net position for a specific symbol.

    Args:
        symbol: Trading symbol
        mt5_module: MT5 module instance

    Returns:
        float: Net position volume (positive for long, negative for short)

    """
    if mt5_module is None:
        mt5_module = mt5

    positions = get_open_positions(mt5_module)
    if not positions:
        return 0.0

    net_position = 0.0
    for pos in positions:
        if getattr(pos, "symbol", "") == symbol:
            volume = float(getattr(pos, "volume", 0.0))
            pos_type = getattr(pos, "type", None)

            if pos_type == mt5_module.POSITION_TYPE_BUY:
                net_position += volume
            elif pos_type == mt5_module.POSITION_TYPE_SELL:
                net_position -= volume

    return net_position
