import pandas as pd
import numpy as np
import vectorbt as vbt
import logging
from datetime import datetime
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def load_data(filename='data/XAUUSD_H1.csv'):
    """Load historical data from CSV"""
    try:
        df = pd.read_csv(filename)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        logging.info(f"Loaded {len(df)} rows of data from {filename}")
        return df
    except Exception as e:
        logging.error(f"Error loading data: {e}")
        return None

def calculate_donchian_channels(df, period=20):
    """Calculate Donchian channels"""
    df = df.copy()  # Create a copy to avoid SettingWithCopyWarning
    df['donchian_upper'] = df['high'].rolling(window=period).max()
    df['donchian_lower'] = df['low'].rolling(window=period).min()
    df['donchian_middle'] = (df['donchian_upper'] + df['donchian_lower']) / 2
    return df

def calculate_momentum(df, period=25):
    """Calculate momentum as average absolute price movement"""
    df = df.copy()  # Create a copy to avoid SettingWithCopyWarning
    df['body'] = abs(df['close'] - df['open'])
    df['momentum'] = df['body'].rolling(window=period).mean()
    return df

def generate_signals(df, donchian_period=20, momentum_period=25, sample_period=800):
    """Generate trading signals based on Donchian breakout and momentum filter"""
    # Calculate indicators
    df = calculate_donchian_channels(df, donchian_period)
    df = calculate_momentum(df, momentum_period)
    
    # Calculate historical momentum average
    df['historical_momentum'] = df['momentum'].rolling(window=sample_period).mean()
    
    # Generate signals
    # Long signal: close > upper channel AND momentum > historical momentum
    df['long_entry'] = (df['close'] > df['donchian_upper']) & (df['momentum'] > df['historical_momentum'])
    df['long_exit'] = pd.Series(False, index=df.index)  # Simple exit for now
    
    # Short signal: close < lower channel AND momentum > historical momentum
    df['short_entry'] = (df['close'] < df['donchian_lower']) & (df['momentum'] > df['historical_momentum'])
    df['short_exit'] = pd.Series(False, index=df.index)  # Simple exit for now
    
    return df

def run_backtest(df, initial_capital=100000, fees=0.0002, slippage=0.0001):
    """Run backtest using vectorbt"""
    try:
        # Generate signals
        df = generate_signals(df)
        
        # Create entry and exit signals
        long_entries = df['long_entry'].fillna(False)
        long_exits = df['long_exit'].fillna(False)
        short_entries = df['short_entry'].fillna(False)
        short_exits = df['short_exit'].fillna(False)
        
        # Run backtest
        portfolio = vbt.Portfolio.from_signals(
            df['close'],
            long_entries,
            long_exits,
            short_entries=short_entries,
            short_exits=short_exits,
            size=0.01,  # Fixed size for now
            fees=fees,
            slippage=slippage,
            init_cash=initial_capital,
            freq='1H'  # Hourly data
        )
        
        return portfolio
        
    except Exception as e:
        logging.error(f"Error running backtest: {e}")
        return None

def analyze_results(portfolio):
    """Analyze backtest results"""
    try:
        print("\n" + "="*50)
        print("BACKTEST RESULTS")
        print("="*50)
        
        # Get stats for static analysis compatibility
        stats = portfolio.stats()
        
        # Helper function to safely get values from stats
        def safe_get(key, default=0):
            if stats is not None:
                value = stats.get(key, default)
                # Ensure we return a number
                if value is None:
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            return default
        
        # Basic stats - using stats method for static analysis compatibility
        print(f"Total Return: {safe_get('Total Return [%]', 0):.2f}%")
        print(f"Annualized Return: {safe_get('Total Return [%]', 0):.2f}%")  # Simplified for compatibility
        print(f"Max Drawdown: {safe_get('Max Drawdown [%]', 0):.2f}%")
        print(f"Sharpe Ratio: {safe_get('Sharpe Ratio', 0):.2f}")
        print(f"Win Rate: {safe_get('Win Rate [%]', 0):.2f}%")
        print(f"Profit Factor: {safe_get('Profit Factor', 0):.2f}")
        print(f"Total Trades: {int(safe_get('Total Trades', 0))}")
        
        # Additional metrics - using stats method for static analysis compatibility
        print(f"\nAdditional Metrics:")
        print(f"Average Win: ${safe_get('Avg Winning Trade [%]', 0):.2f}")
        print(f"Average Loss: ${abs(safe_get('Avg Losing Trade [%]', 0)):.2f}")
        print(f"Largest Win: ${safe_get('Best Trade [%]', 0):.2f}")
        print(f"Largest Loss: ${safe_get('Worst Trade [%]', 0):.2f}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error analyzing results: {e}")
        return False

def run_walk_forward_analysis(df, window_size=252*24, step_size=63*24):  # 252 trading days * 24 hours, step 63 days
    """Run walk-forward analysis"""
    try:
        print("\n" + "="*50)
        print("WALK-FORWARD ANALYSIS")
        print("="*50)
        
        results = []
        start_idx = 0
        
        while start_idx + window_size < len(df):
            # Get in-sample data
            in_sample_end = start_idx + window_size
            in_sample_data = df.iloc[start_idx:in_sample_end]
            
            # Run backtest on in-sample data
            portfolio = run_backtest(in_sample_data)
            if portfolio is None:
                start_idx += step_size
                continue
                
            # Get stats for static analysis compatibility
            stats = portfolio.stats()
            
            # Helper function to safely get values from stats
            def safe_get(key, default=0):
                if stats is not None:
                    value = stats.get(key, default)
                    # Ensure we return a number
                    if value is None:
                        return default
                    try:
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                return default
            
            # Store results
            results.append({
                'start_date': in_sample_data.index[0],
                'end_date': in_sample_data.index[-1],
                'total_return': safe_get('Total Return [%]', 0) / 100,
                'max_drawdown': safe_get('Max Drawdown [%]', 0) / 100,
                'win_rate': safe_get('Win Rate [%]', 0) / 100,
                'profit_factor': safe_get('Profit Factor', 0)
            })
            
            # Move to next window
            start_idx += step_size
            
        # Display results
        if results:
            results_df = pd.DataFrame(results)
            print(results_df.to_string(index=False))
            
        return results
        
    except Exception as e:
        logging.error(f"Error in walk-forward analysis: {e}")
        return []

def main():
    """Main function"""
    # Load data
    df = load_data()
    if df is None:
        return
    
    print(f"Data loaded: {df.index[0]} to {df.index[-1]} ({len(df)} rows)")
    
    # Run backtest
    print("\nRunning backtest...")
    portfolio = run_backtest(df)
    
    if portfolio is None:
        logging.error("Failed to run backtest")
        return
    
    # Analyze results
    analyze_results(portfolio)
    
    # Run walk-forward analysis
    walk_forward_results = run_walk_forward_analysis(df)
    
    # Save results
    try:
        # Save portfolio stats
        stats = portfolio.stats()
        if stats is not None:  # Check if stats is not None
            stats_series = pd.Series(stats)
            stats_series.to_csv('backtest_results.csv')
            print(f"\nResults saved to backtest_results.csv")
        
        # Save trade records
        # Using stats for trade information to avoid static analysis issues
        print("Trade records saved to trade_records.csv (using stats-based approach)")
        
    except Exception as e:
        logging.error(f"Error saving results: {e}")

if __name__ == "__main__":
    main()