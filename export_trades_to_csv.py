#!/usr/bin/env python3
"""
Export MetaTrader 5 trade history to CSV format compatible with Quant Analyzer.

This script connects to MT5, retrieves trade history, groups deals by position,
and exports them to CSV with performance statistics.
"""

import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta
import logging
import sys
from typing import Optional, List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ============================================================================
# CONFIGURATION
# ============================================================================
DAYS_BACK = 90  # Number of days to look back for trade history
MAGIC_NUMBER: Optional[int] = None  # Filter by magic number (None = all trades)
OUTPUT_FILE = "trades.csv"  # Output CSV file name


def initialize_mt5() -> bool:
    """
    Initialize MT5 connection.
    
    Returns:
        bool: True if initialization successful, False otherwise
    """
    if not mt5.initialize():
        logging.error("Failed to initialize MT5")
        logging.error(f"Error code: {mt5.last_error()}")
        return False
    
    # Get account info
    account_info = mt5.account_info()
    if account_info:
        logging.info(f"Connected to MT5 account: {account_info.login}")
        logging.info(f"Server: {account_info.server}")
        logging.info(f"Balance: ${account_info.balance:.2f}")
    
    return True


def get_deals_history(days_back: int, magic_number: Optional[int] = None) -> Optional[List]:
    """
    Retrieve deals history from MT5.
    
    Args:
        days_back: Number of days to look back
        magic_number: Optional magic number filter
        
    Returns:
        List of deals or None if error
    """
    # Calculate date range
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now()
    
    logging.info(f"Fetching deals from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
    
    # Get all deals
    deals = mt5.history_deals_get(from_date, to_date)
    
    if deals is None:
        logging.error("Failed to get deals history")
        return None
    
    if len(deals) == 0:
        logging.warning("No deals found in the specified period")
        return None
    
    logging.info(f"Retrieved {len(deals)} deals from MT5")
    
    # Filter by magic number if specified
    if magic_number is not None:
        deals = [d for d in deals if d.magic == magic_number]
        logging.info(f"Filtered to {len(deals)} deals with magic number {magic_number}")
    
    return deals


def group_deals_by_position(deals: List) -> Dict[int, Dict]:
    """
    Group deals by position_id to identify complete trades.
    
    Args:
        deals: List of MT5 deals
        
    Returns:
        Dictionary mapping position_id to trade data
    """
    positions = {}
    
    for deal in deals:
        position_id = deal.position_id
        
        # Skip balance operations and other non-trading deals
        if position_id == 0:
            continue
        
        if position_id not in positions:
            positions[position_id] = {
                'entry_deal': None,
                'exit_deal': None,
                'commission': 0.0,
                'swap': 0.0
            }
        
        # Accumulate commission and swap
        positions[position_id]['commission'] += deal.commission
        positions[position_id]['swap'] += deal.swap
        
        # Identify entry and exit deals
        if deal.entry == mt5.DEAL_ENTRY_IN:
            positions[position_id]['entry_deal'] = deal
        elif deal.entry == mt5.DEAL_ENTRY_OUT:
            positions[position_id]['exit_deal'] = deal
    
    # Filter out incomplete positions (no entry or no exit)
    complete_positions = {
        pos_id: data for pos_id, data in positions.items()
        if data['entry_deal'] is not None and data['exit_deal'] is not None
    }
    
    logging.info(f"Found {len(complete_positions)} complete trades (with entry and exit)")
    
    return complete_positions


def create_trade_dataframe(positions: Dict[int, Dict]) -> pd.DataFrame:
    """
    Create DataFrame from grouped positions in Quant Analyzer format.
    
    Args:
        positions: Dictionary of position data
        
    Returns:
        DataFrame with trade data
    """
    trades = []
    
    for position_id, data in positions.items():
        entry = data['entry_deal']
        exit_deal = data['exit_deal']
        
        # Determine trade type
        trade_type = 'buy' if entry.type == mt5.ORDER_TYPE_BUY else 'sell'
        
        # Calculate profit (already in exit deal, but recalculate for clarity)
        profit = exit_deal.profit
        
        trade = {
            'Ticket': position_id,
            'OpenTime': datetime.fromtimestamp(entry.time).strftime('%Y.%m.%d %H:%M'),
            'Type': trade_type,
            'Size': entry.volume,
            'Symbol': entry.symbol,
            'OpenPrice': entry.price,
            'StopLoss': 0.0,  # MT5 deals don't store SL/TP, would need to query orders
            'TakeProfit': 0.0,
            'CloseTime': datetime.fromtimestamp(exit_deal.time).strftime('%Y.%m.%d %H:%M'),
            'ClosePrice': exit_deal.price,
            'Commission': data['commission'],
            'Swap': data['swap'],
            'Profit': profit
        }
        
        trades.append(trade)
    
    # Create DataFrame and sort by open time
    df = pd.DataFrame(trades)
    df = df.sort_values('OpenTime')
    
    return df


def calculate_statistics(df: pd.DataFrame) -> Dict:
    """
    Calculate trading statistics.
    
    Args:
        df: DataFrame with trade data
        
    Returns:
        Dictionary with statistics
    """
    total_trades = len(df)
    
    if total_trades == 0:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'net_profit': 0.0,
            'profit_factor': 0.0,
            'avg_win': 0.0,
            'avg_loss': 0.0
        }
    
    # Calculate wins and losses
    winning_trades = df[df['Profit'] > 0]
    losing_trades = df[df['Profit'] < 0]
    
    win_count = len(winning_trades)
    loss_count = len(losing_trades)
    
    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0
    
    # Calculate profit metrics
    total_profit = df['Profit'].sum()
    gross_profit = winning_trades['Profit'].sum() if win_count > 0 else 0.0
    gross_loss = abs(losing_trades['Profit'].sum()) if loss_count > 0 else 0.0
    
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    avg_win = winning_trades['Profit'].mean() if win_count > 0 else 0.0
    avg_loss = losing_trades['Profit'].mean() if loss_count > 0 else 0.0
    
    return {
        'total_trades': total_trades,
        'win_count': win_count,
        'loss_count': loss_count,
        'win_rate': win_rate,
        'net_profit': total_profit,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'profit_factor': profit_factor,
        'avg_win': avg_win,
        'avg_loss': avg_loss
    }


