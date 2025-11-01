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

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Inicializar MT5
if not mt5.initialize():  # type: ignore
    logging.error("No se pudo inicializar MT5")
    quit()

LOGIN = int(os.getenv("MT5_LOGIN", "0"))
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")

if not mt5.login(LOGIN, password=PASSWORD, server=SERVER):  # type: ignore
    logging.error("Login fallido")
    mt5.shutdown()  # type: ignore
    quit()

# Inicializar modulo de seguridad
safety = Safety(mt5_module=mt5)

# Parametros de trade
symbol = "XAUUSD"
side = "BUY"
risk_pct = 1.0

# Verificar safety checks
ok, reason = safety.check_all(new_symbol=symbol)
if not ok:
    alert_safety_violation(reason)
    logging.error("Safety check failed: %s", reason)
    mt5.shutdown()  # type: ignore
    quit()

# Obtener precios actuales
tick = mt5.symbol_info_tick(symbol)  # type: ignore
sym_info = mt5.symbol_info(symbol)  # type: ignore
point = sym_info.point

# Calcular entry y stops
price = tick.ask if side == "BUY" else tick.bid
sl_price = price - 50 * point if side == "BUY" else price + 50 * point
tp_price = price + 100 * point if side == "BUY" else price - 100 * point

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

except Exception as e:
    logging.exception("Error al ejecutar orden")
    from alerts import telegram_alert
    telegram_alert("Error al ejecutar orden: " + str(e))

mt5.shutdown()  # type: ignore