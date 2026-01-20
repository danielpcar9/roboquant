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
from typing import Optional, Dict, Any

import MetaTrader5 as mt5

from config.config_manager import config_manager
from core.brokers.mt5_gateway import MT5Gateway
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from core.donchian_components.validators.risk_market_validators import (
    RiskValidator,
    MarketValidator,
)
from core.donchian_components.managers.position_managers import (
    PositionManager,
    TradeTracker,
)
from core.quant.quantitative_integration import QuantitativeIntegration


class StrategyConfig:
    """Configuration class following Single Responsibility Principle"""

    def __init__(self):
        self.symbol = config_manager.get("SYMBOL", "XAUUSD")
        self.timeframe = config_manager.get("TIMEFRAME", "H1")
        self.period = config_manager.get("PERIOD", 50)
        self.lookback = config_manager.get("LOOKBACK", 10)
        self.risk_percent = config_manager.get("RISK_PERCENT", 1.0)
        self.use_risk_management = config_manager.get("USE_RISK_MANAGEMENT", True)
        self.max_spread_points = config_manager.get("MAX_SPREAD_POINTS", 20)
        self.trading_hour_start = config_manager.get("TRADING_HOUR_START", 0)
        self.trading_hour_end = config_manager.get("TRADING_HOUR_END", 23)
        self.magic_number = config_manager.get("MAGIC_NUMBER", 123456)


