import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
import hmac
import hashlib
import os
# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore
from mt5_utils import build_and_send_order, normalize_volume
from safety import Safety
from security_manager import SecureCredentialManager, InputValidator, RateLimiter, constant_time_compare, sanitize_error_message, ip_whitelist
# Import config manager
from config_manager import config_manager

# Import consolidated MT5 functions
from mt5_core import initialize_mt5

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

# Security components
credential_manager = SecureCredentialManager()
rate_limiter = RateLimiter(max_requests=10, time_window=60)  # 10 requests per minute

# Get webhook secret key from secure credential manager
SECRET_KEY = credential_manager.get_credential('WEBHOOK_SECRET_KEY')

# Configuration parameters
DEFAULT_LOTS = config_manager.get('LOTS')
DEFAULT_SL_POINTS = config_manager.get('STOP_LOSS_POINTS')
DEFAULT_TP_POINTS = config_manager.get('TAKE_PROFIT_POINTS')
DEFAULT_MAGIC = config_manager.get('MAGIC_NUMBER')

# Webhook IP whitelist (configured via environment variable)
WEBHOOK_ALLOWED_IPS = os.getenv('WEBHOOK_ALLOWED_IPS', '127.0.0.1,::1').split(',')


# initialize_mt5 function removed - using consolidated version from mt5_core.py

def process_trade_signal(signal_data):
    """Process a trade signal received from webhook"""
    try:
        # Sanitize input data
        signal_data = InputValidator.sanitize_input(signal_data)
        
        # Extract and validate signal data
        symbol = signal_data.get('symbol', 'XAUUSD')
        order_type = signal_data.get('order_type', '').upper()
        volume = float(signal_data.get('volume', 0.01))
        sl_points = float(signal_data.get('sl_points', 150))  # Updated default
        tp_points = float(signal_data.get('tp_points', 300))  # Updated default
        magic = int(signal_data.get('magic', 234000))
        
        # Validate inputs
        if not InputValidator.validate_symbol(symbol):
            logging.error(f"Invalid symbol: {symbol}")
            return False
            
        if not InputValidator.validate_order_type(order_type):
            logging.error(f"Invalid order type: {order_type}")
            return False
            
        if not InputValidator.validate_volume(volume):
            logging.error(f"Invalid volume: {volume}")
            return False
            
        # Initialize MT5 if not already connected
        if not mt5_connected:
            if not initialize_mt5():
                logging.error("Failed to initialize MT5 for trade execution")
                return False
        
        # Select symbol
        if not mt5.symbol_select(symbol, True):  # type: ignore
            logging.error(f"Failed to select symbol {symbol}")
            return False
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return False
            
        price = tick.ask if order_type == 'BUY' else tick.bid
        
        # Validate price
        if not InputValidator.validate_price(price):
            logging.error(f"Invalid price: {price}")
            return False
            
        point = mt5.symbol_info(symbol).point  # type: ignore
        
        # Calculate SL and TP
        if order_type == 'BUY':
            sl = price - sl_points * point
            tp = price + tp_points * point
        else:  # SELL
            sl = price + sl_points * point
            tp = price - tp_points * point
            
        # Validate calculated prices
        if not InputValidator.validate_price(sl) or not InputValidator.validate_price(tp):
            logging.error(f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}")
            return False
            
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
        logging.error(f"Error processing trade signal: {sanitize_error_message(str(e))}")
        return False

@app.route('/webhook', methods=['POST'])
@ip_whitelist(WEBHOOK_ALLOWED_IPS)  # Apply IP whitelist decorator
def webhook():
    """Webhook endpoint with HMAC authentication, rate limiting, and IP whitelisting"""
    try:
        # Apply rate limiting
        if not rate_limiter.is_allowed():
            retry_after = rate_limiter.get_retry_after()
            logging.warning("Rate limit exceeded from %s", request.remote_addr)
            return jsonify({'error': 'Rate limit exceeded', 'retry_after': retry_after}), 429
        
        # Verify HMAC signature using constant-time comparison
        signature = request.headers.get('X-Webhook-Signature')
        if not signature:
            logging.warning("Webhook without signature from %s", request.remote_addr)
            return jsonify({'error': 'Missing signature'}), 401
        
        # Check if SECRET_KEY is configured and valid
        if not SECRET_KEY:
            logging.error("WEBHOOK_SECRET_KEY not configured in environment")
            return jsonify({'error': 'Server not configured for webhook authentication'}), 500
            
        # Validate secret key length for security
        if len(SECRET_KEY) < 32:
            logging.error("WEBHOOK_SECRET_KEY must be at least 32 characters for security")
            return jsonify({'error': 'Server not configured securely'}), 500
        
        # Calculate expected signature
        body = request.get_data()
        expected_signature = hmac.new(
            SECRET_KEY.encode() if SECRET_KEY else b'',
            body,
            hashlib.sha256
        ).hexdigest()
        
        # Secure comparison against timing attacks
        if not constant_time_compare(signature, expected_signature):
            logging.warning("Invalid signature from %s", request.remote_addr)
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            logging.error("No data received in webhook")
            return jsonify({'error': 'No data received'}), 400
        
        logging.info(f"Authenticated webhook received: {data.get('symbol', 'N/A')} {data.get('order_type', 'N/A')}")
        
        # Process the trade signal
        success = process_trade_signal(data)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Trade executed successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to execute trade'}), 500
            
    except Exception as e:
        logging.error(f"Error in webhook: {sanitize_error_message(str(e))}")
        return jsonify({'error': 'Internal server error'}), 500

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