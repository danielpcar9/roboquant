import os
import pandas as pd
import metatrader5 as mt5
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def initialize_mt5():
    """Initialize MT5 connection"""
    try:
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            return False
            
        logging.info("MT5 initialized successfully")
        return True
    except Exception as e:
        logging.error(f"Error initializing MT5: {e}")
        return False

def get_historical_data(symbol, timeframe, days_back=365):
    """Get historical data from MT5"""
    try:
        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)
        
        # Get rates
        rates = mt5.copy_rates_range(symbol, timeframe, from_date, to_date)
        
        if rates is None or len(rates) == 0:
            logging.error(f"Failed to get rates for {symbol}")
            return None
            
        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Set time as index
        df.set_index('time', inplace=True)
        
        logging.info(f"Retrieved {len(df)} rows of data for {symbol}")
        return df
        
    except Exception as e:
        logging.error(f"Error getting historical data: {e}")
        return None

def export_data(symbol="XAUUSD", timeframe=mt5.TIMEFRAME_H1, days_back=1825):
    """Export historical data to CSV"""
    try:
        # Create data directory if it doesn't exist
        data_dir = "data"
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logging.info(f"Created directory: {data_dir}")
        
        # Get historical data
        logging.info(f"Getting {days_back} days of {symbol} data...")
        df = get_historical_data(symbol, timeframe, days_back)
        
        if df is None:
            logging.error("Failed to get historical data")
            return False
            
        # Save to CSV
        filename = f"{data_dir}/{symbol}_{mt5.TimeFrameToString(timeframe)}.csv"
        df.to_csv(filename)
        logging.info(f"Data saved to {filename}")
        
        # Display basic info
        print(f"\nData Summary:")
        print(f"Symbol: {symbol}")
        print(f"Timeframe: {mt5.TimeFrameToString(timeframe)}")
        print(f"Rows: {len(df)}")
        print(f"Date Range: {df.index[0]} to {df.index[-1]}")
        print(f"File: {filename}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error exporting data: {e}")
        return False

def main():
    """Main function"""
    # Initialize MT5
    if not initialize_mt5():
        return
    
    try:
        # Export data for XAUUSD (Gold) H1 timeframe
        export_data("XAUUSD", mt5.TIMEFRAME_H1, 1825)  # ~5 years of data
        
        # You can add more symbols/timeframes here if needed
        # export_data("EURUSD", mt5.TIMEFRAME_H1, 1825)
        # export_data("XAUUSD", mt5.TIMEFRAME_M15, 365)  # 1 year of 15-minute data
        
    except Exception as e:
        logging.error(f"Error in main: {e}")
    finally:
        # Shutdown MT5
        mt5.shutdown()
        logging.info("MT5 connection closed")

if __name__ == "__main__":
    main()