class DonchianStrategy:
    """
    Main strategy class following SOLID principles.
    This class orchestrates the strategy execution by delegating to specialized services.
    """

    def __init__(self):
        # Initialize core components
        self.mt5_gateway = MT5Gateway()
        self.market_data = TechnicalIndicatorsCalculator()
        self.risk_validator = RiskValidator(self.market_data)
        self.market_validator = MarketValidator(self.mt5_gateway, self.market_data)
        self.position_manager = PositionManager(self.market_data, self.risk_validator)
        self.trade_tracker = TradeTracker()
        self.quant_integration = QuantitativeIntegration()

        # Load configuration
        self.config = StrategyConfig()

        # Global variables for quantitative integration
        global QUANT_OPTIMAL_LOTS, CURRENT_ENTRY_SCORE, TRADE_ENTRY_SCORES
        QUANT_OPTIMAL_LOTS = None
        CURRENT_ENTRY_SCORE = None
        TRADE_ENTRY_SCORES = {}

        logging.info("Donchian Strategy initialized with modular architecture")

    def run_strategy(self, symbol="XAUUSD"):
        """Main strategy function - coordinates all components"""
        logging.info(f"Running modular strategy for symbol: {symbol}")

        # Phase 1: Validate market conditions
        is_valid, reason = self.position_manager.validate_market_conditions(symbol)
        if not is_valid:
            logging.info(f"Market validation failed: {reason}")
            return

        # Phase 2: Quantitative analysis
        try:
            quant_result = self.quant_integration.apply_quantitative_analysis(symbol)
            if not quant_result["should_trade"]:
                logging.info(
                    f"Quantitative analysis rejected trade: {quant_result['reason']}"
                )
                return

            entry_score = quant_result["entry_score"]
            global CURRENT_ENTRY_SCORE
            CURRENT_ENTRY_SCORE = entry_score

        except Exception as e:
            logging.warning(f"Quantitative analysis failed: {e}")
            return

        # Phase 3: Generate trading signal
        try:
            signal = self._generate_signal(symbol)
            if not signal["should_enter"]:
                logging.info(f"No entry signal: {signal['reason']}")
                return

            order_type = signal["direction"]

        except Exception as e:
            logging.error(f"Signal generation failed: {e}")
            return

        # Phase 4: Calculate risk parameters
        try:
            atr = self.market_data.calculate_atr(symbol, 14)
            if atr is None:
                logging.error("Failed to calculate ATR")
                return

            entry_price = self.market_data.get_current_price(symbol, order_type)
            if entry_price is None:
                logging.error("Failed to get entry price")
                return

            sl_price, tp_price = self.risk_validator.calculate_dynamic_stops(
                symbol, entry_price, order_type, atr
            )

            sl_distance = abs(entry_price - sl_price)

        except Exception as e:
            logging.error(f"Risk calculation failed: {e}")
            return

        # Phase 5: Calculate position size
        try:
            account_info = mt5.account_info()
            if account_info is None:
                logging.error("Failed to get account info")
                return

            lots = self.risk_validator.compute_lot_size(
                account_info.balance, self.config.risk_percent, sl_distance, symbol
            )

            if lots <= 0:
                logging.warning("Calculated lot size is zero or negative")
                return

        except Exception as e:
            logging.error(f"Position sizing failed: {e}")
            return

        # Phase 6: Execute trade
        try:
            sl_points = sl_distance / mt5.symbol_info(symbol).point
            tp_points = abs(entry_price - tp_price) / mt5.symbol_info(symbol).point

            success = self.position_manager.execute_trade(
                symbol, order_type, lots, sl_points, tp_points
            )

            if success:
                logging.info(
                    f"✅ Trade executed successfully: {order_type} {symbol} @ {entry_price}"
                )
                # Track the trade for post-mortem analysis
                # Note: Ticket association will be handled in mt5_utils monitor loop
            else:
                logging.error("❌ Trade execution failed")

        except Exception as e:
            logging.error(f"Trade execution error: {e}")

    def _generate_signal(self, symbol: str) -> Dict[str, Any]:
        """Generate trading signal using Donchian channels"""
        try:
            # Get Donchian channels
            upper_channel, lower_channel = self.market_data.get_donchian_channels(
                symbol, self.config.period
            )

            if upper_channel is None or lower_channel is None:
                return {
                    "should_enter": False,
                    "reason": "Failed to calculate Donchian channels",
                }

            # Get current price
            current_price = self.market_data.get_current_price(symbol, "BUY")
            if current_price is None:
                return {"should_enter": False, "reason": "Failed to get current price"}

            # Generate signals
            buy_signal = current_price > upper_channel
            sell_signal = current_price < lower_channel

            if buy_signal:
                return {
                    "should_enter": True,
                    "direction": "BUY",
                    "reason": "Price above upper channel",
                }
            elif sell_signal:
                return {
                    "should_enter": True,
                    "direction": "SELL",
                    "reason": "Price below lower channel",
                }
            else:
                return {"should_enter": False, "reason": "No breakout signal"}

        except Exception as e:
            logging.error(f"Signal generation error: {e}")
            return {
                "should_enter": False,
                "reason": f"Signal generation failed: {str(e)}",
            }

    def initialize_mt5(self) -> bool:
        """Initialize MT5 connection"""
        try:
            if not self.mt5_gateway.initialize():
                logging.error("Failed to initialize MT5 gateway")
                return False
            logging.info("MT5 gateway initialized successfully")
            return True
        except Exception as e:
            logging.error(f"MT5 initialization error: {e}")
            return False

    def main(self):
        """Main execution loop"""
        logging.info("Starting Donchian Strategy (Modular Version)")

        if not self.initialize_mt5():
            return

        try:
            while True:
                try:
                    self.run_strategy(self.config.symbol)
                except KeyboardInterrupt:
                    logging.info("Strategy stopped by user")
                    break
                except Exception as e:
                    logging.error(f"Strategy iteration error: {e}")

        finally:
            self.mt5_gateway.shutdown()


# Global variables for quantitative integration
# These need to be accessible from other modules
QUANT_OPTIMAL_LOTS: Optional[float] = None
CURRENT_ENTRY_SCORE: Optional[float] = None
TRADE_ENTRY_SCORES: Dict[int, float] = {}


if __name__ == "__main__":
    strategy = DonchianStrategy()
    strategy.main()
