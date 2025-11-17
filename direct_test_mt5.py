#!/usr/bin/env python3
"""
Direct test of MT5 functions from post_mortem.py
"""

import sys
import os

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    print("Direct test of MT5 functions from post_mortem.py")
    print("=" * 50)
    
    try:
        # Import the functions directly
        from post_mortem import (
            get_mt5_trade_history,
            calculate_profit_factor_from_trades,
            calculate_sharpe_ratio_from_trades,
            calculate_win_rate_from_trades,
            get_mt5_performance_report,
            print_mt5_performance_report,
            MT5_AVAILABLE
        )
        
        print(f"MT5 Available: {MT5_AVAILABLE}")
        
        if not MT5_AVAILABLE:
            print("MT5 is not available, cannot proceed")
            return
            
        print("\nTesting get_mt5_trade_history with 7 days...")
        trades = get_mt5_trade_history(days_back=7)
        print(f"Found {len(trades)} trades")
        
        if trades:
            print("\nFirst 3 trades:")
            for i, trade in enumerate(trades[:3]):
                print(f"  Trade {i+1}: {trade['time']} - Profit: {trade['profit']}")
                
            print("\nCalculating metrics...")
            profit_factor = calculate_profit_factor_from_trades(trades)
            sharpe_ratio = calculate_sharpe_ratio_from_trades(trades)
            win_rate = calculate_win_rate_from_trades(trades)
            
            print(f"Profit Factor: {profit_factor}")
            print(f"Sharpe Ratio: {sharpe_ratio}")
            print(f"Win Rate: {win_rate}%")
            
            print("\nGenerating full report...")
            report = get_mt5_performance_report(days_back=7)
            if 'error' in report:
                print(f"Error: {report['error']}")
            else:
                print(f"Total Trades: {report['total_trades']}")
                print(f"Total Profit: ${report['total_profit']}")
                print(f"Profit Factor: {report['profit_factor']}")
                print(f"Sharpe Ratio: {report['sharpe_ratio']}")
                print(f"Win Rate: {report['win_rate']}%")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()