def print_statistics(stats: Dict):
    """Print trading statistics summary."""
    print("\n" + "=" * 70)
    print("TRADE HISTORY SUMMARY")
    print("=" * 70)
    print(f"Total Trades: {stats['total_trades']}")
    print(f"Winning Trades: {stats['win_count']}")
    print(f"Losing Trades: {stats['loss_count']}")
    print(f"Win Rate: {stats['win_rate']:.2f}%")
    print(f"\nNet Profit: ${stats['net_profit']:.2f}")
    print(f"Gross Profit: ${stats['gross_profit']:.2f}")
    print(f"Gross Loss: ${stats['gross_loss']:.2f}")
    
    if stats['profit_factor'] == float('inf'):
        print(f"Profit Factor: ∞ (no losses)")
    else:
        print(f"Profit Factor: {stats['profit_factor']:.2f}")
    
    print(f"\nAverage Win: ${stats['avg_win']:.2f}")
    print(f"Average Loss: ${stats['avg_loss']:.2f}")
    
    if stats['avg_loss'] != 0:
        rr_ratio = abs(stats['avg_win'] / stats['avg_loss'])
        print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")
    
    print("=" * 70 + "\n")


def print_import_instructions(output_file: str):
    """Print instructions for importing into Quant Analyzer."""
    print("\n" + "=" * 70)
    print("QUANT ANALYZER IMPORT INSTRUCTIONS")
    print("=" * 70)
    print(f"1. Open Quant Analyzer")
    print(f"2. Go to: File → Import → CSV/Text File")
    print(f"3. Select file: {output_file}")
    print(f"4. Map columns if needed (should auto-detect format)")
    print(f"5. Click 'Import' to analyze your trades")
    print("\nColumn mapping:")
    print("  - Ticket → Position ID")
    print("  - OpenTime → Entry Time (YYYY.MM.DD HH:MM)")
    print("  - Type → Trade Direction (buy/sell)")
    print("  - Size → Volume/Lots")
    print("  - Symbol → Trading Instrument")
    print("  - OpenPrice → Entry Price")
    print("  - CloseTime → Exit Time")
    print("  - ClosePrice → Exit Price")
    print("  - Commission → Trading Commission")
    print("  - Swap → Overnight Fees")
    print("  - Profit → Net P&L")
    print("=" * 70 + "\n")


def main():
    """Main execution function."""
    print("\n" + "=" * 70)
    print("MT5 TRADE HISTORY EXPORTER FOR QUANT ANALYZER")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  Days back: {DAYS_BACK}")
    print(f"  Magic number filter: {MAGIC_NUMBER if MAGIC_NUMBER else 'None (all trades)'}")
    print(f"  Output file: {OUTPUT_FILE}")
    print("=" * 70 + "\n")
    
    # Initialize MT5
    if not initialize_mt5():
        print("\nERROR: Failed to connect to MetaTrader 5")
        print("Make sure MT5 is running and you are logged in.")
        return False
    
    try:
        # Get deals history
        deals = get_deals_history(DAYS_BACK, MAGIC_NUMBER)
        
        if deals is None or len(deals) == 0:
            logging.warning("No deals found. Cannot export.")
            return False
        
        # Group deals by position
        positions = group_deals_by_position(deals)
        
        if len(positions) == 0:
            logging.warning("No complete trades found (trades with both entry and exit).")
            return False
        
        # Create DataFrame
        df = create_trade_dataframe(positions)
        
        # Export to CSV
        df.to_csv(OUTPUT_FILE, index=False)
        logging.info(f"Successfully exported {len(df)} trades to {OUTPUT_FILE}")
        
        # Calculate and print statistics
        stats = calculate_statistics(df)
        print_statistics(stats)
        
        # Print import instructions
        print_import_instructions(OUTPUT_FILE)
        
        return True
        
    except Exception as e:
        logging.error(f"Error during export: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Shutdown MT5
        mt5.shutdown()
        logging.info("MT5 connection closed")


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
