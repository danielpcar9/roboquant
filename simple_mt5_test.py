#!/usr/bin/env python3
"""
Simple test to check MT5 connectivity and trade history
"""

import sys
import os
from datetime import datetime, timedelta

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("Testing MT5 connectivity and trade history...")
    print("=" * 50)
    
    try:
        import MetaTrader5 as mt5
        
        # Initialize MT5
        print("Initializing MT5...")
        if not mt5.initialize():  # type: ignore
            print("Failed to initialize MT5")
            return
            
        print("MT5 initialized successfully!")
        
        # Get account info
        account_info = mt5.account_info()  # type: ignore
        if account_info:
            print(f"Account: {account_info.login}")
            print(f"Balance: {account_info.balance}")
            print(f"Equity: {account_info.equity}")
        else:
            print("Failed to get account info")
            
        # Get deals for last 7 days
        print("\nFetching trade history...")
        from_date = datetime.now() - timedelta(days=7)
        to_date = datetime.now()
        
        deals = mt5.history_deals_get(from_date, to_date)  # type: ignore
        print(f"Found {len(deals) if deals else 0} deals in the last 7 days")
        
        # Show some details about the deals
        if deals and len(deals) > 0:
            print(f"Showing first 5 deals:")
            for i, deal in enumerate(deals[:5]):
                print(f"  Deal {i+1}: {deal.time} - {deal.symbol} - Profit: {deal.profit}")
        
        # Shutdown MT5
        mt5.shutdown()  # type: ignore
        print("\nMT5 shutdown successfully")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()