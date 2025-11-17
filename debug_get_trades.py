#!/usr/bin/env python3
"""
Debug the get_mt5_trade_history function
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_get_mt5_trade_history(days_back=30, magic_number=None):
    """
    Debug version of get_mt5_trade_history with detailed logging
    """
    try:
        import MetaTrader5 as mt5
        
        print(f"Debug: MT5 available and importing correctly")
        
        # Initialize MT5 like in the working script
        print("Initializing MT5...")
        if not mt5.initialize():  # type: ignore
            print("Failed to initialize MT5")
            return []
            
        print("MT5 initialized successfully!")
        
        # Get history for the specified period
        from_date = datetime.now() - timedelta(days=days_back)
        to_date = datetime.now()
        
        print(f"Debug: Requesting deals from {from_date} to {to_date}")
        
        # Get deals from history
        deals = mt5.history_deals_get(from_date, to_date)  # type: ignore
        
        print(f"Debug: MT5 returned {len(deals) if deals else 0} deals")
        
        if not deals or len(deals) == 0:
            print("Debug: No trade history found")
            mt5.shutdown()  # type: ignore
            return []
        
        # Convert to list and filter
        trades = []
        print(f"Debug: Processing {len(deals)} deals")
        
        entry_out_count = 0
        magic_match_count = 0
        
        for i, deal in enumerate(deals):
            if i < 5:  # Show first 5 deals for debugging
                print(f"Debug: Deal {i+1} - Time: {deal.time}, Profit: {deal.profit}, Entry: {getattr(deal, 'entry', 'NO ENTRY')}, Magic: {getattr(deal, 'magic', 'NO MAGIC')}")
            
            # Filter by magic number if specified
            if magic_number is not None:
                deal_magic = getattr(deal, 'magic', None)
                if deal_magic != magic_number:
                    continue
                else:
                    magic_match_count += 1
            
            # Only consider exit deals (not balance operations)
            deal_entry = getattr(deal, 'entry', None)
            if deal_entry == mt5.DEAL_ENTRY_OUT:  # type: ignore
                entry_out_count += 1
                trades.append({
                    'time': datetime.fromtimestamp(deal.time),
                    'symbol': deal.symbol,
                    'profit': deal.profit,
                    'volume': deal.volume,
                    'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL'  # type: ignore
                })
        
        print(f"Debug: Found {entry_out_count} DEAL_ENTRY_OUT deals")
        if magic_number is not None:
            print(f"Debug: Found {magic_match_count} deals matching magic number {magic_number}")
        
        # Shutdown MT5
        mt5.shutdown()  # type: ignore
        print("\nMT5 shutdown successfully")
        
        return trades
        
    except Exception as e:
        print(f"Debug: Error in get_mt5_trade_history: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    print("Debugging get_mt5_trade_history function")
    print("=" * 50)
    
    try:
        trades = debug_get_mt5_trade_history(days_back=7)
        print(f"\nFinal result: Found {len(trades)} filtered trades")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()