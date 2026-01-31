"""
Risk Calculator Module
Provides risk-based lot calculation functions
"""

import logging
from typing import Any

import MetaTrader5 as mt5  # type: ignore


def estimate_lots_by_risk(
    symbol: str,
    entry_price: float,
    stop_price: float,
    risk_pct: float,
    mt5_module: Any = None,
) -> float:
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


def _get_account_info(mt5_module: Any):
    """Get MT5 account information."""
    account_info = mt5_module.account_info()  # type: ignore
    if not account_info:
        logging.error("No se pudo obtener informacion de cuenta")
    return account_info


def _get_default_volume(symbol: str, mt5_module: Any) -> float:
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
            # Fallback to calculated value
            tick_value = sym_info.point * sym_info.trade_contract_size
        return tick_value


def _apply_safety_limits(lots, symbol, sym_info, mt5_module):
    """Apply minimum, maximum, and step size limits."""
    # Get symbol volume limits
    min_lot = sym_info.volume_min
    max_lot = sym_info.volume_max
    lot_step = sym_info.volume_step

    # Apply minimum lot size
    lots = max(lots, min_lot)

    # Apply maximum lot size
    lots = min(lots, max_lot)

    # Round to nearest lot step
    if lot_step > 0:
        lots = round(lots / lot_step) * lot_step

    # Final validation
    lots = max(min_lot, min(lots, max_lot))

    return lots


def _log_risk_calculation(balance, risk_amount, entry_price, stop_price, final_lots, sym_info):
    """Log risk calculation details."""
    logging.info(
        f"Risk calc: Balance=${balance:.2f}, Risk=${risk_amount:.2f}, "
        f"Entry={entry_price:.5f}, Stop={stop_price:.5f}, "
        f"Lot size={final_lots:.2f}, Min={sym_info.volume_min:.2f}, Max={sym_info.volume_max:.2f}"
    )
