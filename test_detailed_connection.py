import logging
import os
from dotenv import load_dotenv

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables
load_dotenv()

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

def test_mt5_detailed():
    """Detailed MT5 connection test"""
    logging.info("Starting detailed MT5 connection test")
    
    # Get credentials
    login = int(os.getenv('MT5_LOGIN', '0'))
    password = os.getenv('MT5_PASSWORD', '')
    server = os.getenv('MT5_SERVER', '')
    
    logging.info(f"MT5 Credentials - Login: {login}, Server: {server}")
    
    # Test basic initialization
    logging.info("Attempting basic MT5 initialization...")
    if not mt5.initialize():  # type: ignore
        logging.error("Failed to initialize MT5")
        error = mt5.last_error()  # type: ignore
        logging.error(f"MT5 initialization error: {error}")
        return False
    
    logging.info("MT5 initialized successfully")
    
    # Test login if credentials are provided
    if login and password and server:
        logging.info("Attempting to login with credentials...")
        authorized = mt5.login(login, password=password, server=server)  # type: ignore
        if authorized:
            logging.info("Login successful!")
            
            # Get account info
            account_info = mt5.account_info()  # type: ignore
            if account_info:
                logging.info(f"Account Info - Balance: {account_info.balance}, Equity: {account_info.equity}")
            else:
                logging.error("Failed to get account info")
        else:
            logging.error("Login failed")
            error = mt5.last_error()  # type: ignore
            logging.error(f"Login error: {error}")
    
    # Test symbol operations
    symbol = "XAUUSD"
    logging.info(f"Testing symbol operations for {symbol}")
    
    # Initialize variables
    tick = None
    symbol_info = None
    
    # Select symbol
    if mt5.symbol_select(symbol, True):  # type: ignore
        logging.info(f"Symbol {symbol} selected successfully")
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if symbol_info:
            logging.info(f"Symbol info - Name: {symbol_info.name}, Point: {symbol_info.point}")
        else:
            logging.error(f"Failed to get symbol info for {symbol}")
        
        # Get tick data
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if tick:
            logging.info(f"Tick data - Bid: {tick.bid}, Ask: {tick.ask}, Last: {tick.last}")
        else:
            logging.error(f"Failed to get tick data for {symbol}")
    else:
        logging.error(f"Failed to select symbol {symbol}")
    
    # Test order preparation (without sending)
    logging.info("Testing order preparation...")
    if tick and symbol_info:
        price = tick.ask  # BUY price
        point = symbol_info.point
        sl = price - 50 * point
        tp = price + 100 * point
        
        logging.info(f"Prepared order - Price: {price}, SL: {sl}, TP: {tp}")
        
        # Check if we can get positions
        positions = mt5.positions_get(symbol=symbol)  # type: ignore
        logging.info(f"Current positions: {positions}")
    else:
        logging.warning("Could not prepare order due to missing tick or symbol info")
    
    # Shutdown
    mt5.shutdown()  # type: ignore
    logging.info("MT5 connection closed")
    return True

if __name__ == "__main__":
    test_mt5_detailed()