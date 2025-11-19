# alerts.py
import os
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def telegram_alert(message, parse_mode="Markdown"):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Credenciales de Telegram no configuradas")
        return False
    
    url = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN + "/sendMessage"
    
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


def alert_daily_summary():
    """Envía resumen diario automático al final del día"""
    try:
        from analysis.post_mortem import analyze_recent_trades
        # Import MetaTrader5 (official package name)
        import MetaTrader5 as mt5  # type: ignore
        
        # Inicializar MT5 para obtener balance
        if not mt5.initialize():  # type: ignore
            logging.error("No se pudo inicializar MT5 para resumen diario")
            return False
        
        account_info = mt5.account_info()  # type: ignore
        
        # Analizar trades del día (últimos 999 = todos del día típicamente)
        metrics = analyze_recent_trades(n=999)
        
        if not metrics or metrics.get('n_trades', 0) == 0:
            msg = """
📊 RESUMEN DIARIO

Sin trades hoy.
Balance: ${:.2f}

Fecha: {}
""".format(account_info.balance if account_info else 0, 
           datetime.utcnow().strftime('%Y-%m-%d'))
        else:
            msg = """
📊 RESUMEN DIARIO

Trades: {}
✅ Ganadores: {} ({:.1f}%)
❌ Perdedores: {}

💰 P&L: ${:.2f}
📊 Profit Factor: {:.2f}
  
📉 Max Racha Perdedora: {}

Balance: ${:.2f}

Fecha: {}
""".format(
    metrics.get('n_trades', 0),
    metrics.get('wins', 0),
    metrics.get('win_rate', 0) * 100,
    metrics.get('losses', 0),
    metrics.get('total_pnl', 0),
    metrics.get('profit_factor', 0),
    metrics.get('max_losing_streak', 0),
    account_info.balance if account_info else 0,
    datetime.utcnow().strftime('%Y-%m-%d')
)
        
        # Cerrar MT5
        mt5.shutdown()  # type: ignore
        
        return telegram_alert(msg)
        
    except Exception as e:
        logging.error(f"Error generando resumen diario: {e}")
        return False