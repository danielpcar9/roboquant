#!/usr/bin/env python3
"""
Test script for MT5 performance metrics
"""

import sys
import os

# Add the current directory to the path so we can import post_mortem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Test MT5 performance metrics"""
    print("Testing MT5 Performance Metrics")
    print("=" * 50)
    
    # Test the MT5 performance report
    try:
        # Import and initialize MT5 directly
        import MetaTrader5 as mt5
        from post_mortem import print_mt5_performance_report
        
        if not mt5.initialize():
            print("Failed to initialize MT5")
            return
            
        print("MT5 initialized successfully")
        print_mt5_performance_report(days_back=30)  # Default to 30 days
        mt5.shutdown()
        
    except Exception as e:
        print(f"Error testing MT5 performance metrics: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()