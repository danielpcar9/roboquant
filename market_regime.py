import logging
from typing import Tuple, Optional

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

class MarketRegimeDetector:
    """Detect market regime (trending/ranging) using ADX and slope"""
    
    def __init__(self, mt5_module=None):
        self.mt5 = mt5_module or mt5
    
    def calculate_adx(self, symbol: str, period: int = 14) -> Optional[float]:
        """
        Calculate ADX (Average Directional Index)
        
        Args:
            symbol: Trading symbol
            period: ADX calculation period
            
        Returns:
            ADX value or None if calculation fails
        """
        try:
            # Get historical data
            rates = self.mt5.copy_rates_from_pos(symbol, self.mt5.TIMEFRAME_H1, 1, period + 10)  # type: ignore
            if rates is None or len(rates) < period + 10:
                logging.warning(f"Insufficient data to calculate ADX for {symbol}")
                return None
            
            # Simplified ADX calculation (in a real implementation, you would calculate the full ADX)
            # For now, we'll use a simplified approach based on price movement
            closes = [rate['close'] for rate in rates]
            highs = [rate['high'] for rate in rates]
            lows = [rate['low'] for rate in rates]
            
            # Calculate directional movement
            plus_dm = 0
            minus_dm = 0
            
            for i in range(1, len(closes)):
                up_move = highs[i] - highs[i-1]
                down_move = lows[i-1] - lows[i]
                
                if up_move > down_move and up_move > 0:
                    plus_dm += up_move
                elif down_move > up_move and down_move > 0:
                    minus_dm += down_move
            
            # Calculate ADX approximation
            tr_sum = sum(high - low for high, low in zip(highs[-period:], lows[-period:]))
            plus_di = (plus_dm / tr_sum) * 100 if tr_sum > 0 else 0
            minus_di = (minus_dm / tr_sum) * 100 if tr_sum > 0 else 0
            
            adx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0
            
            return adx
        except Exception as e:
            logging.error(f"Error calculating ADX for {symbol}: {e}")
            return None
    
    def calculate_slope(self, symbol: str, period: int = 30) -> Optional[float]:
        """
        Calculate price slope over a given period
        
        Args:
            symbol: Trading symbol
            period: Period for slope calculation
            
        Returns:
            Slope value or None if calculation fails
        """
        try:
            # Get historical data
            rates = self.mt5.copy_rates_from_pos(symbol, self.mt5.TIMEFRAME_H1, 1, period)  # type: ignore
            if rates is None or len(rates) < period:
                logging.warning(f"Insufficient data to calculate slope for {symbol}")
                return None
            
            # Simple linear regression to calculate slope
            closes = [rate['close'] for rate in rates]
            n = len(closes)
            
            # Calculate slope using least squares method
            x = list(range(n))
            y = closes
            
            # Calculate means
            x_mean = sum(x) / n
            y_mean = sum(y) / n
            
            # Calculate slope
            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y))
            denominator = sum((xi - x_mean) ** 2 for xi in x)
            
            slope = numerator / denominator if denominator != 0 else 0
            
            return slope
        except Exception as e:
            logging.error(f"Error calculating slope for {symbol}: {e}")
            return None
    
    def detect_regime(self, symbol: str, adx_period: int = 14, slope_period: int = 30) -> Tuple[str, float, float]:
        """
        Detect market regime (trending/ranging)
        
        Args:
            symbol: Trading symbol
            adx_period: ADX calculation period
            slope_period: Slope calculation period
            
        Returns:
            Tuple of (regime, adx_value, slope_value)
            - regime: "TRENDING" or "RANGING"
            - adx_value: ADX value
            - slope_value: Slope value
        """
        adx = self.calculate_adx(symbol, adx_period)
        slope = self.calculate_slope(symbol, slope_period)
        
        if adx is None or slope is None:
            return "UNKNOWN", adx or 0, slope or 0
        
        # Market regime determination
        # High ADX (>25) + significant slope indicates trending
        # Low ADX (<20) indicates ranging
        if adx > 25 and abs(slope) > 0.1:
            regime = "TRENDING"
        elif adx < 20:
            regime = "RANGING"
        else:
            regime = "TRANSITION"
        
        logging.info(f"Market regime for {symbol}: {regime} (ADX: {adx:.2f}, Slope: {slope:.4f})")
        
        return regime, adx, slope

# Global instance for easy access
market_regime_detector = MarketRegimeDetector()

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    
    # Test with a symbol (this would require MT5 to be running)
    # regime, adx, slope = market_regime_detector.detect_regime("XAUUSD")
    # print(f"Regime: {regime}, ADX: {adx:.2f}, Slope: {slope:.4f}")
    pass