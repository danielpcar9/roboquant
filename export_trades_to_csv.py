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
import os
from pathlib import Path
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

# Save to user's home directory for easy access
HOME_PATH = Path.home()
OUTPUT_FILE = str(HOME_PATH / "mt5_statement.html")


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
    Create DataFrame from grouped positions in MT4 statement format for Quant Analyzer.
    
    Args:
        positions: Dictionary of position data
        
    Returns:
        DataFrame with trade data
    """
    trades = []
    
    for position_id, data in positions.items():
        entry = data['entry_deal']
        exit_deal = data['exit_deal']
        
        # Determine trade type (0 = buy, 1 = sell for MT4 compatibility)
        trade_type = 0 if entry.type == mt5.ORDER_TYPE_BUY else 1
        
        # Calculate profit (already in exit deal, but recalculate for clarity)
        profit = exit_deal.profit
        
        trade = {
            'Ticket': position_id,
            'Open Time': datetime.fromtimestamp(entry.time).strftime('%Y.%m.%d %H:%M'),
            'Type': trade_type,
            'Size': entry.volume,
            'Item': entry.symbol,
            'Price': round(entry.price, 5),
            'S / L': 0.0,
            'T / P': 0.0,
            'Close Time': datetime.fromtimestamp(exit_deal.time).strftime('%Y.%m.%d %H:%M'),
            'Price': round(exit_deal.price, 5),  # Close price in same column
            'Commission': round(data['commission'], 2),
            'Taxes': 0.0,
            'Swap': round(data['swap'], 2),
            'Profit': round(profit, 2)
        }
        
        trades.append(trade)
    
    # Create DataFrame and sort by open time
    df = pd.DataFrame(trades)
    df = df.sort_values('Open Time')
    
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
    print(f"2. Go to: File → Import → MT4/MT5 Statement (HTML)")
    print(f"3. Select file: {output_file}")
    print(f"4. Quant Analyzer will automatically parse the MT5 statement format")
    print(f"5. Your trades will be imported and ready for analysis")
    print("\nNote: The HTML file mimics MT4/MT5 account statement format,")
    print("which Quant Analyzer recognizes natively.")
    print("=" * 70 + "\n")


def generate_html_statement(df: pd.DataFrame, stats: Dict) -> str:
    """
    Generate HTML statement in MT4/MT5 format.
    
    Args:
        df: DataFrame with trade data
        stats: Dictionary with statistics
        
    Returns:
        HTML string
    """
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MT5 Account Statement</title>
    <style>
        body {{ font-family: Arial, sans-serif; font-size: 12px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th {{ background-color: #ddd; padding: 8px; text-align: left; border: 1px solid #999; }}
        td {{ padding: 6px; border: 1px solid #ccc; }}
        .profit {{ color: green; }}
        .loss {{ color: red; }}
        h2 {{ color: #333; }}
    </style>
</head>
<body>
    <h2>Closed Transactions</h2>
    <table>
        <tr>
            <th>Ticket</th>
            <th>Open Time</th>
            <th>Type</th>
            <th>Size</th>
            <th>Item</th>
            <th>Price</th>
            <th>S / L</th>
            <th>T / P</th>
            <th>Close Time</th>
            <th>Price</th>
            <th>Commission</th>
            <th>Taxes</th>
            <th>Swap</th>
            <th>Profit</th>
        </tr>
'''
    
    for _, row in df.iterrows():
        profit_class = 'profit' if row['Profit'] > 0 else 'loss'
        trade_type_str = 'buy' if row['Type'] == 0 else 'sell'
        
        html += f'''        <tr>
            <td>{row['Ticket']}</td>
            <td>{row['Open Time']}</td>
            <td>{trade_type_str}</td>
            <td>{row['Size']}</td>
            <td>{row['Item']}</td>
            <td>{row['Price']}</td>
            <td>{row['S / L']}</td>
            <td>{row['T / P']}</td>
            <td>{row['Close Time']}</td>
            <td>{row['Price']}</td>
            <td>{row['Commission']}</td>
            <td>{row['Taxes']}</td>
            <td>{row['Swap']}</td>
            <td class="{profit_class}">{row['Profit']:.2f}</td>
        </tr>
'''
    
    html += f'''    </table>
    <h2>Summary</h2>
    <table style="width: 50%;">
        <tr><td><b>Total Trades:</b></td><td>{stats['total_trades']}</td></tr>
        <tr><td><b>Winning Trades:</b></td><td>{stats['win_count']}</td></tr>
        <tr><td><b>Losing Trades:</b></td><td>{stats['loss_count']}</td></tr>
        <tr><td><b>Win Rate:</b></td><td>{stats['win_rate']:.2f}%</td></tr>
        <tr><td><b>Net Profit:</b></td><td class="{'profit' if stats['net_profit'] > 0 else 'loss'}">${stats['net_profit']:.2f}</td></tr>
        <tr><td><b>Gross Profit:</b></td><td class="profit">${stats['gross_profit']:.2f}</td></tr>
        <tr><td><b>Gross Loss:</b></td><td class="loss">${stats['gross_loss']:.2f}</td></tr>
        <tr><td><b>Profit Factor:</b></td><td>{stats['profit_factor']:.2f}</td></tr>
        <tr><td><b>Average Win:</b></td><td class="profit">${stats['avg_win']:.2f}</td></tr>
        <tr><td><b>Average Loss:</b></td><td class="loss">${stats['avg_loss']:.2f}</td></tr>
    </table>
</body>
</html>
'''
    
    return html


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
        
        # Calculate and print statistics
        stats = calculate_statistics(df)
        
        # Export to HTML format like MT4/MT5 account statements
        html_content = generate_html_statement(df, stats)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logging.info(f"Successfully exported {len(df)} trades to {OUTPUT_FILE}")
        
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
