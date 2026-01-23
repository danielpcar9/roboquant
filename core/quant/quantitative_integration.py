"""Quantitative integration for the Donchian strategy"""

import logging
from typing import Any

from core.quant_engine import QuantitativeEngine


class QuantitativeIntegration:
    """Integration class for quantitative analysis in the Donchian strategy"""

    def __init__(self):
        self.quant_engine = QuantitativeEngine()
        logging.info("QuantitativeIntegration initialized")

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
            from core.donchian_components.calculators.technical_indicators import TechnicalIndicatorsCalculator
            import MetaTrader5 as mt5
                
            calculator = TechnicalIndicatorsCalculator()
                
            # Get price data using MT5 directly (last 100 candles)
            import MetaTrader5 as mt5
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
            try:
                # Try to get ADX data from calculator 
                adx_data = calculator.calculate_adx(symbol, 14)
                if adx_data is not None:
                    adx_value = adx_data.get("adx", 25.0)
                    di_plus = adx_data.get("di_plus", 25.0)
                    di_minus = adx_data.get("di_minus", 25.0)
                    logging.debug(f"Using calculated ADX values: ADX={adx_value:.2f}, DI+={di_plus:.2f}, DI-={di_minus:.2f}")
                else:
                    # Fallback values
                    adx_value = 25.0
                    di_plus = 25.0
                    di_minus = 25.0
                    logging.debug("Using fallback ADX values")
            except AttributeError:
                # Method doesn't exist, use fallback values
                adx_value = 25.0
                di_plus = 25.0
                di_minus = 25.0
                logging.debug("ADX method not available, using defaults")
                
            # Perform quantitative analysis
            analysis_result = self.quant_engine.calculate_entry_score(
                price_array, adx_value, di_plus, di_minus
            )
                
            entry_score = analysis_result["entry_score"]
            recommendation = analysis_result["recommendation"]
                
            # Decision logic based on quantitative analysis
            should_trade = recommendation in ["STRONG_BUY", "BUY", "STRONG_SELL", "SELL"]
                
            result = {
                "should_trade": should_trade,
                "entry_score": entry_score,
                "recommendation": recommendation,
                "reason": f"Quantitative analysis: {recommendation} (score: {entry_score:.3f})",
                "components": analysis_result["components"],
            }
                
            logging.info(
                f"📊 Quantitative Analysis for {symbol}: Score={entry_score:.3f}, "
                f"Recommendation={recommendation}, Trade={'ALLOWED' if should_trade else 'DENIED'}"
            )
                
            return result
                
        except Exception as e:
            logging.exception("Quantitative analysis failed: %s", e)
            return {
                "should_trade": False,
                "entry_score": 0.0,
                "reason": f"Analysis error: {e!s}",
            }
