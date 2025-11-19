#!/usr/bin/env python3
"""
Script to close all open positions in MetaTrader 5
"""

import os
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

# Import our MT5Gateway
from brokers.mt5_utils import MT5Gateway

# Import consolidated MT5 functions
from brokers.mt5_core import initialize_mt5

def close_all_positions():
    """Main function to close all open positions using MT5Gateway"""
    print("=== Cerrando todas las posiciones ===")
    
    # Initialize MT5
    if not initialize_mt5():
        logging.error("Failed to initialize MT5. Exiting.")
        return False
    
    try:
        gateway = MT5Gateway()
        
        # Get positions count first
        positions = gateway.get_open_positions()
        if not positions:
            print("No hay posiciones abiertas para cerrar.")
            mt5.shutdown()  # type: ignore
            return True
        
        total_positions = len(positions)
        print(f"Posiciones encontradas: {total_positions}")
        
        # Close all using gateway
        closed_count, error_count = gateway.close_all_positions()
        
        # Print summary
        print("\nRESUMEN:")
        print(f"- Cerradas exitosamente: {closed_count}")
        print(f"- Errores: {error_count}")
        
        return error_count == 0
    
    except Exception as e:
        logging.error(f"Error in close_all_positions: {e}")
        return False
    finally:
        # Always shutdown MT5
        try:
            mt5.shutdown()  # type: ignore
            logging.info("MT5 shutdown completed")
        except Exception as e:
            logging.error(f"Error shutting down MT5: {e}")

def main():
    """Main entry point"""
    try:
        success = close_all_positions()
        if success:
            logging.info("All positions closed successfully")
        else:
            logging.warning("Some positions failed to close")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        print("❌ Error inesperado:", e)

if __name__ == "__main__":
    main()