"""
Validadores para la estrategia Donchian Channel

Contiene todas las funciones de validación de mercado,
filtros de riesgo y verificaciones de condiciones.

Extraído de RiskCalculator y partes de SessionManager de donchian_strategy.py
"""

import logging

import MetaTrader5 as mt5

from config.config_manager import config_manager

# from core.brokers.mt5_gateway import MT5Gateway  # Comentado temporalmente
from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
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
    def validate_trading_conditions(self, symbol: str) -> bool:
        """Validar condiciones generales de trading"""
        try:
            # Verificar que el símbolo esté disponible
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info or not symbol_info.visible:
                logging.warning(f"Symbol {symbol} not visible or unavailable")
                return False

            # Verificar que haya conectividad
            if not mt5.terminal_info():
                logging.warning("MT5 terminal not connected")
                return False

            return True
        except Exception as e:
            logging.exception(f"Error validating trading conditions: {e}")
            return False

    @handle_exception
    def validate_session_conditions(self, symbol: str) -> tuple[bool, str]:
        """Validar condiciones específicas de sesión"""
        try:
            import time

            current_time = int(time.time())
            # Convertir timestamp a hora local
            import datetime

            hour = datetime.datetime.fromtimestamp(current_time).hour

            # Horario de trading (ajustable según mercado)
            trading_start = 0  # 00:00 UTC
            trading_end = 23  # 23:59 UTC

            if not (trading_start <= hour <= trading_end):
                return False, f"Outside trading hours: {hour}:00 UTC"

            # Validar volatilidad mínima
            current_volume, avg_volume = self.market_data.get_volume_stats(symbol, 20)
            if current_volume is not None and avg_volume is not None:
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
                min_volume_ratio = config_manager.get("MIN_VOLUME_RATIO", 0.5)

                if volume_ratio < min_volume_ratio:
                    return (
                        False,
                        f"Low volume ratio: {volume_ratio:.2f} < {min_volume_ratio}",
                    )

            return True, "OK"

        except Exception as e:
            logging.exception(f"Error validating session conditions: {e}")
            return False, f"Validation error: {e!s}"
