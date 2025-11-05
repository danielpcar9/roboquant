import tempfile
import os
import pandas as pd
from datetime import datetime, timedelta
from post_mortem import log_trade, analyze_recent_trades, generate_performance_report, TRADE_COLUMNS

def test_post_mortem_functionality():
    """Test the post-mortem functionality with proper data."""
    print("Testing post-mortem functionality...")
    
    # Create a temporary trades file path (but don't create the file yet)
    temp_trades_file = tempfile.mktemp(suffix='.csv')
    
    # Import post_mortem module
    import post_mortem
    
    # Store original file path
    original_file = post_mortem.TRADES_FILE
    
    try:
        # Temporarily override the TRADES_FILE path
        post_mortem.TRADES_FILE = temp_trades_file
        
        # Create test data with all required columns
        base_time = datetime.now()
        
        # Add winning trades
        for i in range(3):
            trade_data = {
                'timestamp_open': (base_time - timedelta(hours=i)).isoformat(),
                'timestamp_close': (base_time - timedelta(hours=i) + timedelta(minutes=30)).isoformat(),
                'ticket': 1000 + i,
                'symbol': 'XAUUSD',
                'side': 'BUY' if i % 2 == 0 else 'SELL',
                'volume': 0.01,
                'entry_price': 1234.56,
                'exit_price': 1235.78,
                'sl': 1230.00,
                'tp': 1240.00,
                'pnl': 12.22,
                'pnl_pct': 0.99,
                'duration_minutes': 30,
                'reason_closed': 'TP reached',
                'hour_of_day': 14
            }
            log_trade(trade_data)
        
        # Add losing trades
        for i in range(2):
            trade_data = {
                'timestamp_open': (base_time - timedelta(hours=i+3)).isoformat(),
                'timestamp_close': (base_time - timedelta(hours=i+3) + timedelta(minutes=45)).isoformat(),
                'ticket': 2000 + i,
                'symbol': 'XAUUSD',
                'side': 'SELL' if i % 2 == 0 else 'BUY',
                'volume': 0.01,
                'entry_price': 1235.78,
                'exit_price': 1234.56,
                'sl': 1240.00,
                'tp': 1230.00,
                'pnl': -8.15,
                'pnl_pct': -0.66,
                'duration_minutes': 45,
                'reason_closed': 'SL hit',
                'hour_of_day': 15
            }
            log_trade(trade_data)
        
        # Check file contents
        print("\nFile contents:")
        df = pd.read_csv(temp_trades_file)
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        print(f"First few rows:")
        print(df.head())
        
        # Analyze the trades
        print("\nAnalyzing recent trades...")
        metrics = analyze_recent_trades(n=10)
        print("Metrics:")
        for key, value in metrics.items():
            print(f"  {key}: {value}")
        
        # Generate performance report
        temp_report_file = tempfile.mktemp(suffix='.txt')
        print(f"\nGenerating performance report to {temp_report_file}...")
        generate_performance_report(temp_report_file)
        
        # Check report contents
        if os.path.exists(temp_report_file):
            print("Performance report generated successfully!")
            with open(temp_report_file, 'r') as f:
                content = f.read()
                print("Report preview (first 500 chars):")
                print(content[:500])
            os.unlink(temp_report_file)
        else:
            print("Failed to generate performance report")
            
        return True
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Restore original file path and clean up
        post_mortem.TRADES_FILE = original_file
        try:
            os.unlink(temp_trades_file)
        except Exception:
            pass

if __name__ == "__main__":
    success = test_post_mortem_functionality()
    if success:
        print("\n✅ Post-mortem functionality test passed!")
    else:
        print("\n❌ Post-mortem functionality test failed!")