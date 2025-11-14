#!/usr/bin/env python3
"""
Test script for MT5 performance metrics
"""

import sys
import os

# Add the current directory to the path so we can import post_mortem
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from post_mortem import print_mt5_performance_report

def main():
    """Test MT5 performance metrics"""
    print("Testing MT5 Performance Metrics")
    print("=" * 50)
    
    # Test the MT5 performance report
    try:
        print_mt5_performance_report(days_back=30)
    except Exception as e:
        print(f"Error testing MT5 performance metrics: {e}")
        print("This might be expected if MT5 is not initialized or no trades are found.")

if __name__ == "__main__":
    main()