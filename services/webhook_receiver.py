import logging
from datetime import datetime
from flask import Flask, request, jsonify
import hmac
import hashlib
import os

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore
from brokers.mt5_utils import build_and_send_order, normalize_volume, MT5Gateway
from services.security_manager import (
    SecureCredentialManager,
    InputValidator,
    RateLimiter,
    constant_time_compare,
    sanitize_error_message,
    ip_whitelist,
)

# Import config manager
from config.config_manager import config_manager

# Import consolidated MT5 functions
from brokers.mt5_core import initialize_mt5

# Import ATR calculation function
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator as MarketDataService,
)

# Initialize market data service for ATR calculation
market_data_service = MarketDataService()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler("webhook_receiver.log"), logging.StreamHandler()],
)


class WebhookHandler:
    """Handles webhook trade signal processing with security and validation.
    Follows Single Responsibility Principle for webhook-specific logic.
    """

    def __init__(self, mt5_gateway=None):
        """Initialize with dependency injection for testability"""
        self.mt5_gateway = mt5_gateway or MT5Gateway()
        self.credential_manager = SecureCredentialManager()
        self.rate_limiter = RateLimiter(max_requests=10, time_window=60)
        self.secret_key = self.credential_manager.get_credential("WEBHOOK_SECRET_KEY")
        self.mt5_connected = False

        # Load config defaults
        self.default_lots = config_manager.get("LOTS")
        self.default_sl_points = config_manager.get("STOP_LOSS_POINTS")
        self.default_tp_points = config_manager.get("TAKE_PROFIT_POINTS")
        self.default_magic = config_manager.get("MAGIC_NUMBER")
        self.allowed_ips = os.getenv("WEBHOOK_ALLOWED_IPS", "127.0.0.1,::1").split(",")

    def verify_signature(self, signature, body):
        """Verify HMAC signature with constant-time comparison"""
        if not signature:
            return False, "Missing signature"

        if not self.secret_key:
            return False, "Server not configured for webhook authentication"

        if len(self.secret_key) < 32:
            return False, "Server not configured securely"

        expected_signature = hmac.new(
            self.secret_key.encode(), body, hashlib.sha256
        ).hexdigest()

        if not constant_time_compare(signature, expected_signature):
            return False, "Invalid signature"

        return True, None

    def process_trade_signal(self, signal_data):
        """Process a trade signal received from webhook"""
        try:
            # Sanitize input data
            signal_data = InputValidator.sanitize_input(signal_data)

            # Extract and validate signal data
            symbol = signal_data.get("symbol", "XAUUSD")
            order_type = signal_data.get("order_type", "").upper()
            volume = float(signal_data.get("volume", 0.01))
            sl_points = float(signal_data.get("sl_points", 0))
            tp_points = float(signal_data.get("tp_points", 0))
            magic = int(signal_data.get("magic", 234000))

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
            if not self.mt5_connected:
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

            price = tick.ask if order_type == "BUY" else tick.bid

            # Validate price
            if not InputValidator.validate_price(price):
                logging.error(f"Invalid price: {price}")
                return False

            symbol_info = mt5.symbol_info(symbol)  # type: ignore
            point = symbol_info.point if symbol_info else 0.01

            # Calculate SL and TP
            if sl_points == 0 or tp_points == 0:
                # Use ATR-based calculation
                atr = market_data_service.calculate_atr(symbol) if symbol_info else 5.0
                sl_multiplier = 3.0
                tp_multiplier = 6.0

                if sl_points == 0:
                    sl_distance = sl_multiplier * atr
                else:
                    sl_distance = sl_points * point

                if tp_points == 0:
                    tp_distance = tp_multiplier * atr
                else:
                    tp_distance = tp_points * point

                if order_type == "BUY":
                    sl = price - sl_distance
                    tp = price + tp_distance
                else:  # SELL
                    sl = price + sl_distance
                    tp = price - tp_distance
            else:
                # Use fixed points
                if order_type == "BUY":
                    sl = price - sl_points * point
                    tp = price + tp_points * point
                else:  # SELL
                    sl = price + sl_points * point
                    tp = price - tp_points * point

            # Validate calculated prices
            if not InputValidator.validate_price(
                sl
            ) or not InputValidator.validate_price(tp):
                logging.error(f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}")
                return False

            # Normalize volume
            volume = normalize_volume(symbol, volume)

            # Execute trade
            result = build_and_send_order(
                symbol=symbol, side=order_type, volume=volume, sl=sl, tp=tp, magic=magic
            )

            if result:
                logging.info(
                    f"Trade executed successfully: {order_type} {symbol} @ {price}"
                )
                return True
            else:
                logging.error("Failed to execute trade")
                return False

        except Exception as e:
            logging.error(
                f"Error processing trade signal: {sanitize_error_message(str(e))}"
            )
            return False


app = Flask(__name__)

# Initialize webhook handler
webhook_handler = WebhookHandler()

# Webhook IP whitelist for decorator
WEBHOOK_ALLOWED_IPS = webhook_handler.allowed_ips


@app.route("/webhook", methods=["POST"])
@ip_whitelist(WEBHOOK_ALLOWED_IPS)
def webhook():
    """Webhook endpoint with HMAC authentication, rate limiting, and IP whitelisting"""
    try:
        # Apply rate limiting
        if not webhook_handler.rate_limiter.is_allowed():
            retry_after = webhook_handler.rate_limiter.get_retry_after()
            logging.warning("Rate limit exceeded from %s", request.remote_addr)
            return jsonify(
                {"error": "Rate limit exceeded", "retry_after": retry_after}
            ), 429

        # Verify HMAC signature
        signature = request.headers.get("X-Webhook-Signature")
        body = request.get_data()
        is_valid, error_msg = webhook_handler.verify_signature(signature, body)

        if not is_valid:
            logging.warning(
                f"Signature verification failed from {request.remote_addr}: {error_msg}"
            )
            return jsonify(
                {"error": error_msg}
            ), 401 if error_msg != "Server not configured securely" else 500

        # Get JSON data from request
        data = request.get_json()

        if not data:
            logging.error("No data received in webhook")
            return jsonify({"error": "No data received"}), 400

        logging.info(
            f"Authenticated webhook received: {data.get('symbol', 'N/A')} {data.get('order_type', 'N/A')}"
        )

        # Process the trade signal
        success = webhook_handler.process_trade_signal(data)

        if success:
            return jsonify(
                {"status": "success", "message": "Trade executed successfully"}
            )
        else:
            return jsonify(
                {"status": "error", "message": "Failed to execute trade"}
            ), 500

    except Exception as e:
        logging.error(f"Error in webhook: {sanitize_error_message(str(e))}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "mt5_connected": webhook_handler.mt5_connected,
        }
    )


@app.route("/", methods=["GET"])
def index():
    """Index endpoint"""
    return jsonify(
        {
            "message": "Webhook Receiver for Trading Signals",
            "endpoints": {"webhook": "/webhook (POST)", "health": "/health (GET)"},
        }
    )


if __name__ == "__main__":
    # Initialize MT5 on startup
    initialize_mt5()

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=False)
