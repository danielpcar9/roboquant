"""
Gestores para la estrategia Donchian Channel

Contiene todas las funciones de gestión de posiciones,
ejecución de órdenes y seguimiento de trades.

Extraído de DonchianStrategy de donchian_strategy.py
"""

import logging
from datetime import UTC, datetime

import MetaTrader5 as mt5

from brokers.mt5_core import normalize_volume
from brokers.mt5_utils import build_and_send_order, estimate_lots_by_risk
from config.config_manager import config_manager
from config.set_file_manager import get_set_manager
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from core.donchian_components.validators.risk_market_validators import RiskValidator
from core.market_regime import market_regime_detector
from core.utils.dispatch_functions import (
    calculate_stop_loss,
    calculate_take_profit,
    handle_account_validation,
    handle_trade_execution,
)
from services.news_filter import news_filter
from services.security_manager import InputValidator  # Importar InputValidator completo
from utils.decorators import handle_exception  # Importar decorador faltante

# Import required functions from MT5 utilities


# Mock classes for testing purposes
class _MockNewsFilter:
    @staticmethod
    def is_news_time():
        return False


class _MockMarketRegimeDetector:
    @staticmethod
    def detect_regime(symbol, adx_period=14, adx_threshold=20):
        return "TRENDING", 25.0, 1.0




