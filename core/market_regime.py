import logging

import numpy as np
import pandas as pd

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5


class MarketRegimeDetector:
    """Detect market regime (trending/ranging) using ADX and slope"""

    def __init__(self, mt5_module=None):
        self.mt5 = mt5_module or mt5

    def _get_timeframe_from_config(self):
        """Convert timeframe name to MT5 constant"""
        # Import config manager to get the timeframe from config
        try:
            from config.config_manager import config_manager

            timeframe_name = config_manager.get("TIMEFRAME", "H1")  # Default to H1
        except ImportError:
            # If config manager is not available, default to H1
            timeframe_name = "H1"

        timeframe_map = {
            "M1": self.mt5.TIMEFRAME_M1,
            "M5": self.mt5.TIMEFRAME_M5,
            "M15": self.mt5.TIMEFRAME_M15,
            "M30": self.mt5.TIMEFRAME_M30,
            "H1": self.mt5.TIMEFRAME_H1,
            "H4": self.mt5.TIMEFRAME_H4,
            "D1": self.mt5.TIMEFRAME_D1,
            "W1": self.mt5.TIMEFRAME_W1,
            "MN1": self.mt5.TIMEFRAME_MN1,
        }
        return timeframe_map.get(timeframe_name.upper(), self.mt5.TIMEFRAME_H1)

    def calculate_adx(self, symbol: str, period: int = 14) -> float | None:
        """
        Calculate ADX (Average Directional Index) - IMPROVED VERSION

        Args:
            symbol: Trading symbol
            period: ADX calculation period

        Returns:
            ADX value or None if calculation fails

        """
        try:
            # Get historical data (need more bars for accurate ADX)
            bars_needed = period * 3  # Ensure enough data
            rates = self.mt5.copy_rates_from_pos(
                symbol, self._get_timeframe_from_config(), 1, bars_needed,
            )  # type: ignore
            if rates is None or len(rates) < bars_needed:
                logging.warning(f"Insufficient data to calculate ADX for {symbol}")
                return None

            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(rates)

            # Calculate True Range
            df["high_low"] = df["high"] - df["low"]
            df["high_close"] = np.abs(df["high"] - df["close"].shift())
            df["low_close"] = np.abs(df["low"] - df["close"].shift())
            df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

            # Calculate +DM and -DM
            df["up_move"] = df["high"] - df["high"].shift()
            df["down_move"] = df["low"].shift() - df["low"]

            df["plus_dm"] = np.where(
                (df["up_move"] > df["down_move"]) & (df["up_move"] > 0),
                df["up_move"],
                0,
            )
            df["minus_dm"] = np.where(
                (df["down_move"] > df["up_move"]) & (df["down_move"] > 0),
                df["down_move"],
                0,
            )

            # Smooth using Wilder's smoothing (exponential moving average)
            alpha = 1 / period
            df["atr"] = df["tr"].ewm(alpha=alpha, adjust=False).mean()
            df["plus_dm_smooth"] = df["plus_dm"].ewm(alpha=alpha, adjust=False).mean()
            df["minus_dm_smooth"] = df["minus_dm"].ewm(alpha=alpha, adjust=False).mean()

            # Calculate +DI and -DI
            df["plus_di"] = 100 * (df["plus_dm_smooth"] / df["atr"])
            df["minus_di"] = 100 * (df["minus_dm_smooth"] / df["atr"])

            # Calculate DX
            df["dx"] = (
                100
                * np.abs(df["plus_di"] - df["minus_di"])
                / (df["plus_di"] + df["minus_di"])
            )

            # Calculate ADX (smoothed DX)
            df["adx"] = df["dx"].ewm(alpha=alpha, adjust=False).mean()

            # Return most recent ADX value
            adx_value = df["adx"].iloc[-1]

            if pd.isna(adx_value):
                logging.warning(f"ADX calculation resulted in NaN for {symbol}")
                return None

            return float(adx_value)

        except Exception as e:
            logging.exception(f"Error calculating ADX for {symbol}: {e}")
            return None

    def calculate_slope(self, symbol: str, period: int = 30) -> float | None:
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
            rates = self.mt5.copy_rates_from_pos(
                symbol, self._get_timeframe_from_config(), 1, period,
            )  # type: ignore
            if rates is None or len(rates) < period:
                logging.warning(f"Insufficient data to calculate slope for {symbol}")
                return None

            # Simple linear regression to calculate slope
            closes = [rate["close"] for rate in rates]
            n = len(closes)

            # Calculate slope using least squares method
            x = list(range(n))
            y = closes

            # Calculate means
            x_mean = sum(x) / n
            y_mean = sum(y) / n

            # Calculate slope
            numerator = sum((xi - x_mean) * (yi - y_mean) for xi, yi in zip(x, y, strict=True))
            denominator = sum((xi - x_mean) ** 2 for xi in x)

            slope = numerator / denominator if denominator != 0 else 0

            return slope
        except Exception as e:
            logging.exception(f"Error calculating slope for {symbol}: {e}")
            return None

    def detect_regime(
        self,
        symbol: str,
        adx_period: int = 14,
        slope_period: int = 30,
        adx_threshold: int = 20,
        di_threshold: int = 26,
    ) -> tuple[str, float, float]:
        """
        Detect market regime (trending/ranging) - IMPROVED VERSION with DI filter

        Args:
            symbol: Trading symbol
            adx_period: ADX calculation period
            slope_period: Slope calculation period
            adx_threshold: ADX threshold for trending market (default 20)
            di_threshold: Minimum DI value for strong directional movement (default 26)

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

        # Get +DI and -DI for additional validation
        try:
            # Get historical data for DI calculation
            bars_needed = adx_period * 3
            rates = self.mt5.copy_rates_from_pos(
                symbol, self._get_timeframe_from_config(), 1, bars_needed,
            )  # type: ignore
            if rates is None or len(rates) < bars_needed:
                # Fallback to basic ADX check if can't get DI
                if adx > adx_threshold:
                    regime = "TRENDING"
                else:
                    regime = "RANGING"
                logging.info(
                    f"Market regime for {symbol}: {regime} (ADX: {adx:.2f}, Slope: {slope:.4f}, Threshold: {adx_threshold})",
                )
                return regime, adx, slope

            # Convert to DataFrame for DI calculation
            df = pd.DataFrame(rates)

            # Calculate True Range and DM (reusing logic from calculate_adx)
            df["high_low"] = df["high"] - df["low"]
            df["high_close"] = np.abs(df["high"] - df["close"].shift())
            df["low_close"] = np.abs(df["low"] - df["close"].shift())
            df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

            # Calculate +DM and -DM
            df["up_move"] = df["high"] - df["high"].shift()
            df["down_move"] = df["low"].shift() - df["low"]

            df["plus_dm"] = np.where(
                (df["up_move"] > df["down_move"]) & (df["up_move"] > 0),
                df["up_move"],
                0,
            )
            df["minus_dm"] = np.where(
                (df["down_move"] > df["up_move"]) & (df["down_move"] > 0),
                df["down_move"],
                0,
            )

            # Smooth using Wilder's smoothing
            alpha = 1 / adx_period
            df["atr"] = df["tr"].ewm(alpha=alpha, adjust=False).mean()
            df["plus_dm_smooth"] = df["plus_dm"].ewm(alpha=alpha, adjust=False).mean()
            df["minus_dm_smooth"] = df["minus_dm"].ewm(alpha=alpha, adjust=False).mean()

            # Calculate +DI and -DI
            df["plus_di"] = 100 * (df["plus_dm_smooth"] / df["atr"])
            df["minus_di"] = 100 * (df["minus_dm_smooth"] / df["atr"])

            # Get most recent DI values
            plus_di = df["plus_di"].iloc[-1]
            minus_di = df["minus_di"].iloc[-1]

            if pd.isna(plus_di) or pd.isna(minus_di):
                # Fallback to basic ADX check
                if adx > adx_threshold:
                    regime = "TRENDING"
                else:
                    regime = "RANGING"
                logging.info(
                    f"Market regime for {symbol}: {regime} (ADX: {adx:.2f}, Slope: {slope:.4f}, Threshold: {adx_threshold})",
                )
                return regime, adx, slope

            # === ENHANCED REGIME DETECTION with DI Filter ===
            # Rule 1: Basic ADX check
            if adx <= adx_threshold:
                regime = "RANGING"
                logging.info(
                    f"Market regime for {symbol}: {regime} (ADX: {adx:.2f} <= {adx_threshold})",
                )
            # Rule 2: ADX high BUT no dominant DI -> disguised ranging market
            elif max(plus_di, minus_di) < di_threshold:
                regime = "RANGING"
                logging.info(
                    f"Market regime for {symbol}: {regime} (ADX: {adx:.2f} > {adx_threshold}, but max DI: {max(plus_di, minus_di):.2f} < {di_threshold}) - Choppy market",
                )
            # Rule 3: ADX high AND strong DI -> true trending market
            else:
                regime = "TRENDING"
                dominant_di = "Bullish" if plus_di > minus_di else "Bearish"
                logging.info(
                    f"Market regime for {symbol}: {regime} (ADX: {adx:.2f}, +DI: {plus_di:.2f}, -DI: {minus_di:.2f}, {dominant_di})",
                )

        except Exception as e:
            logging.warning(
                f"Error calculating DI for {symbol}: {e}. Falling back to basic ADX check.",
            )
            # Fallback to basic ADX-only check
            if adx > adx_threshold:
                regime = "TRENDING"
            else:
                regime = "RANGING"
            logging.info(
                f"Market regime for {symbol}: {regime} (ADX: {adx:.2f}, Slope: {slope:.4f}, Threshold: {adx_threshold})",
            )

        return regime, adx, slope

    def get_di_values(self, symbol: str, adx_period: int = 14) -> tuple[float, float]:
        """
        Get +DI and -DI values for quantitative analysis

        Args:
            symbol: Trading symbol
            adx_period: Period for DI calculation

        Returns:
            Tuple of (plus_di, minus_di) or (0, 0) if calculation fails

        """
        try:
            # Get historical data for DI calculation
            bars_needed = adx_period * 3
            rates = self.mt5.copy_rates_from_pos(
                symbol, self._get_timeframe_from_config(), 1, bars_needed,
            )  # type: ignore
            if rates is None or len(rates) < bars_needed:
                logging.warning(f"Insufficient data to calculate DI for {symbol}")
                return 0.0, 0.0

            # Convert to DataFrame for DI calculation
            df = pd.DataFrame(rates)

            # Calculate True Range and DM
            df["high_low"] = df["high"] - df["low"]
            df["high_close"] = np.abs(df["high"] - df["close"].shift())
            df["low_close"] = np.abs(df["low"] - df["close"].shift())
            df["tr"] = df[["high_low", "high_close", "low_close"]].max(axis=1)

            # Calculate +DM and -DM
            df["up_move"] = df["high"] - df["high"].shift()
            df["down_move"] = df["low"].shift() - df["low"]

            df["plus_dm"] = np.where(
                (df["up_move"] > df["down_move"]) & (df["up_move"] > 0),
                df["up_move"],
                0,
            )
            df["minus_dm"] = np.where(
                (df["down_move"] > df["up_move"]) & (df["down_move"] > 0),
                df["down_move"],
                0,
            )

            # Smooth using Wilder's smoothing
            alpha = 1 / adx_period
            df["atr"] = df["tr"].ewm(alpha=alpha, adjust=False).mean()
            df["plus_dm_smooth"] = df["plus_dm"].ewm(alpha=alpha, adjust=False).mean()
            df["minus_dm_smooth"] = df["minus_dm"].ewm(alpha=alpha, adjust=False).mean()

            # Calculate +DI and -DI
            df["plus_di"] = 100 * (df["plus_dm_smooth"] / df["atr"])
            df["minus_di"] = 100 * (df["minus_dm_smooth"] / df["atr"])

            # Get most recent DI values
            plus_di = df["plus_di"].iloc[-1]
            minus_di = df["minus_di"].iloc[-1]

            if pd.isna(plus_di) or pd.isna(minus_di):
                logging.warning(f"DI calculation resulted in NaN for {symbol}")
                return 0.0, 0.0

            return float(plus_di), float(minus_di)

        except Exception as e:
            logging.exception(f"Error calculating DI for {symbol}: {e}")
            return 0.0, 0.0


# Global instance for easy access
market_regime_detector = MarketRegimeDetector()

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s",
    )

    # Test with a symbol (this would require MT5 to be running)
    # regime, adx, slope = market_regime_detector.detect_regime("XAUUSD")
    # print(f"Regime: {regime}, ADX: {adx:.2f}, Slope: {slope:.4f}")
    pass
