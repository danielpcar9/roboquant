import MetaTrader5 as mt5
import os
from datetime import datetime, timedelta
import pytz

OUTPUT_PATH = os.path.expanduser(r"C:\Users\edgar\MT5_statement.html")
DAYS_BACK = int(os.getenv("MT5_EXPORT_DAYS_BACK", "90"))
SYMBOL_FILTER = os.getenv("MT5_EXPORT_SYMBOL", "")  # e.g., "XAUUSD" or empty for all

HTML_HEADER = """
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Account History Report</title>
<style>
body {{ font-family: Arial, sans-serif; }}
 table {{ border-collapse: collapse; width: 100%; }}
 th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 12px; }}
 th {{ background-color: #f2f2f2; text-align: left; }}
 .right {{ text-align: right; }}
</style>
</head>
<body>
<h2>Account History Report</h2>
<table>
<tr><th>From</th><td>{start}</td></tr>
<tr><th>To</th><td>{end}</td></tr>
<tr><th>Symbol</th><td>{symbol}</td></tr>
</table>
<h3>Deals</h3>
<table>
<thead>
<tr>
  <th>Ticket</th>
  <th>Open Time</th>
  <th>Type</th>
  <th>Size</th>
  <th>Symbol</th>
  <th>Price</th>
  <th>S/L</th>
  <th>T/P</th>
  <th>Close Time</th>
  <th>Close Price</th>
  <th>Commission</th>
  <th>Taxes</th>
  <th>Swap</th>
  <th>Profit</th>
</tr>
</thead>
<tbody>
"""

HTML_FOOTER = """
</tbody>
</table>
</body>
</html>
"""

TYPE_MAP = {
    mt5.DEAL_TYPE_BUY: "Buy",
    mt5.DEAL_TYPE_SELL: "Sell",
}


def format_dt(ts: int) -> str:
    # MT5 times are in UTC
    dt = datetime.utcfromtimestamp(ts).replace(tzinfo=pytz.UTC)
    return dt.strftime("%Y.%m.%d %H:%M")


def main():
    if not mt5.initialize():
        print("❌ MT5 initialize failed:", mt5.last_error())
        return

    utc = pytz.UTC
    end_env = os.getenv("MT5_EXPORT_END", "")
    start_env = os.getenv("MT5_EXPORT_START", "")
    try:
        if end_env:
            end = utc.localize(datetime.strptime(end_env, "%Y.%m.%d %H:%M"))
        else:
            end = datetime.now(utc)
    except Exception:
        end = datetime.now(utc)
    try:
        if start_env:
            start_naive = datetime.strptime(start_env, "%Y.%m.%d %H:%M")
            start = utc.localize(start_naive)
        else:
            start = end - timedelta(days=DAYS_BACK)
    except Exception:
        start = end - timedelta(days=DAYS_BACK)

    # Get deals within period
    deals = mt5.history_deals_get(start, end)
    if deals is None:
        print("❌ history_deals_get failed:", mt5.last_error())
        mt5.shutdown()
        return

    # Build map: position_id → list of deals (to infer open/close)
    rows = []
    for d in deals:
        # Filter by symbol if requested
        if SYMBOL_FILTER and getattr(d, "symbol", "") != SYMBOL_FILTER:
            continue
        # Only include Buy/Sell deals
        if d.type not in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL):
            continue
        rows.append(d)

    # Sort by position id and time
    rows.sort(key=lambda x: (getattr(x, "position_id", 0), x.time))

    # Group by position_id to match open/close
    positions = {}
    for d in rows:
        pid = getattr(d, "position_id", 0)
        positions.setdefault(pid, []).append(d)

    # Build HTML rows
    html_rows = []
    for pid, deals_list in positions.items():
        # Find first buy/sell as open, last as close
        open_deal = deals_list[0]
        close_deal = deals_list[-1]
        symbol = getattr(open_deal, "symbol", "")
        lots = getattr(open_deal, "volume", 0.0)
        type_str = TYPE_MAP.get(open_deal.type, str(open_deal.type))
        open_time = format_dt(open_deal.time)
        open_price = getattr(open_deal, "price", 0.0)
        close_time = format_dt(close_deal.time)
        close_price = getattr(close_deal, "price", 0.0)
        commission = sum(getattr(x, "commission", 0.0) for x in deals_list)
        swap = sum(getattr(x, "swap", 0.0) for x in deals_list)
        profit = sum(getattr(x, "profit", 0.0) for x in deals_list)
        ticket = getattr(close_deal, "ticket", getattr(open_deal, "ticket", pid))
        html_rows.append(
            f"<tr>"
            f"<td>{ticket}</td>"
            f"<td>{open_time}</td>"
            f"<td>{type_str}</td>"
            f"<td class='right'>{lots:.2f}</td>"
            f"<td>{symbol}</td>"
            f"<td class='right'>{open_price:.2f}</td>"
            f"<td class='right'>{0.00:.2f}</td>"  # S/L not available
            f"<td class='right'>{0.00:.2f}</td>"  # T/P not available
            f"<td>{close_time}</td>"
            f"<td class='right'>{close_price:.2f}</td>"
            f"<td class='right'>{commission:.2f}</td>"
            f"<td class='right'>{0.00:.2f}</td>"  # Taxes not available
            f"<td class='right'>{swap:.2f}</td>"
            f"<td class='right'>{profit:.2f}</td>"
            f"</tr>"
        )

    # Write HTML
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(
            HTML_HEADER.format(
                start=start.strftime("%Y.%m.%d %H:%M"),
                end=end.strftime("%Y.%m.%d %H:%M"),
                symbol=(SYMBOL_FILTER or "ALL"),
            )
        )
        for row in html_rows:
            f.write(row + "\n")
        f.write(HTML_FOOTER)

    mt5.shutdown()
    print(f"✅ Statement exportado: {OUTPUT_PATH}")
    print(f"   Operaciones incluidas: {len(html_rows)}")
    if SYMBOL_FILTER:
        print(f"   Símbolo: {SYMBOL_FILTER}")


if __name__ == "__main__":
    main()