class PositionManager:
    """Gestor especializado en ejecución y gestión de posiciones"""

    def __init__(
        self,
        market_data_service: TechnicalIndicatorsCalculator,
        risk_validator: RiskValidator,
    ):
        self.market_data = market_data_service
        self.risk_validator = risk_validator
        self.config = self._load_config()

    def _load_config(self):
        """Load strategy configuration"""
        return {
            "trading_hour_start": config_manager.get("TRADING_HOUR_START", 0),
            "trading_hour_end": config_manager.get("TRADING_HOUR_END", 23),
            "use_risk_management": config_manager.get("USE_RISK_MANAGEMENT", True),
            "risk_percent": config_manager.get("RISK_PERCENT", 1.0),
            "max_spread_points": config_manager.get("MAX_SPREAD_POINTS", 20),
            "magic_number": config_manager.get("MAGIC_NUMBER", 123456),
        }

    def validate_trading_hours(self) -> bool:
        """Check if current time is within trading hours (GMT)"""
        # Obtener hora UTC correctamente
        current_hour_utc = datetime.now(UTC).hour
        current_hour_local = datetime.now().hour

        trading_start = self.config["trading_hour_start"]
        trading_end = self.config["trading_hour_end"]
        in_hours = trading_start <= current_hour_utc <= trading_end

        logging.debug(
            f"México: {current_hour_local}:00 | UTC: {current_hour_utc}:00 | Trading: {trading_start}-{trading_end} UTC | Active: {in_hours}",
        )

        return in_hours

    def _validate_trade_inputs(self, symbol: str, order_type: str, lots: float, sl_points: float, tp_points: float) -> tuple[bool, str]:
        """Validate trade inputs"""
        # Validate inputs
        if not InputValidator.validate_symbol(symbol):
            return False, f"Invalid symbol: {symbol}"

        if not InputValidator.validate_order_type(order_type):
            return False, f"Invalid order type: {order_type}"

        if not InputValidator.validate_volume(lots):
            return False, f"Invalid volume: {lots}"

        if sl_points <= 0 or tp_points <= 0:
            return False, f"Invalid SL/TP points: SL={sl_points}, TP={tp_points}"

        return True, ""

    def _get_and_validate_price_info(self, symbol: str, order_type: str):
        """Get and validate price and symbol information"""
        price = self.market_data.get_current_price(symbol, order_type)
        if price is None:
            return None, "Failed to get current price"

        # Validate price
        if not InputValidator.validate_price(price):
            return None, f"Invalid price: {price}"

        # Get symbol info for point value
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return None, f"Failed to get symbol info for {symbol}"

        point = symbol_info.point
        logging.debug(f"Symbol point value: {point}")

        return (price, point), ""

    def _calculate_and_validate_sl_tp(self, order_type: str, price: float, sl_points: float, tp_points: float, point: float):
        """Calculate and validate SL/TP values"""
        # Calculate SL/TP using dispatcher functions
        try:
            sl = calculate_stop_loss(order_type, price, sl_points, point)
            tp = calculate_take_profit(order_type, price, tp_points, point)
        except ValueError as e:
            return None, f"Invalid order type for SL/TP calculation: {e}"

        # Validate calculated prices
        if not InputValidator.validate_price(sl) or not InputValidator.validate_price(tp):
            return None, f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}"

        return (sl, tp), ""

    def _apply_risk_management(self, symbol: str, price: float, sl: float) -> float:
        """Apply risk management and return adjusted lots"""
        if not self.config["use_risk_management"]:
            return self.config["initial_lots"]

        account_info = mt5.account_info()
        is_valid, message = handle_account_validation(account_info)
        if not is_valid:
            logging.error(message)
            return self.config["initial_lots"]

        # Apply adaptive risk scaling based on current drawdown
        try:
            from risk.ftmo_manager import ftmo_manager

            risk_scale = ftmo_manager.get_risk_scale_factor()
            scaled_risk = self.config["risk_percent"] * risk_scale
            if risk_scale < 1.0:
                logging.info(
                    f"Risk scaled down: {self.config['risk_percent']}% → {scaled_risk:.2f}% (factor: {risk_scale:.2f})",
                )
        except Exception as e:
            logging.warning(
                f"Failed to get risk scale factor, using full risk: {e}",
            )
            scaled_risk = self.config["risk_percent"]

        calculated_lots = estimate_lots_by_risk(
            symbol=symbol,
            entry_price=price,
            stop_price=sl,
            risk_pct=scaled_risk,
            mt5_module=mt5,
        )
        logging.info(
            f"Risk: {scaled_risk:.2f}% = ${account_info.balance * scaled_risk / 100:.2f}, Lots: {calculated_lots}",
        )

        return calculated_lots

    def _execute_order(self, symbol: str, order_type: str, lots: float, sl: float, tp: float):
        """Execute the actual order"""
        # Normalize volume to ensure it meets broker requirements
        original_lots = lots
        lots = normalize_volume(symbol, lots)
        if lots != original_lots:
            logging.info(f"Volume normalized from {original_lots} to {lots}")

        logging.info(
            f"Calling build_and_send_order with parameters: symbol={symbol}, side={order_type}, volume={lots}, sl={sl}, tp={tp}",
        )
        result = build_and_send_order(
            symbol=symbol,
            side=order_type,
            volume=lots,
            sl=sl,
            tp=tp,
            magic=self.config["magic_number"],
        )

        success, message = handle_trade_execution(result)
        if success:
            logging.info(
                f"{order_type} executed: Price={self.market_data.get_current_price(symbol, order_type):.5f} SL={sl:.5f} TP={tp:.5f}",
            )
            logging.info(f"Order result: {result}")
            return True
        logging.error(message)
        return False

    @handle_exception
    def execute_trade(
        self,
        symbol: str,
        order_type: str,
        lots: float,
        sl_points: float,
        tp_points: float,
    ) -> bool:
        """Execute a trade with given parameters"""

        logging.info(f"Attempting to execute {order_type} trade for {symbol}")

        # Validate inputs
        is_valid, error_msg = self._validate_trade_inputs(symbol, order_type, lots, sl_points, tp_points)
        if not is_valid:
            logging.error(error_msg)
            return False

        # Get and validate price info
        price_info, error_msg = self._get_and_validate_price_info(symbol, order_type)
        if price_info is None:
            logging.error(error_msg)
            return False

        price, point = price_info

        # Calculate and validate SL/TP
        sl_tp_info, error_msg = self._calculate_and_validate_sl_tp(order_type, price, sl_points, tp_points, point)
        if sl_tp_info is None:
            logging.error(error_msg)
            return False

        sl, tp = sl_tp_info

        # Apply risk management
        adjusted_lots = self._apply_risk_management(symbol, price, sl)

        # Validate final volume
        if not InputValidator.validate_volume(adjusted_lots):
            logging.error(f"Invalid final volume: {adjusted_lots}")
            return False

        logging.info(
            f"Trade parameters - Price: {price}, SL: {sl}, TP: {tp}, Volume: {adjusted_lots}",
        )

        try:
            return self._execute_order(symbol, order_type, adjusted_lots, sl, tp)
        except Exception as e:
            logging.error(f"Error executing trade: {e!s}", exc_info=True)
            return False

    @handle_exception
    def validate_market_conditions(self, symbol: str) -> tuple[bool, str]:
        """Validate general market conditions before trading"""
        # Check if we're in trading hours
        if not self.validate_trading_hours():
            return False, "Outside trading hours"

        # Check for news events that might affect trading
        if news_filter.is_news_time():
            return False, "News event detected, skipping trade execution"

        # Check spread first
        spread = self.market_data.get_spread(symbol)
        if spread is None:
            return False, "Failed to get current spread"

        if spread > self.config["max_spread_points"]:
            return (
                False,
                f"Spread too high: {spread:.2f} points > {self.config['max_spread_points']} points",
            )

        # CHECK MARKET REGIME (ADX FILTER)
        # Get ADX filter settings from configuration
        try:
            cfg = get_set_manager()
            require_adx = cfg.get("strategy.require_adx_confirmation", False)
            adx_threshold = cfg.get("strategy.adx_threshold", 20)
            adx_period = cfg.get("strategy.adx_period", 14)
        except Exception:
            require_adx = False
            adx_threshold = 20
            adx_period = 14

        # Apply ADX filter if enabled
        if require_adx:
            regime, adx_value, slope_value = market_regime_detector.detect_regime(
                symbol, adx_period=adx_period, adx_threshold=adx_threshold,
            )

            if regime == "RANGING":
                return (
                    False,
                    f"Market is RANGING (ADX: {adx_value:.2f}), skipping trade",
                )
            if regime == "UNKNOWN":
                return False, "Unable to determine market regime"
            logging.info(
                f"Market is TRENDING (ADX: {adx_value:.2f} > {adx_threshold}), proceeding with strategy",
            )

        return True, "OK"


class TradeTracker:
    """Seguimiento y monitoreo de trades activos"""

    def __init__(self):
        self.active_trades = {}
        self.trade_history = []

    @handle_exception
    def track_new_trade(
        self,
        ticket: int,
        symbol: str,
        order_type: str,
        entry_price: float,
        sl: float,
        tp: float,
    ):
        """Registrar nuevo trade"""
        self.active_trades[ticket] = {
            "symbol": symbol,
            "type": order_type,
            "entry_price": entry_price,
            "sl": sl,
            "tp": tp,
            "timestamp": datetime.now(),
        }
        logging.info(
            f"Tracking new trade: Ticket {ticket} for {symbol} at {entry_price}",
        )

    @handle_exception
    def remove_closed_trade(self, ticket: int):
        """Remover trade cerrado"""
        if ticket in self.active_trades:
            trade_info = self.active_trades.pop(ticket)
            self.trade_history.append(trade_info)
            logging.info(f"Removed closed trade: Ticket {ticket}")

    def get_active_trades_count(self, symbol: str | None = None) -> int:
        """Obtener conteo de trades activos"""
        if symbol:
            return len(
                [t for t in self.active_trades.values() if t["symbol"] == symbol],
            )
        return len(self.active_trades)
