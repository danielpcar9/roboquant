import logging
from dotenv import load_dotenv

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables
load_dotenv()

# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

# Import our utilities
from mt5_utils import build_and_send_order, normalize_volume

def test_simple_trade():
    """Test simple trade execution"""
    logging.info("Starting simple trade execution test")
    
    # Initialize MT5
    if not mt5.initialize():  # type: ignore
        logging.error("Failed to initialize MT5")
        return False
    
    logging.info("MT5 initialized successfully")
    
    # Select symbol
    symbol = "XAUUSD"
    if not mt5.symbol_select(symbol, True):  # type: ignore
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()  # type: ignore
        return False
    
    logging.info(f"Symbol {symbol} selected successfully")
    
    # Get current market data
    tick = mt5.symbol_info_tick(symbol)  # type: ignore
    if not tick:
        logging.error(f"Failed to get tick data for {symbol}")
        mt5.shutdown()  # type: ignore
        return False
    
    symbol_info = mt5.symbol_info(symbol)  # type: ignore
    if not symbol_info:
        logging.error(f"Failed to get symbol info for {symbol}")
        mt5.shutdown()  # type: ignore
        return False
    
    logging.info(f"Current price - Bid: {tick.bid}, Ask: {tick.ask}")
    logging.info(f"Symbol point value: {symbol_info.point}")
    
    # Prepare trade parameters
    order_type = "BUY"  # or "SELL"
    volume = 0.01
    price = tick.ask if order_type == "BUY" else tick.bid
    point = symbol_info.point
    
    # Small SL/TP for testing
    sl_points = 100
    tp_points = 200
    
    sl = price - sl_points * point if order_type == "BUY" else price + sl_points * point
    tp = price + tp_points * point if order_type == "BUY" else price - tp_points * point
    
    logging.info(f"Trade parameters:")
    logging.info(f"  Symbol: {symbol}")
    logging.info(f"  Type: {order_type}")
    logging.info(f"  Volume: {volume}")
    logging.info(f"  Price: {price}")
    logging.info(f"  SL: {sl}")
    logging.info(f"  TP: {tp}")
    
    # Normalize volume
    normalized_volume = normalize_volume(symbol, volume)
    logging.info(f"Normalized volume: {normalized_volume}")
    
    # Try to execute a test trade
    try:
        logging.info("Attempting to execute test trade...")
        result = build_and_send_order(
            symbol=symbol,
            side=order_type,
            volume=normalized_volume,
            sl=sl,
            tp=tp,
            magic=123456,
            retries=1  # Only one retry for testing
        )
        
        if result:
            logging.info(f"Trade executed successfully!")
            logging.info(f"Result: {result}")
            logging.info(f"Order ticket: {getattr(result, 'order', 'N/A')}")
            logging.info(f"Retcode: {getattr(result, 'retcode', 'N/A')}")
            return True
        else:
            logging.error("Trade execution failed - no result returned")
            return False
            
    except Exception as e:
        logging.error(f"Exception during trade execution: {e}", exc_info=True)
        return False
    finally:
        # Always shutdown MT5
        mt5.shutdown()  # type: ignore
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    test_simple_trade()