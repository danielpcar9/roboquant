#!/usr/bin/env python3
"""
Export MetaTrader 5 trade history to CSV format compatible with Quant Analyzer.

This script connects to MT5, retrieves trade history, groups deals by position,
and exports them to CSV with performance statistics.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from core.mt5_compat import mt5

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
)

# ============================================================================
# CONFIGURATION
# ============================================================================
DAYS_BACK = 90  # Number of days to look back for trade history
MAGIC_NUMBER: int | None = None  # Filter by magic number (None = all trades)

# Save to user's home directory for easy access
HOME_PATH = Path.home()
OUTPUT_FILE = str(HOME_PATH / "mt5_statement.html")


class TradeExporter:
    """Handles MT5 trade history export with statistics calculation.
    Follows Single Responsibility Principle for export-specific logic.
    """

    def __init__(self, days_back=90, magic_number=None, output_file=None):
        """Initialize exporter with configuration"""
        self.days_back = days_back
        self.magic_number = magic_number
        self.output_file = output_file or str(Path.home() / "mt5_statement.html")

    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection"""
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            logging.error(f"Error code: {mt5.last_error()}")
            return False

        account_info = mt5.account_info()
        if account_info:
            logging.info(f"Connected to MT5 account: {account_info.login}")
            logging.info(f"Server: {account_info.server}")
            logging.info(f"Balance: ${account_info.balance:.2f}")

        return True

    def get_deals_history(self) -> list | None:
        """Retrieve deals history from MT5"""
        from_date = datetime.now() - timedelta(days=self.days_back)
        to_date = datetime.now()

        logging.info(
            f"Fetching deals from {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}",
        )

        deals = mt5.history_deals_get(from_date, to_date)

        if deals is None:
            logging.error("Failed to get deals history")
            return None

        if len(deals) == 0:
            logging.warning("No deals found in the specified period")
            return None

        logging.info(f"Retrieved {len(deals)} deals from MT5")

        if self.magic_number is not None:
            deals = [d for d in deals if d.magic == self.magic_number]
            logging.info(
                f"Filtered to {len(deals)} deals with magic number {self.magic_number}",
            )

        return deals

    def group_deals_by_position(self, deals: list) -> dict[int, dict]:
        """Group deals by position_id to identify complete trades"""
        positions = {}

        for deal in deals:
            position_id = deal.position_id

            if position_id == 0:
                continue

            if position_id not in positions:
                positions[position_id] = {
                    "entry_deal": None,
                    "exit_deal": None,
                    "commission": 0.0,
                    "swap": 0.0,
                }

            positions[position_id]["commission"] += deal.commission
            positions[position_id]["swap"] += deal.swap

            if deal.entry == mt5.DEAL_ENTRY_IN:
                positions[position_id]["entry_deal"] = deal
            elif deal.entry == mt5.DEAL_ENTRY_OUT:
                positions[position_id]["exit_deal"] = deal

        complete_positions = {
            pos_id: data
            for pos_id, data in positions.items()
            if data["entry_deal"] is not None and data["exit_deal"] is not None
        }

        logging.info(
            f"Found {len(complete_positions)} complete trades (with entry and exit)",
        )
        return complete_positions

    def create_trade_dataframe(self, positions: dict[int, dict]) -> pd.DataFrame:
        """Create DataFrame from grouped positions in MT4 statement format"""
        trades = []

        for position_id, data in positions.items():
            entry = data["entry_deal"]
            exit_deal = data["exit_deal"]

            trade_type = 0 if entry.type == mt5.ORDER_TYPE_BUY else 1
            profit = exit_deal.profit

            trade = {
                "Ticket": position_id,
                "Open Time": datetime.fromtimestamp(entry.time).strftime(
                    "%Y.%m.%d %H:%M",
                ),
                "Type": trade_type,
                "Size": entry.volume,
                "Item": entry.symbol,
                "Entry Price": round(entry.price, 5),
                "S / L": 0.0,
                "T / P": 0.0,
                "Close Time": datetime.fromtimestamp(exit_deal.time).strftime(
                    "%Y.%m.%d %H:%M",
                ),
                "Exit Price": round(exit_deal.price, 5),
                "Commission": round(data["commission"], 2),
                "Taxes": 0.0,
                "Swap": round(data["swap"], 2),
                "Profit": round(profit, 2),
            }

            trades.append(trade)

        df = pd.DataFrame(trades)
        df = df.sort_values("Open Time")
        return df

    def calculate_statistics(self, df: pd.DataFrame) -> dict:
        """Calculate trading statistics"""
        total_trades = len(df)

        if total_trades == 0:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "net_profit": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }

        winning_trades = df[df["Profit"] > 0]
        losing_trades = df[df["Profit"] < 0]

        win_count = len(winning_trades)
        loss_count = len(losing_trades)
        win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0

        total_profit = df["Profit"].sum()
        gross_profit = winning_trades["Profit"].sum() if win_count > 0 else 0.0
        gross_loss = abs(losing_trades["Profit"].sum()) if loss_count > 0 else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        avg_win = winning_trades["Profit"].mean() if win_count > 0 else 0.0
        avg_loss = losing_trades["Profit"].mean() if loss_count > 0 else 0.0

        return {
            "total_trades": total_trades,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "net_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
        }

    def generate_html_statement(self, df: pd.DataFrame, stats: dict) -> str:
        """Generate HTML statement in MT4/MT5 format"""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>MT5 Account Statement</title>
    <style>
        body { font-family: Arial, sans-serif; font-size: 12px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th { background-color: #ddd; padding: 8px; text-align: left; border: 1px solid #999; }
        td { padding: 6px; border: 1px solid #ccc; }
        .profit { color: green; }
        .loss { color: red; }
        h2 { color: #333; }
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
"""

        for _, row in df.iterrows():
            profit_class = "profit" if row["Profit"] > 0 else "loss"
            trade_type_str = "buy" if row["Type"] == 0 else "sell"

            html += f'''        <tr>
            <td>{row["Ticket"]}</td>
            <td>{row["Open Time"]}</td>
            <td>{trade_type_str}</td>
            <td>{row["Size"]}</td>
            <td>{row["Item"]}</td>
            <td>{row["Price"]}</td>
            <td>{row["S / L"]}</td>
            <td>{row["T / P"]}</td>
            <td>{row["Close Time"]}</td>
            <td>{row["Price"]}</td>
            <td>{row["Commission"]}</td>
            <td>{row["Taxes"]}</td>
            <td>{row["Swap"]}</td>
            <td class="{profit_class}">{row["Profit"]:.2f}</td>
        </tr>
'''

        html += f'''    </table>
    <h2>Summary</h2>
    <table style="width: 50%;">
        <tr><td><b>Total Trades:</b></td><td>{stats["total_trades"]}</td></tr>
        <tr><td><b>Winning Trades:</b></td><td>{stats["win_count"]}</td></tr>
        <tr><td><b>Losing Trades:</b></td><td>{stats["loss_count"]}</td></tr>
        <tr><td><b>Win Rate:</b></td><td>{stats["win_rate"]:.2f}%</td></tr>
        <tr><td><b>Net Profit:</b></td><td class="{"profit" if stats["net_profit"] > 0 else "loss"}">${stats["net_profit"]:.2f}</td></tr>
        <tr><td><b>Gross Profit:</b></td><td class="profit">${stats["gross_profit"]:.2f}</td></tr>
        <tr><td><b>Gross Loss:</b></td><td class="loss">${stats["gross_loss"]:.2f}</td></tr>
        <tr><td><b>Profit Factor:</b></td><td>{stats["profit_factor"]:.2f}</td></tr>
        <tr><td><b>Average Win:</b></td><td class="profit">${stats["avg_win"]:.2f}</td></tr>
        <tr><td><b>Average Loss:</b></td><td class="loss">${stats["avg_loss"]:.2f}</td></tr>
    </table>
</body>
</html>
'''
        return html

    def export(self) -> bool:
        """Main export execution"""
        print("\n" + "=" * 70)
        print("MT5 TRADE HISTORY EXPORTER FOR QUANT ANALYZER")
        print("=" * 70)
        print("Configuration:")
        print(f"  Days back: {self.days_back}")
        print(
            f"  Magic number filter: {self.magic_number if self.magic_number else 'None (all trades)'}",
        )
        print(f"  Output file: {self.output_file}")
        print("=" * 70 + "\n")

        if not self.initialize_mt5():
            print("\nERROR: Failed to connect to MetaTrader 5")
            print("Make sure MT5 is running and you are logged in.")
            return False

        try:
            deals = self.get_deals_history()

            if deals is None or len(deals) == 0:
                logging.warning("No deals found. Cannot export.")
                return False

            positions = self.group_deals_by_position(deals)

            if len(positions) == 0:
                logging.warning(
                    "No complete trades found (trades with both entry and exit).",
                )
                return False

            df = self.create_trade_dataframe(positions)
            stats = self.calculate_statistics(df)

            html_content = self.generate_html_statement(df, stats)
            with open(self.output_file, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info(
                f"Successfully exported {len(df)} trades to {self.output_file}",
            )

            print_statistics(stats)
            print_import_instructions(self.output_file)

            return True

        except Exception as e:
            logging.exception(f"Error during export: {e}")
            import traceback

            traceback.print_exc()
            return False

        finally:
            mt5.shutdown()
            logging.info("MT5 connection closed")


def initialize_mt5() -> bool:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter()
    return exporter.initialize_mt5()


def get_deals_history(
    days_back: int, magic_number: int | None = None,
) -> list | None:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter(days_back, magic_number)
    return exporter.get_deals_history()


def group_deals_by_position(deals: list) -> dict[int, dict]:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter()
    return exporter.group_deals_by_position(deals)


def create_trade_dataframe(positions: dict[int, dict]) -> pd.DataFrame:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter()
    return exporter.create_trade_dataframe(positions)


def calculate_statistics(df: pd.DataFrame) -> dict:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter()
    return exporter.calculate_statistics(df)
    total_trades = len(df)

    if total_trades == 0:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "net_profit": 0.0,
            "profit_factor": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
        }

    # Calculate wins and losses
    winning_trades = df[df["Profit"] > 0]
    losing_trades = df[df["Profit"] < 0]

    win_count = len(winning_trades)
    loss_count = len(losing_trades)

    win_rate = (win_count / total_trades) * 100 if total_trades > 0 else 0.0

    # Calculate profit metrics
    total_profit = df["Profit"].sum()
    gross_profit = winning_trades["Profit"].sum() if win_count > 0 else 0.0
    gross_loss = abs(losing_trades["Profit"].sum()) if loss_count > 0 else 0.0

    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    avg_win = winning_trades["Profit"].mean() if win_count > 0 else 0.0
    avg_loss = losing_trades["Profit"].mean() if loss_count > 0 else 0.0

    return {
        "total_trades": total_trades,
        "win_count": win_count,
        "loss_count": loss_count,
        "win_rate": win_rate,
        "net_profit": total_profit,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
    }


def print_statistics(stats: dict):
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

    if stats["profit_factor"] == float("inf"):
        print("Profit Factor: ∞ (no losses)")
    else:
        print(f"Profit Factor: {stats['profit_factor']:.2f}")

    print(f"\nAverage Win: ${stats['avg_win']:.2f}")
    print(f"Average Loss: ${stats['avg_loss']:.2f}")

    if stats["avg_loss"] != 0:
        rr_ratio = abs(stats["avg_win"] / stats["avg_loss"])
        print(f"Risk/Reward Ratio: 1:{rr_ratio:.2f}")

    print("=" * 70 + "\n")


def print_import_instructions(output_file: str):
    """Print instructions for importing into Quant Analyzer."""
    print("\n" + "=" * 70)
    print("QUANT ANALYZER IMPORT INSTRUCTIONS")
    print("=" * 70)
    print("1. Open Quant Analyzer")
    print("2. Go to: File → Import → MT4/MT5 Statement (HTML)")
    print(f"3. Select file: {output_file}")
    print("4. Quant Analyzer will automatically parse the MT5 statement format")
    print("5. Your trades will be imported and ready for analysis")
    print("\nNote: The HTML file mimics MT4/MT5 account statement format,")
    print("which Quant Analyzer recognizes natively.")
    print("=" * 70 + "\n")


def generate_html_statement(df: pd.DataFrame, stats: dict) -> str:
    """Legacy function for backward compatibility"""
    exporter = TradeExporter()
    return exporter.generate_html_statement(df, stats)


def main():
    """Main execution function using TradeExporter class"""
    exporter = TradeExporter(DAYS_BACK, MAGIC_NUMBER, OUTPUT_FILE)
    return exporter.export()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
