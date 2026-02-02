"""Quantitative integration for the Donchian strategy"""

import logging
from typing import TYPE_CHECKING, Any

import numpy as np

from core.quant_engine import QuantitativeEngine

# Importar logger de comportamiento
from trading_behavior_logger import get_behavior_logger

from .validators.ml_validator import MLStrategyValidator


class QuantitativeIntegration:
    """Integration class for quantitative analysis in the Donchian strategy"""

    def __init__(self):
        # Note: Not initializing quant_engine to avoid circular dependency
        # quant_engine functionality is now in QuantitativeIntegration directly
        self.ml_validator = MLStrategyValidator()  # Initialize ML validator
        self.behavior_logger = get_behavior_logger()  # Initialize behavior logger
        logging.info("QuantitativeIntegration initialized")

    def _should_trade_adaptive(self, recommendation: str, ml_confidence: float,
                              entry_score: float, adx_value: float, di_diff: float) -> bool:
        """Determina si debe operar usando sistema de votación flexible y umbrales adaptativos"""
        # Verificar que sea una recomendación válida para trading
        valid_recommendations = ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"]
        if recommendation not in valid_recommendations:
            return False

        # Sistema de votación flexible basado en regímenes de mercado
        # Ajustar umbrales según fuerza de tendencia (ADX) - REDUCIDOS PARA MÁS OPERACIONES
        if adx_value > 40:
            # Tendencia fuerte - umbrales más permisivos
            ml_threshold = 0.25  # Reducido de 0.40
            quant_threshold = 0.15  # Reducido de 0.25
            regime = "FUERTE"
        elif adx_value > 30:
            # Tendencia moderada - umbrales intermedios
            ml_threshold = 0.35  # Reducido de 0.50
            quant_threshold = 0.25  # Reducido de 0.35
            regime = "MODERADA"
        else:
            # Rango lateral/débil - umbrales más estrictos
            ml_threshold = 0.45  # Reducido de 0.65
            quant_threshold = 0.30  # Reducido de 0.45
            regime = "LATERAL"

        # DETECCIÓN DE TENDENCIA FUERTE: Permitir SELL si DI- > DI+ por 15+ puntos
        strong_sell_condition = di_diff < -15 and recommendation in {
            "SELL",
            "STRONG_SELL",
        }

        # Sistema de votación ponderada en lugar de AND estricto - CAMBIADO A OR
        # Calcular puntuación combinada
        ml_weight = 0.5
        quant_weight = 0.5

        combined_score = (ml_confidence * ml_weight) + (entry_score * quant_weight)
        min_combined_threshold = 0.25  # Reducido de 0.35

        # Validación con OR lógico en lugar de AND
        ml_approval = ml_confidence > ml_threshold
        quant_approval = entry_score > quant_threshold

        # Aprobación final: ML O análisis cuantitativo aprueban, o tendencia fuerte detectada
        meets_criteria = ml_approval or quant_approval or strong_sell_condition or (combined_score > min_combined_threshold)

        # Logging detallado para monitoreo
        logging.debug(
            f"Validación adaptativa [{regime}] - "
            f"ADX: {adx_value:.2f}, DI Diff: {di_diff:.2f}\n"
            f"  Umbrales -> ML: {ml_threshold:.2f}, Quant: {quant_threshold:.2f}\n"
            f"  Ponderación -> ML Weight: {ml_weight:.2f}, Quant Weight: {quant_weight:.2f}\n"
            f"  Scores -> ML: {ml_confidence:.3f}, Quant: {entry_score:.3f}\n"
            f"  Combined Score: {combined_score:.3f} (threshold: {min_combined_threshold})\n"
            f"  ML Approval: {ml_approval}, Quant Approval: {quant_approval}\n"
            f"  Strong Sell Condition: {strong_sell_condition}\n"
            f"  Final Decision: {meets_criteria}"
        )

        return meets_criteria

    def calculate_entry_score(self, prices: np.ndarray, adx: float, di_plus: float, di_minus: float) -> dict[str, Any]:
        """Calculate entry score based on quantitative analysis (moved from QuantitativeEngine)

        Args:
            prices: Array of price data
            adx: Average Directional Index value
            di_plus: Positive Directional Indicator
            di_minus: Negative Directional Indicator

        Returns:
            Dictionary with entry_score and recommendation
        """
        try:
            # Calculate statistical measures
            returns = np.diff(prices) / prices[:-1]
            volatility = np.std(returns)
            trend_strength = abs(di_plus - di_minus) / (di_plus + di_minus + 0.001)

            # Momentum analysis
            recent_returns = returns[-10:] if len(returns) >= 10 else returns
            momentum = np.mean(recent_returns)

            # ADX contribution (trend quality)
            adx_contribution = min(adx / 50.0, 1.0)  # Normalize ADX to 0-1

            # Combine factors with weights
            momentum_score = np.clip(momentum * 100, -1, 1)  # Scale momentum
            volatility_score = np.clip(1 - volatility * 10, 0, 1)  # Lower volatility is better
            trend_score = np.clip(trend_strength, 0, 1)

            # Weighted combination
            entry_score = (
                0.4 * momentum_score +
                0.3 * volatility_score +
                0.3 * trend_score * adx_contribution
            )

            # Ensure score is between 0 and 1
            entry_score = np.clip(entry_score, 0, 1)

            # Generate recommendation
            if entry_score > 0.7:
                recommendation = "STRONG_BUY" if momentum > 0 else "STRONG_SELL"
            elif entry_score > 0.5:
                recommendation = "BUY" if momentum > 0 else "SELL"
            elif entry_score > 0.3:
                recommendation = "WEAK_BUY" if momentum > 0 else "WEAK_SELL"
            else:
                recommendation = "AVOID"

            return {
                "entry_score": float(entry_score),
                "recommendation": recommendation,
                "components": {
                    "momentum": float(momentum_score),
                    "volatility": float(volatility_score),
                    "trend": float(trend_score),
                    "adx_factor": float(adx_contribution)
                }
            }

        except Exception as e:
            logging.error(f"Error calculating entry score: {e}")
            return {
                "entry_score": 0.0,
                "recommendation": "AVOID",
                "components": {}
            }

    def apply_quantitative_analysis(self, symbol: str) -> dict[str, Any]:
        """Apply quantitative analysis to determine if a trade should be made

        Args:
            symbol: Trading symbol

        Returns:
            Dictionary with analysis results including:
            - should_trade: Boolean indicating if trade should proceed
            - entry_score: Probability score for entry (0-1)
            - reason: Explanation for the decision

        """
        try:
            # Get market data for quantitative analysis
            import MetaTrader5 as mt5

            from core.donchian_components.calculators.technical_indicators import (
                TechnicalIndicatorsCalculator,
            )

            calculator = TechnicalIndicatorsCalculator()

            # Get price data using MT5 directly (last 100 candles)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)  # type: ignore
            if rates is None or len(rates) < 50:
                return {
                    "should_trade": False,
                    "entry_score": 0.0,
                    "reason": "Insufficient market data for quantitative analysis",
                }

            # Extract closing prices
            prices = [rate[4] for rate in rates]  # close price is at index 4
            import numpy as np
            price_array = np.array(prices)

            # Calculate ADX and DI using existing market data service
            adx_data = calculator.calculate_adx(symbol, 14)
            if adx_data is not None:
                adx_value = adx_data.get("adx", 25.0)
                di_plus = adx_data.get("di_plus", 25.0)
                di_minus = adx_data.get("di_minus", 25.0)
                logging.debug(f"Using calculated ADX values: ADX={adx_value:.2f}, DI+={di_plus:.2f}, DI-={di_minus:.2f}")
                logging.debug(f"DI Difference: {di_plus - di_minus:.2f}")
            else:
                # Fallback values
                adx_value = 25.0
                di_plus = 25.0
                di_minus = 25.0
                logging.debug("Using fallback ADX values")

            # Perform quantitative analysis
            analysis_result = self.calculate_entry_score(
                price_array, adx_value, di_plus, di_minus
            )

            entry_score = analysis_result["entry_score"]
            recommendation = analysis_result["recommendation"]

            # Extract features for ML validation
            features = self.ml_validator.extract_features(symbol)

            # Apply ML validation if features are available
            ml_should_trade = True  # Default to True if no ML model
            ml_confidence = 0.0
            ml_action = "HOLD"

            if features:
                ml_should_trade, ml_confidence, ml_action = self.ml_validator.validate_signal(features)
                logging.info(f"ML Validation - Should Trade: {ml_should_trade}, Confidence: {ml_confidence:.3f}, Action: {ml_action}")

            # Combined decision logic with adaptive thresholds
            # Both quantitative analysis AND ML validation must approve the trade
            di_diff = di_plus - di_minus
            should_trade = self._should_trade_adaptive(
                recommendation, ml_confidence, entry_score, adx_value, di_diff
            )

            result = {
                "should_trade": should_trade,
                "entry_score": entry_score,
                "recommendation": recommendation,
                "reason": f"Quantitative analysis: {recommendation} (score: {entry_score:.3f})",
                "components": analysis_result["components"],
                "market_data": {
                    "adx": adx_value,
                    "di_plus": di_plus,
                    "di_minus": di_minus,
                    "di_difference": di_plus - di_minus,
                    "current_price": prices[-1] if prices else None
                },
                "ml_validation": {
                    "ml_approved": ml_should_trade,
                    "ml_confidence": ml_confidence,
                    "ml_action": ml_action,
                    "features_available": bool(features)
                },
                "symbol": symbol  # Agregar símbolo para logging
            }

            # Registrar decisión en el logger de comportamiento
            try:
                self.behavior_logger.log_decision(result)
            except Exception as log_error:
                logging.warning(f"Error registrando decisión: {log_error}")

            logging.info(
                f"📊 Quantitative Analysis for {symbol}: Score={entry_score:.3f}, "
                f"Recommendation={recommendation}, Trade={'ALLOWED' if should_trade else 'DENIED'}"
            )
            logging.info(
                f"📈 Market Data - ADX: {adx_value:.2f}, DI+: {di_plus:.2f}, DI-: {di_minus:.2f}, "
                f"DI Diff: {di_plus - di_minus:.2f}"
            )

            return result

        except Exception as e:
            logging.exception("Quantitative analysis failed: %s", e)
            return {
                "should_trade": False,
                "entry_score": 0.0,
                "reason": f"Analysis error: {e!s}",
            }

# Backward compatibility - Alias for legacy code

if TYPE_CHECKING:
    from .engine import QuantitativeEngine
else:
    QuantitativeEngine = QuantitativeIntegration

# Backward compatibility
# Note: QuantitativeEngine is now an alias for QuantitativeIntegration
# This maintains backward compatibility while avoiding circular imports
