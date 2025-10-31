import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import metatrader5 as mt5
from mt5_utils import build_and_send_order, normalize_volume
from safety import Safety

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('webhook_receiver.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)

# Global variables for MT5 connection
mt5_connected = False

def initialize_mt5():
    """Initialize MT5 connection"""
    global mt5_connected
    try:
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            return False
        
        # Try to login with credentials from .env
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        login = int(os.getenv('MT5_LOGIN', '0'))
        password = os.getenv('MT5_PASSWORD', '')
        server = os.getenv('MT5_SERVER', '')
        
        if login and password and server:
            authorized = mt5.login(login, password=password, server=server)
            if not authorized:
                logging.error("Failed to login to MT5")
                return False
        
        mt5_connected = True
        logging.info("MT5 initialized and logged in successfully")
        return True
    except Exception as e:
        logging.error(f"Error initializing MT5: {e}")
        return False

def process_trade_signal(signal_data):
    """Process a trade signal received from webhook"""
    try:
        # Extract signal data
        symbol = signal_data.get('symbol', 'XAUUSD')
        order_type = signal_data.get('order_type', '').upper()
        volume = float(signal_data.get('volume', 0.01))
        sl_points = float(signal_data.get('sl_points', 50))
        tp_points = float(signal_data.get('tp_points', 100))
        magic = int(signal_data.get('magic', 234000))
        
        # Validate signal
        if order_type not in ['BUY', 'SELL']:
            logging.error(f"Invalid order type: {order_type}")
            return False
            
        if volume <= 0:
            logging.error(f"Invalid volume: {volume}")
            return False
            
        # Initialize MT5 if not already connected
        if not mt5_connected:
            if not initialize_mt5():
                logging.error("Failed to initialize MT5 for trade execution")
                return False
        
        # Select symbol
        if not mt5.symbol_select(symbol, True):
            logging.error(f"Failed to select symbol {symbol}")
            return False
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return False
            
        price = tick.ask if order_type == 'BUY' else tick.bid
        point = mt5.symbol_info(symbol).point
        
        # Calculate SL and TP
        if order_type == 'BUY':
            sl = price - sl_points * point
            tp = price + tp_points * point
        else:  # SELL
            sl = price + sl_points * point
            tp = price - tp_points * point
            
        # Normalize volume
        volume = normalize_volume(symbol, volume)
        
        # Execute trade
        result = build_and_send_order(
            symbol=symbol,
            side=order_type,
            volume=volume,
            sl=sl,
            tp=tp,
            magic=magic
        )
        
        if result:
            logging.info(f"Trade executed successfully: {order_type} {symbol} @ {price}")
            return True
        else:
            logging.error("Failed to execute trade")
            return False
            
    except Exception as e:
        logging.error(f"Error processing trade signal: {e}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    """Webhook endpoint to receive trading signals"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            logging.error("No data received in webhook")
            return jsonify({'error': 'No data received'}), 400
        
        logging.info(f"Webhook received: {data}")
        
        # Process the trade signal
        success = process_trade_signal(data)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Trade executed successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to execute trade'}), 500
            
    except Exception as e:
        logging.error(f"Error in webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'mt5_connected': mt5_connected
    })

@app.route('/', methods=['GET'])
def index():
    """Index endpoint"""
    return jsonify({
        'message': 'Webhook Receiver for Trading Signals',
        'endpoints': {
            'webhook': '/webhook (POST)',
            'health': '/health (GET)'
        }
    })

if __name__ == '__main__':
    # Initialize MT5 on startup
    initialize_mt5()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)