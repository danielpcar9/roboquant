# alerts.py
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def telegram_alert(message, parse_mode="Markdown"):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Credenciales de Telegram no configuradas")
        return False
    
    url = "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage"
    
    try:
        response = requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": parse_mode
        }, timeout=10)
        
        if response.status_code == 200:
            logging.info("Alerta enviada a Telegram")
            return True
        else:
            logging.error("Error API Telegram: %d %s", response.status_code, response.text)
            return False
            
    except Exception as e:
        logging.error("Error enviando alerta a Telegram: %s", e)
        return False


def alert_trade_opened(ticket, symbol, side, volume, entry, sl, tp):
    emoji = "BUY" if side == "BUY" else "SELL"
    msg = """
TRADE OPENED

Ticket: {}
Symbol: {}
Side: {}
Volume: {}
Entry: {:.5f}
SL: {:.5f}
TP: {:.5f}

Time: {}
""".format(ticket, symbol, emoji, volume, entry, sl, tp, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
    return telegram_alert(msg)


def alert_trade_closed(ticket, symbol, pnl, reason):
    emoji = "WIN" if pnl > 0 else "LOSS"
    msg = """
TRADE CLOSED

Ticket: {}
Symbol: {}
PnL: ${:.2f}
Result: {}
Reason: {}

Time: {}
""".format(ticket, symbol, pnl, emoji, reason, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
    return telegram_alert(msg)


def alert_safety_violation(reason):
    msg = """
SAFETY CHECK FAILED

Reason: {}

Trading halted until issue is resolved.

Time: {}
""".format(reason, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
    return telegram_alert(msg)


def alert_kill_switch_activated(reason="manual"):
    msg = """
KILL SWITCH ACTIVATED

Reason: {}

All trading stopped immediately.
Remove config/kill_switch.flag to resume.

Time: {}
""".format(reason, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
    return telegram_alert(msg)