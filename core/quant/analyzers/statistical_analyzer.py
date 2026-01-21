"""Statistical Analysis Engine
Mathematical framework for quantitative trading decisions
"""

from typing import Any

import numpy as np
from scipy import stats


class QuantitativeAnalyzer:
    """Statistical analysis engine with mathematical formulas for trading decisions
    """

    def __init__(self) -> None:
        self.weights: dict[str, Any] = {
            "momentum": [0.5, 0.3, 0.2],  # Short, medium, long term weights
            "probability": {
                "momentum": 0.2,
                "volatility": 0.15,
                "trend": 0.25,
                "adx": 0.2,
                "di_diff": 0.2,
            },
        }

    def calculate_momentum_score(
        self, prices: np.ndarray, periods: list[int] | None = None,
    ) -> float:
        """Calculate momentum score using multiple timeframes with weighted average
        Formula: Weighted sum of momentum ratios across different periods
        """
        if periods is None:
            periods = [5, 10, 20]

        if len(prices) < max(periods):
            return 0.0

        momentum_scores = []
        weights = self.weights["momentum"]

        for i, period in enumerate(periods):
            if len(prices) > period:
                recent_price = prices[-1]
                past_price = prices[-period - 1]
                momentum = (recent_price - past_price) / past_price
                momentum_scores.append(momentum * weights[i])

        return sum(momentum_scores)

    def calculate_volatility_score(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate volatility score using rolling standard deviation
        Formula: (Current volatility - mean_volatility) / std_volatility
        """
        if len(prices) < period + 5:  # Need extra data for stability
            return 0.0

        returns = np.diff(np.log(prices))
        if len(returns) < period:
            return 0.0

        # Vectorized calculation of rolling volatility
        rolling_std = np.array(
            [np.std(returns[i - period : i]) for i in range(period, len(returns))],
        )

        if len(rolling_std) == 0:
            return 0.0

        current_vol = rolling_std[-1]
        mean_vol = np.mean(rolling_std)
        std_vol = np.std(rolling_std)

        if std_vol == 0:
            return 0.0

        return (current_vol - mean_vol) / std_vol

    def calculate_trend_strength(self, prices: np.ndarray, period: int = 20) -> float:
        """Calculate trend strength using linear regression slope
        Formula: Slope of regression line normalized by price level
        """
        if len(prices) < period:
            return 0.0

        y = prices[-period:]
        x = np.arange(len(y), dtype=np.float64)

        # Linear regression: y = ax + b
        result = stats.linregress(x, y)
        slope: float = float(result.slope)
        r_value: float = float(result.rvalue)

        # Normalize by average price to get relative strength
        avg_price = np.mean(y)
        trend_strength = slope / avg_price if avg_price != 0 else 0.0

        # Multiply by R² to weight by statistical significance
        return trend_strength * (r_value**2)

    def calculate_statistical_probability(
        self,
        momentum_score: float,
        volatility_score: float,
        trend_strength: float,
        adx_value: float,
        di_plus: float,
        di_minus: float,
    ) -> dict[str, float | dict[str, float]]:
        """Calculate entry probability using weighted statistical model
        Formula: Combined probability = w1*momentum + w2*volatility + w3*trend + w4*adx + w5*di_diff
        """
        # Normalize scores to 0-1 range
        momentum_norm = (momentum_score + 1) / 2 if abs(momentum_score) <= 1 else 0.5
        volatility_norm = (
            (volatility_score + 1) / 2 if abs(volatility_score) <= 1 else 0.5
        )
        trend_norm = (trend_strength + 1) / 2 if abs(trend_strength) <= 1 else 0.5

        # ADX normalized (0-100 range to 0-1)
        adx_norm = min(adx_value / 100.0, 1.0)

        # DI difference (positive for bullish, negative for bearish)
        di_diff = di_plus - di_minus
        di_norm = di_diff / 100.0  # Normalize to -1 to 1

        # Weighted combination
        weights = self.weights["probability"]

        probability = (
            weights["momentum"] * max(0, momentum_norm)
            + weights["volatility"] * max(0, volatility_norm)
            + weights["trend"] * max(0, trend_norm)
            + weights["adx"] * adx_norm
            + weights["di_diff"] * max(0, di_norm)  # Only positive DI difference
        )

        return {
            "probability": min(probability, 1.0),
            "components": {
                "momentum_score": momentum_norm,
                "volatility_score": volatility_norm,
                "trend_strength": trend_norm,
                "adx_normalized": adx_norm,
                "di_difference": di_norm,
            },
            "weights": weights,
        }


# Utility functions for statistical calculations
def calculate_hurst_exponent(prices: np.ndarray, max_lags: int = 20) -> float:
    """Calculate Hurst exponent for mean reversion analysis
    """
    lags = range(2, min(max_lags, len(prices) // 2))
    tau = [np.std(np.subtract(prices[lag:], prices[:-lag])) for lag in lags]

    # Avoid log(0) errors
    valid_indices = [i for i, t in enumerate(tau) if t > 0 and lags[i] > 0]
    if not valid_indices:
        return 0.5  # Default to random walk

    log_tau = [np.log(tau[i]) for i in valid_indices]
    log_lags = [np.log(lags[i]) for i in valid_indices]

    if len(log_tau) < 2:
        return 0.5

    # Linear regression to find Hurst exponent
    result = stats.linregress(log_lags, log_tau)
    slope: float = float(result.slope)
    hurst = slope / 2.0

    return max(0.0, min(1.0, hurst))  # Clamp to [0,1]


def calculate_sharpe_ratio(returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
    """Calculate Sharpe ratio for risk-adjusted returns
    """
    if len(returns) < 2:
        return 0.0

    excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
    mean_excess = np.mean(excess_returns)
    std_dev = np.std(returns)

    if std_dev == 0:
        return 0.0

    return mean_excess / std_dev
