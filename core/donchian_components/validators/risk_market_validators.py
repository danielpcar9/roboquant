"""
Validadores para la estrategia Donchian Channel

Contiene todas las funciones de validación de mercado,
filtros de riesgo y verificaciones de condiciones.

Extraído de RiskCalculator y partes de SessionManager de donchian_strategy.py
"""

import logging

from config.config_manager import config_manager

# from core.brokers.mt5_gateway import MT5Gateway  # Comentado temporalmente
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from core.mt5_compat import mt5
from utils.decorators import handle_exception


class RiskValidator:
    """Validador especializado en cálculos de riesgo y gestión de capital"""

    def __init__(
        self, market_data_service: TechnicalIndicatorsCalculator, mt5_module: mt5 = None,
    ):
        self.market_data = market_data_service
        self.mt5 = mt5_module or mt5  # Usar el pasado o el global

    @handle_exception
    def calculate_dynamic_stops(
        self, symbol: str, entry_price: float, order_type: str, atr: float,
    ) -> tuple[float, float]:
        """
        Calculate dynamic SL/TP based on ATR and risk profile.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            order_type: "BUY" or "SELL"
            atr: Average True Range value

        Returns:
            tuple: (sl_price, tp_price)

        """
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error(f"Failed to get symbol info for {symbol}")
            # Fallback to ATR-based values with default multipliers
            point = 0.01 if "JPY" not in symbol else 0.001
            # For NASDAQ, adjust point value
            if "NASDAQ" in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            # Use default ATR multipliers for fallback
            sl_multiplier = 3.0  # LOW RISK profile default
            tp_multiplier = 6.0  # LOW RISK profile default
            # Estimate ATR if we can't get it
            estimated_atr = 5.0  # Default ATR estimate
            sl_distance = sl_multiplier * estimated_atr
            tp_distance = tp_multiplier * estimated_atr

            if order_type == "BUY":
                sl_price = entry_price - (sl_distance * point)
                tp_price = entry_price + (tp_distance * point)
            else:
                sl_price = entry_price + (sl_distance * point)
                tp_price = entry_price - (tp_distance * point)
            return sl_price, tp_price

        point = symbol_info.point

        # Adjust point value for NASDAQ
        if "NASDAQ" in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices

        # Determine if we're using LOW RISK (default) or HIGH RISK (aggressive) profile
        # Based on the risk_per_trade_pct in the current configuration
        risk_percent = config_manager.get("RISK_PERCENT")
        risk_profile = "HIGH" if risk_percent > 1.0 else "LOW"

        # Get ATR multipliers from configuration
        # cfg = get_set_manager()  # Comentado temporalmente

        try:

            if risk_profile == "LOW":  # Default profile
                sl_multiplier = config_manager.get("SL_ATR_MULTIPLIER", 3.0)
                tp_multiplier = config_manager.get("TP_ATR_MULTIPLIER", 6.0)
            else:  # HIGH RISK (aggressive)
                sl_multiplier = config_manager.get("SL_ATR_MULTIPLIER", 2.0)
                tp_multiplier = config_manager.get("TP_ATR_MULTIPLIER", 1.5)
        except Exception as e:
            logging.warning(
                f"Failed to load ATR multipliers from config, using defaults: {e}",
            )
            # Fallback to configuration-based defaults
            if risk_profile == "LOW":
                sl_multiplier = config_manager.get("SL_ATR_MULTIPLIER", 3.0)
                tp_multiplier = config_manager.get("TP_ATR_MULTIPLIER", 6.0)
            else:
                sl_multiplier = config_manager.get("SL_ATR_MULTIPLIER", 2.0)
                tp_multiplier = config_manager.get("TP_ATR_MULTIPLIER", 1.5)

        # Calculate SL/TP distances based on ATR multipliers
        # Handle zero ATR case
        if atr <= 0:
            # Use minimum distances when ATR is zero or negative
            min_sl_distance = 5.0  # Minimum 5 points
            min_tp_distance = 10.0  # Minimum 10 points
            sl_distance = min_sl_distance
            tp_distance = min_tp_distance
        else:
            sl_distance = sl_multiplier * atr
            tp_distance = tp_multiplier * atr

        sl_price = (
            entry_price - sl_distance
            if order_type == "BUY"
            else entry_price + sl_distance
        )
        tp_price = (
            entry_price + tp_distance
            if order_type == "BUY"
            else entry_price - tp_distance
        )

        logging.info(
            f"Dynamic stops calculated - Profile: {risk_profile}, SL: {sl_price:.5f}, TP: {tp_price:.5f}",
        )
        return sl_price, tp_price

    @handle_exception
    def compute_lot_size(
        self, balance: float, risk_pct: float, sl_distance: float, symbol: str,
    ) -> float:
        """Calculate lot size based on risk percentage and stop loss distance"""

        # Check if quantitative optimal lot size is available from global variables
        try:
            from core.donchian_strategy import QUANT_OPTIMAL_LOTS
            if QUANT_OPTIMAL_LOTS is not None:
                quant_lots = QUANT_OPTIMAL_LOTS
                logging.info(f"Using quantitative optimal lot size: {quant_lots:.3f}")

                # Validate and return quantitative lot size
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    logging.error(f"Failed to get symbol info for {symbol}")
                    return 0.01  # Seguridad: mínimo absoluto

                # Apply broker limits to quantitative lot size
                min_lot = symbol_info.volume_min
                max_lot = symbol_info.volume_max or quant_lots

                # Apply safety limits
                max_allowed_lots = 0.30  # Safety limit
                quant_lots = max(min_lot, min(quant_lots, max_lot, max_allowed_lots))

                # Apply simple volume step normalization
                step = symbol_info.volume_step or 0.01
                normalized_lots = round(quant_lots / step) * step
                normalized_lots = min(normalized_lots, max_allowed_lots)

                logging.info(
                    f"Quantitative lot size after validation: {normalized_lots:.3f}",
                )
                return normalized_lots
        except ImportError:
            # Fall back to traditional calculation if QUANT_OPTIMAL_LOTS not available
            pass

        # Traditional risk-based calculation
        risk_amount = balance * (risk_pct / 100.0)

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return 0.01  # Seguridad: mínimo absoluto

        # For XAU/USD, 1 lot = 100 oz troy, so point value is 100
        point_value = 100.0 if "XAU" in symbol or "GOLD" in symbol else 1.0
        point = symbol_info.point

        if point == 0 or sl_distance == 0:
            logging.warning(
                f"Invalid point or SL distance for {symbol}, using minimum lot size",
            )
            return 0.01

        # LOG DETALLADO para debugging
        logging.info("=== LOT CALCULATION DEBUG ===")
        logging.info(f"Symbol: {symbol}")
        logging.info(f"Balance: ${balance:.2f}")
        logging.info(f"Risk %: {risk_pct}%")
        logging.info(f"Risk Amount: ${risk_amount:.2f}")
        logging.info(f"SL Distance (price points): {sl_distance:.5f}")
        logging.info(f"Point value: {point:.5f}")
        logging.info(f"Contract multiplier: {point_value:.2f}")

        # Calculate lots: risk_amount / (sl_distance * point_value)
        # For XAU/USD: sl_distance is already in price points, point_value is contract size (100 oz)
        # Risk per lot = sl_distance * point_value = points * ($ per point per lot)
        # So lots = risk_amount / (sl_distance * point_value)
        lots = risk_amount / (sl_distance * point_value)

        logging.info(f"Raw calculated lots: {lots:.6f}")

        # Ensure minimum lot size
        min_lot = symbol_info.volume_min
        lots = max(lots, min_lot)

        logging.info(f"After min limit ({min_lot}): {lots:.6f}")

        # LÍMITE DE SEGURIDAD MÁXIMO - AJUSTADO PARA MAYOR RIESGO
        # Límite moderado: máximo 0.60 lotes para permitir mayor exposición
        max_allowed_lots = 0.60
        if lots > max_allowed_lots:
            logging.warning(
                f"⚠️ SEGURIDAD: Lotaje {lots:.2f} excede límite {max_allowed_lots:.2f}, FORZANDO a límite",
            )
            lots = max_allowed_lots

        # Ensure we don't exceed broker maximum lot size
        max_lot = symbol_info.volume_max or lots
        lots = min(lots, max_lot)

        logging.info(f"After max safety limit ({max_allowed_lots}): {lots:.6f}")

        # Normalize to broker requirements (simple rounding)
        step = symbol_info.volume_step or 0.01
        normalized_lots = round(lots / step) * step

        logging.info(f"After normalization: {normalized_lots:.6f}")

        # VALIDACIÓN FINAL CRÍTICA
        if normalized_lots > max_allowed_lots:
            logging.error(
                f"🚨 CRÍTICO: normalize_volume retornó {normalized_lots:.2f} que excede límite {max_allowed_lots:.2f}. FORZANDO a límite.",
            )
            normalized_lots = max_allowed_lots

        logging.info(f"FINAL LOT SIZE: {normalized_lots:.6f}")
        logging.info("=== END LOT CALCULATION ===")

        return normalized_lots

    @handle_exception
    def validate_stop_loss_distance(
        self, sl_points: float, symbol: str,
    ) -> tuple[bool, str]:
        """Validate stop loss distance is reasonable"""
        min_sl_points = config_manager.get("MIN_SL_POINTS", 5.0)
        max_sl_points = config_manager.get("MAX_SL_POINTS", 100.0)

        if sl_points < min_sl_points:
            return (
                False,
                f"SL distance {sl_points:.1f} points too small, minimum {min_sl_points:.1f}",
            )
        if sl_points > max_sl_points:
            return (
                False,
                f"SL distance {sl_points:.1f} points too large, maximum {max_sl_points:.1f}",
            )
        return True, f"SL distance {sl_points:.1f} points is acceptable"

    @handle_exception
    def validate_take_profit_ratio(
        self, tp_points: float, sl_points: float,
    ) -> tuple[bool, str]:
        """Validate take profit to stop loss ratio"""
        if sl_points <= 0:
            return False, "Invalid stop loss distance"

        ratio = tp_points / sl_points
        min_ratio = config_manager.get("MIN_TP_SL_RATIO", 1.5)

        if ratio < min_ratio:
            return False, f"TP/SL ratio {ratio:.2f} too low, minimum {min_ratio:.2f}"
        return True, f"TP/SL ratio {ratio:.2f} is acceptable"

    @handle_exception
    def check_account_risk_limits(
        self, balance: float, risk_amount: float, max_risk_percent: float,
    ) -> tuple[bool, str]:
        """Check if risk amount is within account limits"""
        risk_percent = (risk_amount / balance) * 100 if balance > 0 else 0

        if risk_percent > max_risk_percent:
            return (
                False,
                f"Risk {risk_percent:.1f}% exceeds maximum {max_risk_percent:.1f}%",
            )
        return True, f"Risk {risk_percent:.1f}% is within limits"

    @handle_exception
    def get_account_exposure(self) -> float:
        """Get total account exposure from open positions"""
        try:
            positions = self.mt5.positions_get()
            if positions is None:
                return 0.0

            total_exposure = 0.0
            for position in positions:
                total_exposure += abs(position.volume)

            return total_exposure
        except Exception as e:
            logging.exception(f"Error getting account exposure: {e}")
            return 0.0

    @handle_exception
    def validate_position_sizing(
        self, lot_size: float, max_lot_size: float, min_lot_size: float,
    ) -> tuple[bool, str]:
        """Validate position lot size is within limits"""
        if lot_size < min_lot_size:
            return (
                False,
                f"Lot size {lot_size:.3f} too small, minimum {min_lot_size:.3f}",
            )
        if lot_size > max_lot_size:
            return (
                False,
                f"Lot size {lot_size:.3f} too large, maximum {max_lot_size:.3f}",
            )
        return True, f"Lot size {lot_size:.3f} is acceptable"


