# open_trade.py
import os
import logging
from dotenv import load_dotenv
import metatrader5 as mt5

load_dotenv()
LOGIN = int(os.getenv("MT5_LOGIN", "0"))
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SYMBOL = "XAUUSD"
ORDER_TYPE = mt5.ORDER_TYPE_BUY
LOT = 0.01  # Ajustar según volume_min del broker
SL_PIPS = 50
TP_PIPS = 100
DEVIATION = 20

if not mt5.initialize():
    logging.error("No se pudo inicializar MT5")
    quit()

if not mt5.login(LOGIN, password=PASSWORD, server=SERVER):
    logging.error("No se pudo logear en MT5")
    mt5.shutdown()
    quit()

if not mt5.symbol_select(SYMBOL, True):
    logging.error(f"Símbolo {SYMBOL} no disponible en Market Watch")
    mt5.shutdown()
    quit()

sym_info = mt5.symbol_info(SYMBOL)
tick = mt5.symbol_info_tick(SYMBOL)
point = sym_info.point

# Calcular precio y niveles
price = tick.ask if ORDER_TYPE == mt5.ORDER_TYPE_BUY else tick.bid
sl = price - SL_PIPS * point if ORDER_TYPE == mt5.ORDER_TYPE_BUY else price + SL_PIPS * point
tp = price + TP_PIPS * point if ORDER_TYPE == mt5.ORDER_TYPE_BUY else price - TP_PIPS * point

logging.info(f"Precio: {price:.5f}, SL: {sl:.5f}, TP: {tp:.5f}")

request = {
    "action": mt5.TRADE_ACTION_DEAL,
    "symbol": SYMBOL,
    "volume": LOT,
    "type": ORDER_TYPE,
    "price": price,
    "sl": sl,
    "tp": tp,
    "deviation": DEVIATION,
    "magic": 234000,
    "comment": "test_trade",
    "type_time": mt5.ORDER_TIME_GTC,
    "type_filling": mt5.ORDER_FILLING_IOC,
}

result = mt5.order_send(request)

if result.retcode != mt5.TRADE_RETCODE_DONE:
    logging.error(f"Error al abrir orden: {result.retcode} - {result.comment}")
else:
    logging.info(f"✅ Trade abierto. Ticket: {result.order}")

# Verificar posiciones abiertas
positions = mt5.positions_get(symbol=SYMBOL)
if positions:
    logging.info(f"Posiciones abiertas: {len(positions)}")
    for pos in positions:
        logging.info(f"  Ticket: {pos.ticket}, Volume: {pos.volume}, Profit: {pos.profit:.2f}")

mt5.shutdown()