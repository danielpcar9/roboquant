# risk_orders.py
import logging
from datetime import datetime

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5, MT5_AVAILABLE
from dotenv import load_dotenv

from analysis.post_mortem import log_trade

# Import consolidated MT5 functions
from brokers.mt5_core import initialize_mt5
from brokers.mt5_utils import build_and_send_order, estimate_lots_by_risk

# Import ATR calculation function
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator as MarketDataService,
)
from risk.safety import Safety
from services.alerts import alert_safety_violation, alert_trade_opened

# Import error handler
from services.error_handler import handle_exception, retry_with_exponential_backoff

# Initialize market data service for ATR calculation
market_data_service = MarketDataService()

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


@handle_exception
# initialize_mt5 function removed - using consolidated version from mt5_core.py

@handle_exception
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def execute_risk_order():
    """Execute a risk-based order with comprehensive error handling"""
    # Initialize MT5
    if not initialize_mt5():
        return False

    try:
        # Initialize safety module
        safety = Safety(mt5_module=mt5)

        # Execute the trade with proper safety checks
        return _execute_controlled_trade(safety)

    except Exception as e:
        logging.exception("Error executing risk order")
        _send_error_alert(e)
        return False
    finally:
        mt5.shutdown()  # type: ignore


def _execute_controlled_trade(safety):
    """Execute trade with safety controls and risk management."""
    # Trade parameters
    symbol = "XAUUSD"
    side = "BUY"
    risk_pct = 1.0

    # Perform safety checks - MUST NOT BYPASS
    if not _perform_safety_checks(safety, symbol):
        return False

    # Get current prices and market data
    tick, sym_info = _get_market_data(symbol)
    if not tick or not sym_info:
        return False

    point = sym_info.point

    # Calculate entry and stops using ATR-based approach
    price = _calculate_entry_price(tick, side)
    sl_price, tp_price = _calculate_atr_based_stops(symbol, price, side, point)

    # Ensure minimum distance requirements
    sl_price, tp_price = _adjust_minimum_distances(sl_price, tp_price, price, side, point)

    _log_price_calculations(price, sl_price, tp_price, point)

    # Calculate risk-based volume
    volume = _calculate_risk_volume(symbol, price, sl_price, risk_pct)

    # Execute the order
    return _send_trade_order(symbol, side, volume, sl_price, tp_price)


def _perform_safety_checks(safety, symbol):
    """Perform all required safety checks."""
    ok, reason = safety.check_all(new_symbol=symbol)
    if not ok:
        alert_safety_violation(reason)
        logging.error("Safety check failed: %s", reason)
        logging.critical("Trade execution prevented by safety checks. Aborting.")
        return False
    return True


def _get_market_data(symbol):
    """Get current market data for the symbol."""
    try:
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        sym_info = mt5.symbol_info(symbol)  # type: ignore
        return tick, sym_info
    except Exception as e:
        logging.error("Failed to get market data for %s: %s", symbol, e)
        return None, None


def _calculate_entry_price(tick, side):
    """Calculate entry price based on order side."""
    return tick.ask if side == "BUY" else tick.bid


def _calculate_atr_based_stops(symbol, price, side, point):
    """Calculate stop loss and take profit using ATR methodology."""
    # Use ATR-based SL/TP values for XAUUSD
    # XAUUSD typically needs wider stops due to higher volatility
    atr = market_data_service.calculate_atr(symbol, 14)  # 14-period ATR
    if atr is None:
        atr = 5.0  # Default ATR estimate

    # Use ATR multipliers (LOW RISK profile)
    sl_multiplier = 3.0
    tp_multiplier = 6.0

    sl_points = sl_multiplier * atr
    tp_points = tp_multiplier * atr

    # Calculate SL/TP with proper direction
    if side == "BUY":
        sl_price = price - sl_points * point
        tp_price = price + tp_points * point
    else:  # SELL
        sl_price = price + sl_points * point
        tp_price = price - tp_points * point

    return sl_price, tp_price


def _adjust_minimum_distances(sl_price, tp_price, price, side, point):
    """Ensure SL/TP maintain minimum distance from current price."""
    min_distance_points = 100 * point  # Minimum 100 points distance

    if side == "BUY":
        if sl_price > price - min_distance_points:
            sl_price = price - min_distance_points
        if tp_price < price + min_distance_points * 2:
            tp_price = price + min_distance_points * 2
    else:  # SELL
        if sl_price < price + min_distance_points:
            sl_price = price + min_distance_points
        if tp_price > price - min_distance_points * 2:
            tp_price = price - min_distance_points * 2

    return sl_price, tp_price


def _log_price_calculations(price, sl_price, tp_price, point):
    """Log price calculations for debugging."""
    logging.info(f"Current price: {price}, SL: {sl_price}, TP: {tp_price}")
    logging.info(
        f"Price difference - SL: {abs(price - sl_price) / point} points, TP: {abs(price - tp_price) / point} points",
    )
    logging.info(f"Adjusted prices - Price: {price}, SL: {sl_price}, TP: {tp_price}")


def _calculate_risk_volume(symbol, price, sl_price, risk_pct):
    """Calculate position size based on risk percentage."""
    volume = estimate_lots_by_risk(
        symbol=symbol,
        entry_price=price,
        stop_price=sl_price,
        risk_pct=risk_pct,
        mt5_module=mt5,
    )

    logging.info(
        "Volumen calculado: %s lotes para %s porciento de riesgo", volume, risk_pct,
    )
    return volume


def _send_trade_order(symbol, side, volume, sl_price, tp_price):
    """Send the trade order with all parameters."""
    try:
        result = build_and_send_order(
            symbol=symbol,
            side=side,
            volume=volume,
            sl=sl_price,
            tp=tp_price,
            mt5_module=mt5,
        )

        # Logging para post-mortem
        _log_trade_execution(result, symbol, side, volume, sl_price, tp_price)

        # Enviar alerta
        alert_trade_opened(
            result.order, symbol, side, volume, result.price, sl_price, tp_price,
        )

        logging.info("Orden ejecutada exitosamente. Ticket: %s", result.order)
        return True

    except Exception as e:
        logging.exception("Error al ejecutar orden")
        _send_error_alert(e)
        return False


def _log_trade_execution(result, symbol, side, volume, sl_price, tp_price):
    """Log trade execution details for post-mortem analysis."""
    log_trade(
        {
            "timestamp_open": datetime.utcnow().isoformat(),
            "ticket": result.order,
            "symbol": symbol,
            "side": side,
            "volume": volume,
            "entry_price": result.price,
            "sl": sl_price,
            "tp": tp_price,
            "balance_before": mt5.account_info().balance,  # type: ignore
            "hour_of_day": datetime.utcnow().hour,
            "day_of_week": datetime.utcnow().weekday(),
        },
    )


def _send_error_alert(error):
    """Send error alert via Telegram."""
    from services.alerts import telegram_alert
    telegram_alert("Error al ejecutar orden: " + str(error))


if __name__ == "__main__":
    execute_risk_order()
