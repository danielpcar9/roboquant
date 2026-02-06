"""
Consolidated Technical Indicators Module

This module provides a single, authoritative implementation of all technical
indicators used throughout the RoboQuant project. This eliminates code duplication
and ensures consistent calculations across backtesting and live trading.

Author: RoboQuant Team
Date: 2026-02-05
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class TechnicalIndicators:
    """
    Centralized technical indicator calculations.
    
    All indicator functions are implemented as class methods for easy testing
    and consistent behavior across the project.
    """
    
    # =========================================================================
    # TREND INDICATORS
    # =========================================================================
    
    @staticmethod
    def calculate_donchian_channels(
        df: pd.DataFrame, 
        period: int = 20,
        shift: bool = True
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculate Donchian Channels.
        
        Args:
            df: DataFrame with 'high' and 'low' columns
            period: Lookback period for channels
            shift: If True, shift by 1 to avoid look-ahead bias
            
        Returns:
            Tuple of (upper_channel, lower_channel, middle_channel)
        """
        upper = df["high"].rolling(window=period).max()
        lower = df["low"].rolling(window=period).min()
        middle = (upper + lower) / 2
        
        if shift:
            upper = upper.shift(1)
            lower = lower.shift(1)
            middle = middle.shift(1)
            
        return upper, lower, middle
    
    @staticmethod
    def calculate_adx(
        df: pd.DataFrame, 
        period: int = 14
    ) -> dict[str, pd.Series]:
        """
        Calculate Average Directional Index (ADX) with DI+ and DI-.
        
        Uses Wilder's smoothing method for accurate ADX calculation.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ADX period (typically 14)
            
        Returns:
            Dictionary with 'adx', 'di_plus', 'di_minus' Series
        """
        # Calculate True Range
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate Directional Movement
        up_move = df["high"] - df["high"].shift()
        down_move = df["low"].shift() - df["low"]
        
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
        
        # Wilder's smoothing (alpha = 1/period)
        alpha = 1 / period
        
        atr = tr.ewm(alpha=alpha, adjust=False).mean()
        plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
        
        # Calculate Directional Indicators
        plus_di = 100 * (plus_dm_smooth / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm_smooth / atr.replace(0, np.nan))
        
        # Calculate DX and ADX
        di_sum = plus_di + minus_di
        dx = 100 * np.abs(plus_di - minus_di) / di_sum.replace(0, np.nan)
        adx = dx.ewm(alpha=alpha, adjust=False).mean()
        
        return {
            "adx": adx,
            "di_plus": plus_di,
            "di_minus": minus_di,
            "atr": atr  # Also return ATR as it's calculated anyway
        }
    
    @staticmethod
    def calculate_atr(
        df: pd.DataFrame, 
        period: int = 14,
        use_ema: bool = True
    ) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ATR period
            use_ema: If True, use EMA; if False, use SMA
            
        Returns:
            ATR Series
        """
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        if use_ema:
            atr = tr.ewm(span=period, adjust=False).mean()
        else:
            atr = tr.rolling(window=period).mean()
            
        return atr
    
    # =========================================================================
    # MOMENTUM INDICATORS
    # =========================================================================
    
    @staticmethod
    def calculate_rsi(
        prices: pd.Series, 
        period: int = 14
    ) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            prices: Price series (typically close prices)
            period: RSI period
            
        Returns:
            RSI Series (0-100)
        """
        delta = prices.diff()
        
        gain = delta.where(delta > 0, 0)
        loss = (-delta.where(delta < 0, 0))
        
        # Use Wilder's smoothing
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_macd(
        prices: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> dict[str, pd.Series]:
        """
        Calculate MACD indicator.
        
        Args:
            prices: Price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            
        Returns:
            Dictionary with 'macd', 'signal', 'histogram' Series
        """
        ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
        ema_slow = prices.ewm(span=slow_period, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
    
    @staticmethod
    def calculate_momentum(
        prices: pd.Series, 
        period: int = 10
    ) -> pd.Series:
        """
        Calculate price momentum.
        
        Args:
            prices: Price series
            period: Momentum period
            
        Returns:
            Momentum Series
        """
        return prices - prices.shift(period)
    
    @staticmethod
    def calculate_roc(
        prices: pd.Series, 
        period: int = 10
    ) -> pd.Series:
        """
        Calculate Rate of Change (ROC).
        
        Args:
            prices: Price series
            period: ROC period
            
        Returns:
            ROC Series (percentage)
        """
        return ((prices - prices.shift(period)) / prices.shift(period)) * 100
    
    # =========================================================================
    # VOLATILITY INDICATORS
    # =========================================================================
    
    @staticmethod
    def calculate_bollinger_bands(
        prices: pd.Series,
        period: int = 20,
        std_dev: float = 2.0
    ) -> dict[str, pd.Series]:
        """
        Calculate Bollinger Bands.
        
        Args:
            prices: Price series
            period: Moving average period
            std_dev: Standard deviation multiplier
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower', 'width' Series
        """
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        width = (upper - lower) / middle  # Bandwidth
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "width": width
        }
    
    @staticmethod
    def calculate_keltner_channels(
        df: pd.DataFrame,
        ema_period: int = 20,
        atr_period: int = 10,
        atr_multiplier: float = 2.0
    ) -> dict[str, pd.Series]:
        """
        Calculate Keltner Channels.
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            ema_period: EMA period for middle line
            atr_period: ATR period
            atr_multiplier: ATR multiplier for bands
            
        Returns:
            Dictionary with 'upper', 'middle', 'lower' Series
        """
        middle = df["close"].ewm(span=ema_period, adjust=False).mean()
        atr = TechnicalIndicators.calculate_atr(df, atr_period)
        
        upper = middle + (atr * atr_multiplier)
        lower = middle - (atr * atr_multiplier)
        
        return {
            "upper": upper,
            "middle": middle,
            "lower": lower
        }
    
    # =========================================================================
    # VOLUME INDICATORS
    # =========================================================================
    
    @staticmethod
    def calculate_volume_sma(
        volume: pd.Series, 
        period: int = 20
    ) -> pd.Series:
        """Calculate volume simple moving average."""
        return volume.rolling(window=period).mean()
    
    @staticmethod
    def calculate_volume_ratio(
        volume: pd.Series, 
        period: int = 20
    ) -> pd.Series:
        """Calculate volume ratio (current / average)."""
        avg_volume = volume.rolling(window=period).mean()
        return volume / avg_volume.replace(0, np.nan)
    
    # =========================================================================
    # HELPER FUNCTIONS
    # =========================================================================
    
    @staticmethod
    def detect_market_regime(
        df: pd.DataFrame,
        adx_threshold: float = 25.0,
        di_threshold: float = 20.0
    ) -> pd.Series:
        """
        Detect market regime (TRENDING, RANGING, UNCERTAIN).
        
        Args:
            df: DataFrame with price data
            adx_threshold: ADX threshold for trend detection
            di_threshold: DI threshold for directional movement
            
        Returns:
            Series with regime labels
        """
        adx_data = TechnicalIndicators.calculate_adx(df)
        adx = adx_data["adx"]
        di_plus = adx_data["di_plus"]
        di_minus = adx_data["di_minus"]
        
        # Calculate DI strength
        di_strength = np.maximum(di_plus, di_minus)
        
        # Determine regime
        regime = pd.Series("UNCERTAIN", index=df.index)
        regime[(adx > adx_threshold) & (di_strength > di_threshold)] = "TRENDING"
        regime[(adx <= adx_threshold)] = "RANGING"
        
        return regime
    
    @staticmethod
    def calculate_dynamic_stops(
        df: pd.DataFrame,
        entry_price: float,
        direction: str,
        atr_sl_multiplier: float = 2.0,
        atr_tp_multiplier: float = 4.0,
        atr_period: int = 14
    ) -> tuple[float, float]:
        """
        Calculate dynamic SL/TP based on ATR.
        
        Args:
            df: DataFrame with price data
            entry_price: Entry price
            direction: 'BUY' or 'SELL'
            atr_sl_multiplier: ATR multiplier for stop loss
            atr_tp_multiplier: ATR multiplier for take profit
            atr_period: ATR period
            
        Returns:
            Tuple of (stop_loss, take_profit)
        """
        atr = TechnicalIndicators.calculate_atr(df, atr_period)
        current_atr = atr.iloc[-1]
        
        sl_distance = current_atr * atr_sl_multiplier
        tp_distance = current_atr * atr_tp_multiplier
        
        if direction == "BUY":
            stop_loss = entry_price - sl_distance
            take_profit = entry_price + tp_distance
        else:  # SELL
            stop_loss = entry_price + sl_distance
            take_profit = entry_price - tp_distance
            
        return stop_loss, take_profit


# ============================================================================
# CONVENIENCE FUNCTIONS (for backward compatibility)
# ============================================================================

def calculate_donchian(df: pd.DataFrame, period: int = 20) -> tuple[pd.Series, pd.Series]:
    """Backward-compatible Donchian calculation."""
    upper, lower, _ = TechnicalIndicators.calculate_donchian_channels(df, period)
    return upper, lower


def calculate_adx(df: pd.DataFrame, period: int = 14) -> dict[str, Any]:
    """Backward-compatible ADX calculation."""
    return TechnicalIndicators.calculate_adx(df, period)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Backward-compatible ATR calculation."""
    return TechnicalIndicators.calculate_atr(df, period)


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Backward-compatible RSI calculation."""
    return TechnicalIndicators.calculate_rsi(prices, period)
