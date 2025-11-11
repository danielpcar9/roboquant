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

# Import our utility function
from mt5_utils import close_position_by_ticket

# Import consolidated MT5 functions
from mt5_core import initialize_mt5

# initialize_mt5 function removed - using consolidated version from mt5_core.py

def get_open_positions():
    """Get all open positions"""
    positions = mt5.positions_get()  # type: ignore
    if positions is None:
        logging.error("Failed to get positions")
        return []
    return positions

def close_all_positions():
    """Main function to close all open positions"""
    print("=== Cerrando todas las posiciones ===")
    
    # Initialize MT5
    if not initialize_mt5():
        logging.error("Failed to initialize MT5. Exiting.")
        return False
    
    try:
        # Get all open positions
        positions = get_open_positions()
        
        if not positions:
            print("No hay posiciones abiertas para cerrar.")
            mt5.shutdown()  # type: ignore
            return True
        
        total_positions = len(positions)
        print(f"Posiciones encontradas: {total_positions}")
        
        closed_count = 0
        error_count = 0
        
        # Close each position
        for i, position in enumerate(positions, 1):
            ticket = position.ticket
            symbol = position.symbol
            volume = float(position.volume)
            
            print(f"[{i}/{total_positions}] Cerrando ticket {ticket} ({symbol}, {volume} lotes)...", end=" ")
            
            try:
                # Close the position using our utility function
                success = close_position_by_ticket(ticket)
                if success:
                    print("✅")
                    closed_count += 1
                else:
                    print("❌")
                    error_count += 1
            except Exception as e:
                logging.error(f"Error closing position {ticket}: {e}")
                print("❌")
                error_count += 1
        
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