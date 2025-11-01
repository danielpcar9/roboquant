import os
import logging

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables (with error handling)
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception as e:
    logging.warning(f"Could not load .env file: {e}")

# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

def test_exness_symbols():
    """Test and analyze Exness symbols containing XAU or GOLD"""
    logging.info("Starting Exness symbol analysis")
    
    # Initialize MT5
    if not mt5.initialize():  # type: ignore
        logging.error("Failed to initialize MT5")
        return False
    
    logging.info("MT5 initialized successfully")
    
    try:
        # Get account information
        account_info = mt5.account_info()  # type: ignore
        if account_info:
            logging.info("Account Information:")
            logging.info(f"  Broker: {getattr(account_info, 'company', 'N/A')}")
            logging.info(f"  Server: {getattr(account_info, 'server', 'N/A')}")
            logging.info(f"  Balance: {getattr(account_info, 'balance', 'N/A')}")
            logging.info(f"  Leverage: {getattr(account_info, 'leverage', 'N/A')}:1")
        else:
            logging.warning("Could not retrieve account information")
        
        # Get all available symbols
        symbols = mt5.symbols_get()  # type: ignore
        if not symbols:
            logging.error("Failed to get symbols")
            mt5.shutdown()  # type: ignore
            return False
        
        # Filter symbols containing XAU or GOLD
        gold_symbols = [symbol for symbol in symbols if 'XAU' in symbol.name or 'GOLD' in symbol.name]
        
        if not gold_symbols:
            logging.warning("No XAU or GOLD symbols found")
            mt5.shutdown()  # type: ignore
            return False
        
        logging.info(f"Found {len(gold_symbols)} XAU/GOLD symbols:")
        
        # Analyze each gold symbol
        for symbol in gold_symbols:
            # Select the symbol
            if not mt5.symbol_select(symbol.name, True):  # type: ignore
                logging.warning(f"Failed to select symbol {symbol.name}")
                continue
            
            # Get symbol info
            symbol_info = mt5.symbol_info(symbol.name)  # type: ignore
            if not symbol_info:
                logging.warning(f"Failed to get info for symbol {symbol.name}")
                continue
            
            # Get current tick data
            tick = mt5.symbol_info_tick(symbol.name)  # type: ignore
            if not tick:
                logging.warning(f"Failed to get tick data for symbol {symbol.name}")
                continue
            
            # Display key information including description
            logging.info(f"Symbol: {symbol.name}")
            logging.info(f"  Description: {getattr(symbol_info, 'description', 'N/A')}")
            logging.info(f"  Spread: {getattr(symbol_info, 'spread', 'N/A')} points")
            logging.info(f"  Minimum Volume: {getattr(symbol_info, 'volume_min', 'N/A')}")
            logging.info(f"  Point Value: {getattr(symbol_info, 'point', 'N/A')}")
            logging.info(f"  Bid Price: {getattr(tick, 'bid', 'N/A')}")
            logging.info(f"  Ask Price: {getattr(tick, 'ask', 'N/A')}")
            logging.info("-" * 40)
            
            # Exness-specific information
            if 'EXNESS' in getattr(symbol_info, 'description', '').upper():
                logging.info(f"  ⚡ Exness-specific symbol detected")
        
        return True
        
    except Exception as e:
        logging.error(f"Error during symbol analysis: {e}", exc_info=True)
        return False
    finally:
        # Always shutdown MT5
        mt5.shutdown()  # type: ignore
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    test_exness_symbols()