"""
Estrategia Donchian Channel - Versión Refactorizada Modular

Esta es la clase principal que coordina todos los componentes especializados
siguiendo los principios SOLID y responsabilidad única.

Componentes organizados en:
- calculators/: Indicadores técnicos y cálculos de mercado
- validators/: Validación de riesgo y condiciones de mercado
- managers/: Gestión de posiciones y ejecución de trades

Autor: Edgar Roboto
Fecha: 2026-01-20
"""

import logging
import os
import time

import MetaTrader5 as mt5

from brokers.mt5_utils import MT5Gateway
from config.config_manager import config_manager
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from core.donchian_components.managers.position_managers import (
    PositionManager,
    TradeTracker,
)
from core.donchian_components.validators.risk_market_validators import (
    MarketValidator,
    RiskValidator,
)
from core.quant.quantitative_integration import QuantitativeIntegration
from utils.decorators import handle_exception


class DonchianStrategy:
    """
    Main strategy class following SOLID principles.
    This class orchestrates the strategy execution by delegating to specialized services.
    """

    def __init__(self) -> None:
        # Initialize core components with type hints
        self.mt5_gateway: MT5Gateway = MT5Gateway()
        self.market_data: TechnicalIndicatorsCalculator = TechnicalIndicatorsCalculator()
        self.risk_validator: RiskValidator = RiskValidator(self.market_data)
        self.market_validator: MarketValidator = MarketValidator(self.mt5_gateway, self.market_data)
        self.position_manager: PositionManager = PositionManager(self.market_data, self.risk_validator)
        self.trade_tracker: TradeTracker = TradeTracker()
        self.quant_integration: QuantitativeIntegration = QuantitativeIntegration()

        # Load configuration directly in __init__
        self.symbol: str = config_manager.get("SYMBOL", "XAUUSD")
        self.timeframe: str = config_manager.get("TIMEFRAME", "H1")
        self.period: int = config_manager.get("PERIOD", 50)
        self.lookback: int = config_manager.get("LOOKBACK", 10)

        # Get risk percent from set file manager first, fallback to config_manager
        try:
            from config.set_file_manager import get_set_manager

            cfg = get_set_manager()
            # Load default configuration if no env var is set
            set_file = os.getenv("ROBOQUANT_SET_FILE", "default.json")
            cfg.load_set_file(set_file)
            self.risk_percent: float = cfg.get("risk_management.risk_per_trade_pct", 2.0)
        except Exception as e:
            logging.warning(f"Failed to load risk percent from set file, using config_manager: {e}")
            self.risk_percent = config_manager.get("RISK_PERCENT", 2.0)

        self.use_risk_management: bool = config_manager.get("USE_RISK_MANAGEMENT", True)
        self.max_spread_points: int = config_manager.get("MAX_SPREAD_POINTS", 20)
        self.trading_hour_start: int = config_manager.get("TRADING_HOUR_START", 0)
        self.trading_hour_end: int = config_manager.get("TRADING_HOUR_END", 23)
        self.magic_number: int = config_manager.get("MAGIC_NUMBER", 123456)

        # Global variables for quantitative integration (reset on initialization)
        global QUANT_OPTIMAL_LOTS, CURRENT_ENTRY_SCORE, TRADE_ENTRY_SCORES
        QUANT_OPTIMAL_LOTS = None
        CURRENT_ENTRY_SCORE = None
        TRADE_ENTRY_SCORES = {}

        logging.info("Donchian Strategy initialized with modular architecture")

    def run_strategy(self, symbol: str = "XAUUSD") -> None:
        """Main strategy function - coordinates all components"""
        logging.info(f"🚀 Running modular strategy for symbol: {symbol}")

        # Log current market conditions
        self._log_market_conditions(symbol)

        # Phase 1: Validate market conditions
        is_valid: bool
        reason: str
        is_valid, reason = self.position_manager.validate_market_conditions(symbol)
        if not is_valid:
            logging.info(f"Market validation failed: {reason}")
            return

        # Phase 2: Apply quantitative filter
        if not self._apply_quant_filter(symbol):
            return

        # Phase 3-4: Generate signal and calculate risk parameters (consolidated)
        signal_and_risk: tuple[str, float, float, float] | None = self._generate_signal_with_risk(symbol)
        if not signal_and_risk:
            return

        order_type: str
        entry_price: float
        sl_distance: float
        tp_price: float
        order_type, entry_price, sl_distance, tp_price = signal_and_risk

        # Phase 5: Calculate position size
        lots: float | None = self._calculate_position_size(symbol, sl_distance)
        if lots is None or lots <= 0:
            return

        # Phase 6: Execute trade
        self._execute_trade(symbol, order_type, lots, entry_price, sl_distance, tp_price)


    def _generate_signal_with_risk(self, symbol: str) -> tuple[str, float, float, float] | None:
        """Generate trading signal and calculate risk parameters in one call"""
        # Get Donchian channels
        upper_channel, lower_channel = self.market_data.get_donchian_channels(symbol, self.period)
        if upper_channel is None or lower_channel is None:
            logging.info("Failed to calculate Donchian channels")
            return None

        # Get current price for BUY (we'll check both directions)
        current_price = self.market_data.get_current_price(symbol, "BUY")
        if current_price is None:
            logging.info("Failed to get current price")
            return None

        # Generate signals
        buy_signal = current_price > upper_channel
        sell_signal = current_price < lower_channel

        if buy_signal:
            order_type = "BUY"
            entry_price = current_price
            reason = "Price above upper channel"
        elif sell_signal:
            order_type = "SELL"
            entry_price = current_price
            reason = "Price below lower channel"
        else:
            logging.info("No breakout signal")
            return None

        logging.info(f"Signal generated: {order_type} - {reason}")

        # Calculate risk parameters
        atr = self.market_data.calculate_atr(symbol, 14)
        if atr is None:
            logging.error("Failed to calculate ATR")
            return None

        sl_price, tp_price = self.risk_validator.calculate_dynamic_stops(
            symbol, entry_price, order_type, atr
        )
        sl_distance = abs(entry_price - sl_price)

        return order_type, entry_price, sl_distance, tp_price


    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection"""
        if not self.mt5_gateway.initialize():
            logging.error("Failed to initialize MT5 gateway")
            return False
        logging.info("MT5 gateway initialized successfully")
        return True

    def main(self) -> None:
        """Main execution loop."""
        logging.info("Starting Donchian Strategy (Modular Version)")

        if not self.initialize_mt5():
            return

        try:
            while True:
                try:
                    self.run_strategy(self.symbol)
                    # Add delay to prevent excessive execution
                    time.sleep(180)  # Wait 3 minutes between iterations
                except KeyboardInterrupt:
                    logging.info("Strategy stopped by user")
                    break
                except Exception as e:
                    logging.exception(f"Strategy iteration error: {e}")
                    # Add delay even on error to prevent spamming
                    time.sleep(180)

        finally:
            self.mt5_gateway.shutdown()

    @handle_exception
    def _log_market_conditions(self, symbol: str) -> None:
        """Log current market conditions."""
        try:
            adx_data = self.market_data.calculate_adx(symbol, 14)  # type: ignore
            if adx_data:
                logging.info(
                    "📊 Market Conditions - ADX: %.2f, DI+: %.2f, DI-: %.2f",
                    adx_data["adx"],
                    adx_data["di_plus"],
                    adx_data["di_minus"],
                )
        except AttributeError:
            # Method may not exist, skip logging
            pass
        except Exception as e:
            logging.warning(f"Could not get market conditions: {e}")

    def _apply_quant_filter(self, symbol: str) -> bool:
        """Apply quantitative analysis filter"""
        quant_result = self.quant_integration.apply_quantitative_analysis(symbol)
        if not quant_result["should_trade"]:
            logging.info(f"Quantitative analysis rejected trade: {quant_result['reason']}")
            return False

        entry_score = quant_result["entry_score"]
        global CURRENT_ENTRY_SCORE
        CURRENT_ENTRY_SCORE = entry_score
        return True

    def _calculate_position_size(self, symbol: str, sl_distance: float) -> float | None:
        """Calculate position size based on risk management"""
        account_info = mt5.account_info()  # type: ignore
        if account_info is None:
            logging.error("Failed to get account info")
            return None

        lots = self.risk_validator.compute_lot_size(
            account_info.balance, self.risk_percent, sl_distance, symbol
        )

        if lots <= 0:
            logging.warning("Calculated lot size is zero or negative")
            return None

        return lots

    @handle_exception
    def _execute_trade(
        self,
        symbol: str,
        order_type: str,
        lots: float,
        entry_price: float,
        sl_distance: float,
        tp_price: float,
    ) -> None:
        """Execute the trade with calculated parameters."""
        sl_points = sl_distance / mt5.symbol_info(symbol).point  # type: ignore
        tp_points = abs(entry_price - tp_price) / mt5.symbol_info(symbol).point  # type: ignore

        success = self.position_manager.execute_trade(
            symbol, order_type, lots, sl_points, tp_points
        )

        if success:
            logging.info(
                "✅ Trade executed successfully: %s %s @ %s",
                order_type,
                symbol,
                entry_price,
            )
            # Track the trade for post-mortem analysis
            # Note: Ticket association will be handled in mt5_utils monitor loop
        else:
            logging.error("❌ Trade execution failed")


# Global variables for quantitative integration
# These need to be accessible from other modules
QUANT_OPTIMAL_LOTS: float | None = None
CURRENT_ENTRY_SCORE: float | None = None
TRADE_ENTRY_SCORES: dict[int, float] = {}


if __name__ == "__main__":
    strategy = DonchianStrategy()
    strategy.main()
