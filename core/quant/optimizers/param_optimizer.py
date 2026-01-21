"""Mathematical Parameter Optimization Engine
Optimizes trading parameters using quantitative methods
"""


import numpy as np


class QuantitativeOptimizer:
    """Mathematical optimization for trading parameters
    """

    def __init__(self):
        self.default_period = 20
        self.min_period = 10
        self.max_period = 30
        self.lookback_days = 90

    @staticmethod
    def _generate_breakout_signals(prices: np.ndarray, period: int) -> list[float]:
        """Generate hypothetical breakout signals for optimization"""
        signals = []
        for i in range(period, len(prices)):
            high_period = max(prices[i - period : i])
            low_period = min(prices[i - period : i])

            current_price = prices[i]

            # Simulate long signal
            if current_price > high_period:
                # Simulate return over next few periods
                future_return = (
                    prices[min(i + 5, len(prices) - 1)] - current_price
                ) / current_price
                signals.append(future_return)
            elif current_price < low_period:
                # Simulate short return (negative for short positions)
                future_return = (
                    current_price - prices[min(i + 5, len(prices) - 1)]
                ) / current_price
                signals.append(future_return)

        return signals

    @staticmethod
    def _calculate_signal_sharpe(signals: list[float]) -> float:
        """Calculate Sharpe ratio of signals"""
        if len(signals) < 2:
            return 0.0

        returns = np.array(signals)
        mean_return = np.mean(returns)
        std_return = np.std(returns)

        return mean_return / std_return if std_return != 0 else 0.0

    def optimize_donchian_period(
        self,
        prices: np.ndarray,
        periods_range: tuple[int, int] | None = None,
        lookback_days: int | None = None,
    ) -> int:
        """Optimize Donchian period using statistical performance
        Formula: Find period that maximizes Sharpe ratio of breakout signals
        """
        if periods_range is None:
            periods_range = (self.min_period, self.max_period)
        if lookback_days is None:
            lookback_days = self.lookback_days

        if len(prices) < max(periods_range) + lookback_days:
            return self.default_period  # Default if insufficient data

        best_period = self.default_period
        best_sharpe = -np.inf

        for period in range(periods_range[0], periods_range[1] + 1):
            # Generate hypothetical signals for this period
            signals = QuantitativeOptimizer._generate_breakout_signals(
                prices[-lookback_days:], period,
            )

            if len(signals) > 5:  # Need sufficient signals
                sharpe = QuantitativeOptimizer._calculate_signal_sharpe(signals)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_period = period

        return best_period

    def optimize_risk_parameters(
        self,
        historical_returns: np.ndarray,
        target_win_rate: float = 0.55,
    ) -> dict[str, float]:
        """Optimize risk parameters based on historical performance
        """
        if len(historical_returns) < 20:
            return {
                "optimal_risk_percent": 2.0,
                "optimal_kelly_fraction": 0.5,
                "confidence": "low",
            }

        # Calculate basic statistics
        positive_returns = historical_returns[historical_returns > 0]
        negative_returns = historical_returns[historical_returns <= 0]

        win_rate = len(positive_returns) / len(historical_returns)
        avg_win = np.mean(positive_returns) if len(positive_returns) > 0 else 0.0
        avg_loss = abs(np.mean(negative_returns)) if len(negative_returns) > 0 else 1.0

        # Adjust risk based on performance
        if win_rate >= target_win_rate and avg_win > avg_loss:
            # Good performance - can increase risk slightly
            risk_multiplier = 1.2
            confidence = "high"
        elif win_rate < target_win_rate * 0.8:
            # Poor performance - reduce risk
            risk_multiplier = 0.7
            confidence = "low"
        else:
            # Moderate performance - maintain current risk
            risk_multiplier = 1.0
            confidence = "medium"

        optimal_risk = min(2.0 * risk_multiplier, 3.0)  # Cap at 3%
        kelly_fraction = min(0.5 * risk_multiplier, 0.7)  # Cap at 70%

        return {
            "optimal_risk_percent": round(optimal_risk, 2),
            "optimal_kelly_fraction": round(kelly_fraction, 2),
            "current_win_rate": round(win_rate, 3),
            "average_win": round(avg_win, 4),
            "average_loss": round(avg_loss, 4),
            "confidence": confidence,
        }

    def optimize_position_sizing_formula(
        self,
        trade_history: list[dict],
        market_conditions: str = "normal",
    ) -> dict[str, float]:
        """Optimize position sizing formula based on recent performance
        """
        if len(trade_history) < 15:
            return {
                "formula_weights": {"kelly": 0.4, "sharpe": 0.3, "fixed": 0.3},
                "minimum_trades": 15,
            }

        # Extract returns from trade history
        returns = [trade["pnl"] / trade["investment"] for trade in trade_history]

        # Calculate performance metrics
        sharpe = self._calculate_signal_sharpe(returns)
        win_rate = len([r for r in returns if r > 0]) / len(returns)

        # Market condition adjustments
        condition_multipliers = {
            "volatile": 0.8,
            "normal": 1.0,
            "stable": 1.2,
        }
        multiplier = condition_multipliers.get(market_conditions, 1.0)

        # Adjust formula weights based on performance
        if sharpe > 1.0 and win_rate > 0.6:
            # Strong performance - favor Kelly criterion
            weights = {"kelly": 0.6, "sharpe": 0.3, "fixed": 0.1}
        elif sharpe < 0.5 or win_rate < 0.4:
            # Weak performance - favor fixed sizing
            weights = {"kelly": 0.2, "sharpe": 0.2, "fixed": 0.6}
        else:
            # Balanced performance - mixed approach
            weights = {"kelly": 0.4, "sharpe": 0.4, "fixed": 0.2}

        # Apply market condition multiplier
        for key in weights:
            weights[key] *= multiplier
            weights[key] = round(weights[key], 2)

        # Ensure weights sum to 1.0
        total = sum(weights.values())
        if total > 0:
            for key in weights:
                weights[key] /= total

        return {
            "formula_weights": weights,
            "recent_sharpe": round(sharpe, 3),
            "recent_win_rate": round(win_rate, 3),
            "market_condition": market_conditions,
            "total_trades_analyzed": len(trade_history),
        }


# Utility functions for parameter optimization
def calculate_optimal_stop_loss(prices: np.ndarray, atr_multiplier: float = 2.0) -> float:
    """Calculate optimal stop loss distance based on ATR
    """
    if len(prices) < 15:
        return 0.0

    # Calculate ATR-like measure
    high_low = np.max(prices) - np.min(prices)
    close_open = abs(prices[-1] - prices[0])

    # Simple ATR approximation
    atr_approx = (high_low + close_open) / 2

    return atr_approx * atr_multiplier


def optimize_take_profit_ratio(
    win_rate: float,
    avg_win: float,
    avg_loss: float,
) -> float:
    """Optimize take profit ratio based on win rate and payout ratio
    """
    if avg_loss == 0:
        return 2.0  # Default 2:1 ratio

    current_ratio = avg_win / avg_loss

    # Adjust based on win rate
    if win_rate > 0.6:
        # High win rate - can afford lower ratio
        optimal_ratio = max(1.5, current_ratio * 0.9)
    elif win_rate < 0.4:
        # Low win rate - need higher ratio
        optimal_ratio = min(4.0, current_ratio * 1.2)
    else:
        # Medium win rate - maintain current ratio
        optimal_ratio = current_ratio

    return round(optimal_ratio, 2)
