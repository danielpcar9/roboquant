import hashlib
import hmac
import logging
import os
from datetime import UTC, datetime

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5, MT5_AVAILABLE
from flask import Flask, jsonify, request

# Import consolidated MT5 functions
from brokers.mt5_core import initialize_mt5, normalize_volume
from brokers.mt5_utils import MT5Gateway, build_and_send_order

# Import config manager
from config.config_manager import config_manager

# Import ATR calculation function
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator as MarketDataService,
)
from services.security_manager import (
    InputValidator,
    RateLimiter,
    SecureCredentialManager,
    constant_time_compare,
    ip_whitelist,
    sanitize_error_message,
)

# Initialize market data service for ATR calculation
market_data_service = MarketDataService()

# Default ATR-based SL/TP multipliers
DEFAULT_SL_ATR_MULTIPLIER = 3.0
DEFAULT_TP_ATR_MULTIPLIER = 6.0

# Set up module-level logger; configuration of handlers/formatters
# should be done by the hosting application or in a __main__ entrypoint.
logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles webhook trade signal processing with security and validation.

    Follows the Single Responsibility Principle for webhook-specific logic.
    """

    def __init__(self, mt5_gateway: MT5Gateway | None = None) -> None:
        """Initialize webhook handler.

        Args:
            mt5_gateway: Optional gateway instance for MetaTrader5 integration.
                         If not provided, a default ``MT5Gateway`` is created.
        """
        self.mt5_gateway: MT5Gateway = mt5_gateway or MT5Gateway()
        self.credential_manager = SecureCredentialManager()
        self.rate_limiter = RateLimiter(max_requests=10, time_window=60)
        self.secret_key = self.credential_manager.get_credential("WEBHOOK_SECRET_KEY")
        self.mt5_connected = False  # Will be updated when MT5 is initialized

        # Load config defaults
        self.default_lots = config_manager.get("LOTS")
        self.default_sl_points = config_manager.get("STOP_LOSS_POINTS")
        self.default_tp_points = config_manager.get("TAKE_PROFIT_POINTS")
        self.default_magic = config_manager.get("MAGIC_NUMBER")
        self.allowed_ips = os.getenv("WEBHOOK_ALLOWED_IPS", "127.0.0.1,::1").split(",")

    def verify_signature(
        self,
        signature: str | None,
        body: bytes,
    ) -> tuple[bool, str | None]:
        """Verify HMAC signature with constant-time comparison.

        Args:
            signature: Signature value from the ``X-Webhook-Signature`` header.
            body: Raw request body used to recompute the HMAC.

        Returns:
            A tuple ``(is_valid, error_message)``. If ``is_valid`` is ``True``,
            ``error_message`` will be ``None``.
        """
        if not signature:
            return False, "Missing signature"

        if not self.secret_key:
            return False, "Server not configured for webhook authentication"

        if len(self.secret_key) < 32:
            return False, "Server not configured securely"

        expected_signature = hmac.new(
            self.secret_key.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not constant_time_compare(signature, expected_signature):
            return False, "Invalid signature"

        return True, None

    def _extract_and_validate_signal_data(
        self,
        signal_data: dict,
    ) -> dict | None:
        """Extract and validate signal data from input.

        Args:
            signal_data: Raw signal payload from the webhook request.

        Returns:
            A dictionary with normalized and validated parameters, or ``None``
            if validation fails.
        """
        # Sanitize input data
        signal_data = InputValidator.sanitize_input(signal_data)

        # Extract signal data with defaults
        symbol = signal_data.get("symbol", "XAUUSD")
        order_type = signal_data.get("order_type", "").upper()
        volume = float(signal_data.get("volume", self.default_lots))
        sl_points = float(signal_data.get("sl_points", self.default_sl_points))
        tp_points = float(signal_data.get("tp_points", self.default_tp_points))
        magic = int(signal_data.get("magic", self.default_magic))

        # Validate inputs
        if not InputValidator.validate_symbol(symbol):
            logger.error(f"Invalid symbol: {symbol}")
            return None

        if not InputValidator.validate_order_type(order_type):
            logger.error(f"Invalid order type: {order_type}")
            return None

        if not InputValidator.validate_volume(volume):
            logger.error(f"Invalid volume: {volume}")
            return None

        return {
            "symbol": symbol,
            "order_type": order_type,
            "volume": volume,
            "sl_points": sl_points,
            "tp_points": tp_points,
            "magic": magic,
        }

    def _initialize_mt5_connection(self) -> bool:
        """Initialize MT5 connection if not already connected."""
        if not self.mt5_connected:
            if not initialize_mt5():
                logger.error("Failed to initialize MT5 for trade execution")
                return False
            self.mt5_connected = True  # Update connection status
        return True

    def _get_market_data(
        self,
        symbol: str,
        order_type: str,
    ) -> dict | None:
        """Get current market data for symbol."""
        # Select symbol
        if not mt5.symbol_select(symbol, True):  # type: ignore
            logger.error(f"Failed to select symbol {symbol}")
            return None

        # Get current price
        tick = mt5.symbol_info_tick(symbol)  # type: ignore
        if tick is None:
            logger.error(f"Failed to get tick data for {symbol}")
            return None

        price = tick.ask if order_type == "BUY" else tick.bid

        # Validate price
        if not InputValidator.validate_price(price):
            logger.error(f"Invalid price: {price}")
            return None

        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)  # type: ignore
        if symbol_info is None:
            logger.error(f"Failed to get symbol info for {symbol}")
            return None

        return {
            "price": price,
            "point": symbol_info.point,
            "symbol_info": symbol_info,
        }

    def _calculate_sl_tp(
        self,
        order_type: str,
        price: float,
        point: float,
        sl_points: float,
        tp_points: float,
        symbol: str,
    ) -> tuple[float, float]:
        """Calculate stop loss and take profit levels."""
        if sl_points == 0 or tp_points == 0:
            # Use ATR-based calculation
            atr = market_data_service.calculate_atr(symbol)
            sl_multiplier = DEFAULT_SL_ATR_MULTIPLIER
            tp_multiplier = DEFAULT_TP_ATR_MULTIPLIER

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

        return sl, tp

    def process_trade_signal(self, signal_data: dict) -> bool:
        """Process a trade signal received from webhook."""
        try:
            # Extract and validate signal data
            signal_params = self._extract_and_validate_signal_data(signal_data)
            if signal_params is None:
                return False

            # Initialize MT5 connection
            if not self._initialize_mt5_connection():
                return False

            # Get market data
            market_data = self._get_market_data(
                signal_params["symbol"],
                signal_params["order_type"],
            )
            if market_data is None:
                return False

            # Calculate SL and TP
            sl, tp = self._calculate_sl_tp(
                signal_params["order_type"],
                market_data["price"],
                market_data["point"],
                signal_params["sl_points"],
                signal_params["tp_points"],
                signal_params["symbol"],
            )

            # Validate calculated prices
            if not InputValidator.validate_price(sl) or not InputValidator.validate_price(tp):
                logger.error(f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}")
                return False

            # Normalize volume
            volume = normalize_volume(signal_params["symbol"], signal_params["volume"])

            # Execute trade
            result = build_and_send_order(
                symbol=signal_params["symbol"],
                side=signal_params["order_type"],
                volume=volume,
                sl=sl,
                tp=tp,
                magic=signal_params["magic"],
            )

            if result:
                logger.info(
                    f"Trade executed successfully: {signal_params['order_type']} {signal_params['symbol']} @ {market_data['price']}",
                )
                return True
            logger.error("Failed to execute trade")
            return False

        except Exception as e:
            logger.exception(
                f"Error processing trade signal: {sanitize_error_message(str(e))}",
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
    """Webhook endpoint with HMAC authentication, rate limiting, and IP whitelisting."""
    try:
        # Apply rate limiting
        if not webhook_handler.rate_limiter.is_allowed():
            retry_after = webhook_handler.rate_limiter.get_retry_after()
            logger.warning("Rate limit exceeded from %s", request.remote_addr)
            return jsonify(
                {"error": "Rate limit exceeded", "retry_after": retry_after},
            ), 429

        # Verify HMAC signature
        signature = request.headers.get("X-Webhook-Signature")
        body = request.get_data()
        is_valid, error_msg = webhook_handler.verify_signature(signature, body)

        if not is_valid:
            logger.warning(
                f"Signature verification failed from {request.remote_addr}: {error_msg}",
            )
            status_code = 401 if error_msg != "Server not configured securely" else 500
            # Return a generic error message to avoid exposing internal security posture
            return jsonify(
                {"error": "Invalid webhook signature"},
            ), status_code

        # Get JSON data from request
        data = request.get_json()

        if data is None:
            logger.error("No valid JSON data received in webhook")
            return jsonify({"error": "No valid JSON data received"}), 400

        logger.info(
            f"Authenticated webhook received: {data.get('symbol', 'N/A')} {data.get('order_type', 'N/A')}",
        )

        # Process the trade signal
        success = webhook_handler.process_trade_signal(data)

        if success:
            return jsonify(
                {"status": "success", "message": "Trade executed successfully"},
            )
        return jsonify(
            {"status": "error", "message": "Failed to execute trade"},
        ), 500

    except Exception as e:
        logger.exception(f"Error in webhook: {sanitize_error_message(str(e))}")
        return jsonify({"error": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime.now(UTC).isoformat(),
            "mt5_connected": webhook_handler.mt5_connected,
        },
    )


@app.route("/", methods=["GET"])
def index():
    """Index endpoint."""
    return jsonify(
        {
            "message": "Webhook Receiver for Trading Signals",
            "endpoints": {
                "webhook": "/webhook (POST)",
                "health": "/health (GET)",
            },
        },
    )


if __name__ == "__main__":
    # Initialize MT5 on startup
    initialize_mt5()

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000, debug=False)
