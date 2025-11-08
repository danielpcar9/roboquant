# risk_orders.py
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore
from safety import Safety
from mt5_utils import build_and_send_order, estimate_lots_by_risk
from post_mortem import log_trade
from alerts import alert_trade_opened, alert_safety_violation
# Import error handler
from error_handler import handle_exception, retry_with_exponential_backoff, MT5ConnectionError, OrderExecutionError

# Import consolidated MT5 functions
from mt5_core import initialize_mt5

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

@handle_exception
# initialize_mt5 function removed - using consolidated version from mt5_core.py

@handle_exception
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def execute_risk_order():
    """Execute a risk-based order with comprehensive error handling"""
    # Inicializar MT5
    if not initialize_mt5():
        return False

    # Inicializar modulo de seguridad
    safety = Safety(mt5_module=mt5)

    # Parametros de trade
    symbol = "XAUUSD"
    side = "BUY"
    risk_pct = 1.0

    # Verificar safety checks - MUST NOT BYPASS
    ok, reason = safety.check_all(new_symbol=symbol)
    if not ok:
        alert_safety_violation(reason)
        logging.error("Safety check failed: %s", reason)
        logging.critical("Trade execution prevented by safety checks. Aborting.")
        mt5.shutdown()  # type: ignore
        return False

    # Obtener precios actuales
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    sym_info = mt5.symbol_info(symbol)  # type: ignore
    point = sym_info.point

    # Calcular entry y stops
    price = tick.ask if side == "BUY" else tick.bid

    # Use more conservative SL/TP values for XAUUSD (in points)
    # XAUUSD typically needs wider stops due to higher volatility
    sl_points = 200  # Increased from 150 to 200 points for SL
    tp_points = 400  # Increased from 300 to 400 points for TP (2:1 ratio)

    # Calculate SL/TP with proper direction
    if side == "BUY":
        sl_price = price - sl_points * point
        tp_price = price + tp_points * point
    else:  # SELL
        sl_price = price + sl_points * point
        tp_price = price - tp_points * point

    # Log the calculated prices for debugging
    logging.info(f"Current price: {price}, SL: {sl_price}, TP: {tp_price}")
    logging.info(f"Price difference - SL: {abs(price - sl_price)/point} points, TP: {abs(price - tp_price)/point} points")

    # Ensure SL/TP are not too close to current price (minimum distance)
    min_distance_points = 100 * point  # Minimum 100 points distance
    if side == "BUY":
        if (sl_price > price - min_distance_points):
            sl_price = price - min_distance_points
        if (tp_price < price + min_distance_points * 2):
            tp_price = price + min_distance_points * 2
    else:  # SELL
        if (sl_price < price + min_distance_points):
            sl_price = price + min_distance_points
        if (tp_price > price - min_distance_points * 2):
            tp_price = price - min_distance_points * 2

    logging.info(f"Adjusted prices - Price: {price}, SL: {sl_price}, TP: {tp_price}")

    # Calcular volumen basado en riesgo
    volume = estimate_lots_by_risk(
        symbol=symbol,
        entry_price=price,
        stop_price=sl_price,
        risk_pct=risk_pct,
        mt5_module=mt5
    )

    logging.info("Volumen calculado: %s lotes para %s porciento de riesgo", volume, risk_pct)

    # Enviar orden
    try:
        result = build_and_send_order(
            symbol=symbol,
            side=side,
            volume=volume,
            sl=sl_price,
            tp=tp_price,
            mt5_module=mt5
        )
        
        # Logging para post-mortem
        log_trade({
            'timestamp_open': datetime.utcnow().isoformat(),
            'ticket': result.order,
            'symbol': symbol,
            'side': side,
            'volume': volume,
            'entry_price': result.price,
            'sl': sl_price,
            'tp': tp_price,
            'balance_before': mt5.account_info().balance,  # type: ignore
            'hour_of_day': datetime.utcnow().hour,
            'day_of_week': datetime.utcnow().weekday()
        })
        
        # Enviar alerta
        alert_trade_opened(result.order, symbol, side, volume, result.price, sl_price, tp_price)
        
        logging.info("Orden ejecutada exitosamente. Ticket: %s", result.order)
        return True

    except Exception as e:
        logging.exception("Error al ejecutar orden")
        from alerts import telegram_alert
        telegram_alert("Error al ejecutar orden: " + str(e))
        return False
    finally:
        mt5.shutdown()  # type: ignore

if __name__ == "__main__":
    execute_risk_order()