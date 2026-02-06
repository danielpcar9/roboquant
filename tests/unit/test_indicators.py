"""
Unit Tests for Technical Indicators Module

Tests the consolidated technical indicators implementation for accuracy
and edge case handling.
"""

import numpy as np
import pandas as pd
import pytest

from indicators import (
    TechnicalIndicators,
    calculate_adx,
    calculate_atr,
    calculate_donchian,
    calculate_rsi,
)


class TestDonchianChannels:
    """Test Donchian Channel calculations."""
    
    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLC data."""
        np.random.seed(42)
        n = 100
        
        close = 1000 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n) * 1)
        low = close - np.abs(np.random.randn(n) * 1)
        
        return pd.DataFrame({
            "open": close - np.random.randn(n) * 0.5,
            "high": high,
            "low": low,
            "close": close
        })
    
    def test_donchian_basic(self, sample_data):
        """Test basic Donchian calculation."""
        upper, lower, middle = TechnicalIndicators.calculate_donchian_channels(
            sample_data, period=20, shift=False
        )
        
        assert len(upper) == len(sample_data)
        assert len(lower) == len(sample_data)
        assert len(middle) == len(sample_data)
        
        # Upper should always be >= lower
        valid_idx = ~(upper.isna() | lower.isna())
        assert all(upper[valid_idx] >= lower[valid_idx])
    
    def test_donchian_shifted(self, sample_data):
        """Test Donchian with shift to avoid look-ahead."""
        upper_shift, lower_shift, _ = TechnicalIndicators.calculate_donchian_channels(
            sample_data, period=20, shift=True
        )
        upper_noshift, lower_noshift, _ = TechnicalIndicators.calculate_donchian_channels(
            sample_data, period=20, shift=False
        )
        
        # With shift, values should be from previous period
        # First valid index should be at position period (20) for shifted
        assert upper_shift.iloc[20] == upper_noshift.iloc[19]
    
    def test_donchian_period_effect(self, sample_data):
        """Test that larger periods produce smoother channels."""
        upper_10, lower_10, _ = TechnicalIndicators.calculate_donchian_channels(
            sample_data, period=10, shift=False
        )
        upper_30, lower_30, _ = TechnicalIndicators.calculate_donchian_channels(
            sample_data, period=30, shift=False
        )
        
        # Longer period should have wider or equal channel
        valid_idx = ~(upper_10.isna() | upper_30.isna())
        
        width_10 = (upper_10 - lower_10)[valid_idx]
        width_30 = (upper_30 - lower_30)[valid_idx]
        
        # On average, 30-period should be wider
        assert width_30.mean() >= width_10.mean() * 0.8  # Allow some tolerance
    
    def test_backward_compat_function(self, sample_data):
        """Test backward compatibility function."""
        upper, lower = calculate_donchian(sample_data, period=20)
        
        assert upper is not None
        assert lower is not None


class TestADX:
    """Test ADX and DI calculations."""
    
    @pytest.fixture
    def trending_data(self) -> pd.DataFrame:
        """Create trending market data (should have high ADX)."""
        n = 100
        # Create uptrend
        close = np.linspace(1000, 1200, n)
        high = close + np.random.uniform(1, 5, n)
        low = close - np.random.uniform(1, 5, n)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    @pytest.fixture
    def ranging_data(self) -> pd.DataFrame:
        """Create ranging market data (should have low ADX)."""
        n = 100
        # Create sideways movement
        close = 1000 + np.sin(np.linspace(0, 10, n)) * 10
        high = close + np.random.uniform(1, 3, n)
        low = close - np.random.uniform(1, 3, n)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    def test_adx_returns_dict(self, trending_data):
        """Test that ADX returns expected structure."""
        result = TechnicalIndicators.calculate_adx(trending_data, period=14)
        
        assert "adx" in result
        assert "di_plus" in result
        assert "di_minus" in result
        assert "atr" in result
    
    def test_adx_range(self, trending_data):
        """Test that ADX values are in valid range (0-100)."""
        result = TechnicalIndicators.calculate_adx(trending_data, period=14)
        
        valid_adx = result["adx"].dropna()
        assert all(valid_adx >= 0)
        assert all(valid_adx <= 100)
    
    def test_trending_vs_ranging(self, trending_data, ranging_data):
        """Test that ADX is higher for trending market."""
        trending_adx = TechnicalIndicators.calculate_adx(trending_data, period=14)
        ranging_adx = TechnicalIndicators.calculate_adx(ranging_data, period=14)
        
        # Average ADX should be higher for trending
        trend_mean = trending_adx["adx"].iloc[30:].mean()  # Skip warmup
        range_mean = ranging_adx["adx"].iloc[30:].mean()
        
        assert trend_mean > range_mean
    
    def test_di_direction(self, trending_data):
        """Test that DI+ > DI- in uptrend."""
        result = TechnicalIndicators.calculate_adx(trending_data, period=14)
        
        # In uptrend, DI+ should generally be higher
        valid_idx = ~(result["di_plus"].isna() | result["di_minus"].isna())
        di_diff = (result["di_plus"] - result["di_minus"])[valid_idx]
        
        # Most of the time, DI+ should be higher
        assert (di_diff > 0).sum() > len(di_diff) * 0.7


class TestATR:
    """Test ATR calculations."""
    
    @pytest.fixture
    def volatile_data(self) -> pd.DataFrame:
        """Create volatile market data."""
        n = 100
        np.random.seed(42)
        
        close = 1000 + np.cumsum(np.random.randn(n) * 5)
        high = close + np.abs(np.random.randn(n) * 10)
        low = close - np.abs(np.random.randn(n) * 10)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    @pytest.fixture
    def calm_data(self) -> pd.DataFrame:
        """Create low volatility data."""
        n = 100
        np.random.seed(42)
        
        close = 1000 + np.cumsum(np.random.randn(n) * 0.5)
        high = close + np.abs(np.random.randn(n) * 1)
        low = close - np.abs(np.random.randn(n) * 1)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    def test_atr_positive(self, volatile_data):
        """Test that ATR is always positive."""
        atr = TechnicalIndicators.calculate_atr(volatile_data, period=14)
        
        valid_atr = atr.dropna()
        assert all(valid_atr > 0)
    
    def test_atr_volatility_relationship(self, volatile_data, calm_data):
        """Test that ATR is higher for volatile data."""
        atr_volatile = TechnicalIndicators.calculate_atr(volatile_data, period=14)
        atr_calm = TechnicalIndicators.calculate_atr(calm_data, period=14)
        
        # Volatile market should have higher ATR
        assert atr_volatile.iloc[-1] > atr_calm.iloc[-1]
    
    def test_ema_vs_sma(self, volatile_data):
        """Test EMA vs SMA calculation methods."""
        atr_ema = TechnicalIndicators.calculate_atr(volatile_data, period=14, use_ema=True)
        atr_sma = TechnicalIndicators.calculate_atr(volatile_data, period=14, use_ema=False)
        
        # Both should be similar in magnitude
        assert abs(atr_ema.iloc[-1] - atr_sma.iloc[-1]) < atr_ema.iloc[-1] * 0.2


class TestRSI:
    """Test RSI calculations."""
    
    @pytest.fixture
    def overbought_data(self) -> pd.Series:
        """Create price series that should be overbought."""
        # Strong upward movement with small variations for RSI calculation
        np.random.seed(42)
        base = np.linspace(100, 200, 100)
        # Add small random variations (mostly positive for uptrend)
        noise = np.abs(np.random.randn(100)) * 2
        return pd.Series(base + noise)
    
    @pytest.fixture
    def oversold_data(self) -> pd.Series:
        """Create price series that should be oversold."""
        # Strong downward movement with small variations
        np.random.seed(42)
        base = np.linspace(200, 100, 100)
        # Add small random variations (mostly negative for downtrend)
        noise = -np.abs(np.random.randn(100)) * 2
        return pd.Series(base + noise)
    
    @pytest.fixture
    def neutral_data(self) -> pd.Series:
        """Create price series that should be neutral."""
        np.random.seed(42)
        # Random walk around same level
        return pd.Series(100 + np.cumsum(np.random.randn(100) * 0.5))
    
    def test_rsi_range(self, neutral_data):
        """Test that RSI is between 0 and 100."""
        rsi = TechnicalIndicators.calculate_rsi(neutral_data, period=14)
        
        valid_rsi = rsi.dropna()
        assert all(valid_rsi >= 0)
        assert all(valid_rsi <= 100)
    
    def test_overbought_condition(self, overbought_data):
        """Test that strong uptrend produces high RSI."""
        rsi = TechnicalIndicators.calculate_rsi(overbought_data, period=14)
        
        # Last valid RSI should be in overbought zone (>70)
        valid_rsi = rsi.dropna()
        assert len(valid_rsi) > 0, "RSI should have valid values"
        assert valid_rsi.iloc[-1] > 70
    
    def test_oversold_condition(self, oversold_data):
        """Test that strong downtrend produces low RSI."""
        rsi = TechnicalIndicators.calculate_rsi(oversold_data, period=14)
        
        # Last RSI should be in oversold zone (<30)
        assert rsi.iloc[-1] < 30


class TestMACD:
    """Test MACD calculations."""
    
    @pytest.fixture
    def sample_prices(self) -> pd.Series:
        """Create sample price series."""
        np.random.seed(42)
        return pd.Series(100 + np.cumsum(np.random.randn(100) * 2))
    
    def test_macd_structure(self, sample_prices):
        """Test MACD returns expected structure."""
        result = TechnicalIndicators.calculate_macd(sample_prices)
        
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
    
    def test_histogram_calculation(self, sample_prices):
        """Test that histogram = MACD - Signal."""
        result = TechnicalIndicators.calculate_macd(sample_prices)
        
        calculated_histogram = result["macd"] - result["signal"]
        
        # Allow for floating point differences
        diff = abs(calculated_histogram - result["histogram"]).max()
        assert diff < 1e-10


class TestBollingerBands:
    """Test Bollinger Bands calculations."""
    
    @pytest.fixture
    def sample_prices(self) -> pd.Series:
        """Create sample price series."""
        np.random.seed(42)
        return pd.Series(100 + np.cumsum(np.random.randn(100) * 2))
    
    def test_band_structure(self, sample_prices):
        """Test Bollinger Bands returns expected structure."""
        result = TechnicalIndicators.calculate_bollinger_bands(sample_prices)
        
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert "width" in result
    
    def test_band_ordering(self, sample_prices):
        """Test that upper > middle > lower."""
        result = TechnicalIndicators.calculate_bollinger_bands(sample_prices)
        
        valid_idx = ~(result["upper"].isna() | result["lower"].isna())
        
        assert all(result["upper"][valid_idx] >= result["middle"][valid_idx])
        assert all(result["middle"][valid_idx] >= result["lower"][valid_idx])


class TestMarketRegime:
    """Test market regime detection."""
    
    @pytest.fixture
    def trending_data(self) -> pd.DataFrame:
        """Create trending market data."""
        n = 100
        close = np.linspace(1000, 1200, n)
        high = close + np.random.uniform(1, 5, n)
        low = close - np.random.uniform(1, 5, n)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    def test_regime_values(self, trending_data):
        """Test that regime returns expected values."""
        regime = TechnicalIndicators.detect_market_regime(trending_data)
        
        # Should contain only valid regime labels
        valid_regimes = {"TRENDING", "RANGING", "UNCERTAIN"}
        assert set(regime.unique()).issubset(valid_regimes)


class TestDynamicStops:
    """Test dynamic stop loss/take profit calculations."""
    
    @pytest.fixture
    def sample_data(self) -> pd.DataFrame:
        """Create sample OHLC data."""
        np.random.seed(42)
        n = 50
        
        close = 1000 + np.cumsum(np.random.randn(n) * 2)
        high = close + np.abs(np.random.randn(n) * 3)
        low = close - np.abs(np.random.randn(n) * 3)
        
        return pd.DataFrame({
            "high": high,
            "low": low,
            "close": close
        })
    
    def test_buy_stop_direction(self, sample_data):
        """Test that BUY stops are in correct direction."""
        entry = sample_data["close"].iloc[-1]
        sl, tp = TechnicalIndicators.calculate_dynamic_stops(
            sample_data, entry, "BUY", 
            atr_sl_multiplier=2.0, 
            atr_tp_multiplier=4.0
        )
        
        # For BUY: SL < entry < TP
        assert sl < entry
        assert tp > entry
    
    def test_sell_stop_direction(self, sample_data):
        """Test that SELL stops are in correct direction."""
        entry = sample_data["close"].iloc[-1]
        sl, tp = TechnicalIndicators.calculate_dynamic_stops(
            sample_data, entry, "SELL",
            atr_sl_multiplier=2.0,
            atr_tp_multiplier=4.0
        )
        
        # For SELL: SL > entry > TP
        assert sl > entry
        assert tp < entry
    
    def test_risk_reward_ratio(self, sample_data):
        """Test that TP distance is greater than SL distance."""
        entry = sample_data["close"].iloc[-1]
        sl, tp = TechnicalIndicators.calculate_dynamic_stops(
            sample_data, entry, "BUY",
            atr_sl_multiplier=2.0,
            atr_tp_multiplier=4.0
        )
        
        sl_distance = abs(entry - sl)
        tp_distance = abs(tp - entry)
        
        # TP should be 2x SL (4.0 / 2.0 = 2)
        expected_ratio = 4.0 / 2.0
        actual_ratio = tp_distance / sl_distance
        
        assert abs(actual_ratio - expected_ratio) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
