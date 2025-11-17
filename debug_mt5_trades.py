#!/usr/bin/env python3
"""
Debug script to check MT5 trade filtering
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("Debugging MT5 trade filtering...")
    print("=" * 50)
    
    try:
        import MetaTrader5 as mt5
        
        # Initialize MT5
        print("Initializing MT5...")
        if not mt5.initialize():  # type: ignore
            print("Failed to initialize MT5")
            return
            
        print("MT5 initialized successfully!")
        
        # Get deals for last 7 days
        print("\nFetching trade history...")
        from_date = datetime.now() - timedelta(days=7)
        to_date = datetime.now()
        
        deals = mt5.history_deals_get(from_date, to_date)  # type: ignore
        print(f"Total deals found: {len(deals) if deals else 0}")
        
        # Check what attributes are available in the deals
        if deals and len(deals) > 0:
            print("\nAnalyzing deal attributes...")
            sample_deal = deals[0]
            print(f"Sample deal attributes: {dir(sample_deal)}")
            
            # Check specific attributes we're interested in
            print(f"Deal entry attribute: {getattr(sample_deal, 'entry', 'NOT FOUND')}")
            print(f"Deal type attribute: {getattr(sample_deal, 'type', 'NOT FOUND')}")
            print(f"Deal magic attribute: {getattr(sample_deal, 'magic', 'NOT FOUND')}")
            
            # Count different types of deals
            entry_out_count = 0
            entry_in_count = 0
            other_count = 0
            
            for deal in deals:
                entry = getattr(deal, 'entry', None)
                if entry == mt5.DEAL_ENTRY_OUT:  # type: ignore
                    entry_out_count += 1
                elif entry == mt5.DEAL_ENTRY_IN:  # type: ignore
                    entry_in_count += 1
                else:
                    other_count += 1
                    
            print(f"\nDeal entry breakdown:")
            print(f"  DEAL_ENTRY_OUT: {entry_out_count}")
            print(f"  DEAL_ENTRY_IN: {entry_in_count}")
            print(f"  Other/Unknown: {other_count}")
            
            # Test our filtering logic
            print("\nTesting our filtering logic...")
            filtered_trades = []
            for deal in deals:
                # Only consider exit deals (not balance operations)
                if getattr(deal, 'entry', None) == mt5.DEAL_ENTRY_OUT:  # type: ignore
                    filtered_trades.append({
                        'time': datetime.fromtimestamp(deal.time),
                        'symbol': deal.symbol,
                        'profit': deal.profit,
                        'volume': deal.volume,
                        'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL'  # type: ignore
                    })
            
            print(f"Filtered trades (DEAL_ENTRY_OUT only): {len(filtered_trades)}")
            
            # Show some filtered trades
            if filtered_trades:
                print("\nFirst 3 filtered trades:")
                for i, trade in enumerate(filtered_trades[:3]):
                    print(f"  Trade {i+1}: {trade['time']} - {trade['symbol']} - Profit: {trade['profit']} - Type: {trade['type']}")
        
        # Shutdown MT5
        mt5.shutdown()  # type: ignore
        print("\nMT5 shutdown successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()