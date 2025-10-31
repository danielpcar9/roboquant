import os
from datetime import datetime
from dotenv import load_dotenv
import logging
import metatrader5 as mt5

load_dotenv()

LOGIN = int(os.getenv("MT5_LOGIN", "0"))
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

print("=" * 50)
print("INICIANDO CONEXIÓN CON METATRADER 5")
print("=" * 50)

# Inicializar CON credenciales (funciona con MT5 abierto o cerrado)
if not mt5.initialize(login=LOGIN, password=PASSWORD, server=SERVER):
    logging.error("Error inicializando/conectando MT5: %s", mt5.last_error())
    quit()

logging.info("MT5 inicializado y conectado")

print("\n" + "=" * 50)
print("INFORMACIÓN DE TU CUENTA")
print("=" * 50)

account_info = mt5.account_info()
if account_info:
    print(f"Balance: ${account_info.balance:.2f}")
    print(f"Equity: ${account_info.equity:.2f}")
    print(f"Margen Libre: ${account_info.margin_free:.2f}")
    print(f"Broker: {account_info.company}")
else:
    print("No info cuenta")

# Precio Oro (XAUUSD)
symbol = "XAUUSD"
if mt5.symbol_select(symbol, True):
    tick = mt5.symbol_info_tick(symbol)
    if tick:
        print(f"\n{symbol}:")
        print(f"BID: ${tick.bid:.2f} | ASK: ${tick.ask:.2f} | Spread: ${tick.ask - tick.bid:.2f}")
        print(f"Hora: {datetime.fromtimestamp(tick.time)}")
    else:
        print("No tick – activa símbolo en MT5 Market Watch")
else:
    print(f"No se pudo seleccionar {symbol}")

mt5.shutdown()
print("\nConexión cerrada")