class MarketValidator:
    """Validador especializado en condiciones de mercado y sesiones"""

    def __init__(
        self, mt5_module: mt5, market_data_service: TechnicalIndicatorsCalculator,
    ):
        self.mt5 = mt5_module
        self.market_data = market_data_service
        self.session_pending_orders = {}  # Track pending orders by session
        self.last_session = None  # Track the last session

    @handle_exception
    def is_trading_session_active(self) -> tuple[bool, str]:
        """Check if current time is within allowed trading hours"""
        # Trading hours restriction DISABLED - bot operates 24/7
        return True, "Trading session active (24/7 mode)"

    @handle_exception
    def check_spread(self, symbol: str) -> tuple[bool, str]:
        """Check if current spread is within acceptable limits"""
        spread = self.market_data.get_spread(symbol)
        if spread is None:
            return False, "Failed to get spread data"

        max_spread = config_manager.get("MAX_SPREAD_POINTS", 300)
        if spread > max_spread:
            return False, f"Spread too wide: {spread:.1f} > {max_spread}"

        return True, f"Spread acceptable: {spread:.1f}"

    @handle_exception
    def is_market_volatile(self, symbol: str, atr_threshold: float) -> tuple[bool, str]:
        """Check if market volatility is within limits using ATR"""
        atr = self.market_data.calculate_atr(symbol)
        if atr is None:
            return True, "Insufficient data for volatility check, assuming OK"

        if atr > atr_threshold:
            return False, f"Market too volatile: ATR {atr:.5f} > {atr_threshold}"

        return True, f"Market volatility acceptable: ATR {atr:.5f}"

    @handle_exception
    def has_recent_news_events(self, symbol: str) -> tuple[bool, str]:
        """Check for high impact news events (Stub)"""
        # This is a stub - real implementation would check an economic calendar
        return False, "No high impact news detected"

    @handle_exception
    def validate_price_action(self, symbol: str, lookback: int = 20) -> tuple[bool, str]:
        """Validate recent price action (look for spikes, gaps, etc.)"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.market_data.timeframe, 1, lookback)
        if rates is None or len(rates) < 2:
            return True, "Insufficient data for price action validation"

        # Calculate average body size for comparison
        bodies = [abs(rate["close"] - rate["open"]) for rate in rates]
        avg_body = sum(bodies) / len(bodies)

        # Check for extreme candle size (relative to average and absolute)
        for i, rate in enumerate(rates):
            body = bodies[i]
            # If body is more than 3x the average OR more than 1% of price
            if (body > avg_body * 2.5 and body > 0) or body > 0.01 * rate["open"]:
                return False, f"Extreme price movement detected: {body:.2f} points"

        return True, "Price action normal"

    @handle_exception
    def is_liquidity_sufficient(
        self, symbol: str, lookback: int = 20, min_avg_volume: float = 10.0,
    ) -> tuple[bool, str]:
        """Check if trading volume is sufficient for liquidity"""
        _, avg_volume = self.market_data.get_volume_stats(symbol, lookback)
        if avg_volume is None:
            return True, "Insufficient data for liquidity check"

        if avg_volume < min_avg_volume:
            return False, f"Insufficient liquidity: Avg Volume {avg_volume:.1f} < {min_avg_volume}"

        return True, f"Liquidity sufficient: Avg Volume {avg_volume:.1f}"

    @handle_exception
    def get_market_regime(self, symbol: str, period: int = 50) -> tuple[str, float]:
        """Get current market regime and volatility"""
        # Very basic regime detection
        atr = self.market_data.calculate_atr(symbol, period) or 0.0

        # Simple logic: higher than usual ATR = volatile
        if atr > 0.002: # Crude threshold
            return "volatile", atr

        # This could be much more sophisticated
        return "ranging", atr
