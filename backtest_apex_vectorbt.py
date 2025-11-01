import vectorbt as vbt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def load_data(symbol="XAUUSD", timeframe="H1", days_back=1825):
    """Load data from CSV file"""
    try:
        filename = f"data/{symbol}_{timeframe}.csv"
        if not os.path.exists(filename):
            logging.error(f"Data file {filename} not found")
            return None
            
        df = pd.read_csv(filename)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        logging.info(f"Loaded {len(df)} rows of data for {symbol}")
        return df
    except Exception as e:
        logging.error(f"Error loading data: {e}")
        return None

def calculate_donchian_channels(df, period=20):
    """Calculate Donchian channels"""
    df['donchian_upper'] = df['high'].rolling(window=period).max()
    df['donchian_lower'] = df['low'].rolling(window=period).min()
    return df

def calculate_momentum(df, lookback=25, sample_period=800):
    """Calculate momentum indicators"""
    # Current momentum (short-term)
    df['momentum'] = abs(df['close'] - df['open']).rolling(window=lookback).mean()
    
    # Historical momentum (long-term)
    df['historical_momentum'] = abs(df['close'] - df['open']).rolling(window=sample_period).mean()
    
    return df

def generate_signals(df, donchian_period=20, momentum_period=25, sample_period=800, 
                     sl_points=50, tp_points=100):
    """Generate trading signals with proper exits"""
    # Calculate indicators
    df = calculate_donchian_channels(df, donchian_period)
    df = calculate_momentum(df, momentum_period, sample_period)
    
    # Calcular SL/TP para cada potencial entrada
    point_value = 0.01  # Para oro
    
    # Para LONG entries
    df['sl_long'] = df['close'] - (sl_points * point_value)
    df['tp_long'] = df['close'] + (tp_points * point_value)
    
    # Para SHORT entries
    df['sl_short'] = df['close'] + (sl_points * point_value)
    df['tp_short'] = df['close'] - (tp_points * point_value)
    
    # Entry signals
    df['long_entry'] = (df['close'] > df['donchian_upper']) & \
                       (df['momentum'] > df['historical_momentum'])
    df['short_entry'] = (df['close'] < df['donchian_lower']) & \
                        (df['momentum'] > df['historical_momentum'])
    
    # EXIT signals - activar cuando precio toca SL o TP
    # IMPORTANTE: Usar shift(1) porque SL/TP se calculan en la barra de entrada
    df['long_exit'] = (df['low'] <= df['sl_long'].shift(1)) | \
                      (df['high'] >= df['tp_long'].shift(1))
    
    df['short_exit'] = (df['high'] >= df['sl_short'].shift(1)) | \
                       (df['low'] <= df['tp_short'].shift(1))
    
    return df

def run_backtest(df, initial_capital=10000, lot_size=0.01, sl_points=50, tp_points=100):
    """Run backtest with VectorBT"""
    try:
        # Generate signals
        df = generate_signals(df, sl_points=sl_points, tp_points=tp_points)
        
        # Create portfolio
        portfolio = vbt.Portfolio.from_signals(
            df['close'],
            entries=df['long_entry'],
            exits=df['long_exit'],
            short_entries=df['short_entry'],
            short_exits=df['short_exit'],
            init_cash=initial_capital,
            fees=0.001,  # 0.1% commission
            slippage=0.0001,  # 1 pip slippage
            size=lot_size,
            size_type='amount'
        )
        
        # Print results
        print("\n" + "="*50)
        print("BACKTEST RESULTS")
        print("="*50)
        print(f"Total Return: {portfolio.total_return() * 100:.2f}%")
        print(f"Total Trades: {portfolio.trades.count()}")
        print(f"Win Rate: {portfolio.win_rate() * 100:.2f}%")
        print(f"Profit Factor: {portfolio.profit_factor():.2f}")
        print(f"Max Drawdown: {portfolio.max_drawdown() * 100:.2f}%")
        print(f"Sharpe Ratio: {portfolio.sharpe_ratio():.2f}")
        
        # Plot results
        fig = portfolio.plot()
        fig.write_html("backtest_results.html")
        print(f"\nResults saved to backtest_results.html")
        
        # Save trade log
        trades = portfolio.trades.records_readable
        trades.to_csv("backtest_trades.csv", index=False)
        print(f"Trade log saved to backtest_trades.csv")
        
        return portfolio
        
    except Exception as e:
        logging.error(f"Error running backtest: {e}")
        return None

def main():
    """Main function"""
    logging.info("Starting backtest...")
    
    # Load data
    df = load_data("XAUUSD", "H1", 1825)  # ~5 years of hourly data
    if df is None:
        return
    
    # Run backtest with optimized parameters
    portfolio = run_backtest(
        df, 
        initial_capital=10000, 
        lot_size=0.01, 
        sl_points=150,    # Updated for gold
        tp_points=300     # Updated for gold
    )
    
    if portfolio:
        logging.info("Backtest completed successfully")
    else:
        logging.error("Backtest failed")

if __name__ == "__main__":
    main()