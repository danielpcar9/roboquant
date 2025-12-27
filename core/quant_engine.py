"""
Quantitative Trading Engine
==========================
Mathematical framework for statistical analysis and quantitative trading decisions
"""
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class QuantitativeAnalyzer:
    """
    Statistical analysis engine with mathematical formulas for trading decisions
    """
    
    def __init__(self):
        self.weights = {
            'momentum': [0.5, 0.3, 0.2],  # Short, medium, long term weights
            'probability': {
                'momentum': 0.2,
                'volatility': 0.15,
                'trend': 0.25,
                'adx': 0.2,
                'di_diff': 0.2
            }
        }
    
    def calculate_momentum_score(self, prices: np.ndarray, periods: List[int] = None) -> float:
        """
        Calculate momentum score using multiple timeframes with weighted average
        Formula: Weighted sum of momentum ratios across different periods
        """
        if periods is None:
            periods = [5, 10, 20]

        if len(prices) < max(periods):
            return 0.0

        momentum_scores = []
        weights = self.weights['momentum']

        for i, period in enumerate(periods):
            if len(prices) > period:
                recent_price = prices[-1]
                past_price = prices[-period-1]
                momentum = (recent_price - past_price) / past_price
                momentum_scores.append(momentum * weights[i])

        return sum(momentum_scores)
    
    def calculate_volatility_score(self, prices: np.ndarray, period: int = 20) -> float:
        """
        Calculate volatility score using rolling standard deviation
        Formula: (Current volatility - mean_volatility) / std_volatility
        """
        if len(prices) < period + 5:  # Need extra data for stability
            return 0.0
        
        returns = np.diff(np.log(prices))
        if len(returns) < period:
            return 0.0
        
        # Vectorized calculation of rolling volatility
        rolling_std = np.array([np.std(returns[i-period:i]) for i in range(period, len(returns))])
        
        if len(rolling_std) == 0:
            return 0.0
        
        current_vol = rolling_std[-1]
        mean_vol = np.mean(rolling_std)
        std_vol = np.std(rolling_std)
        
        if std_vol == 0:
            return 0.0
        
        return (current_vol - mean_vol) / std_vol
    
    def calculate_trend_strength(self, prices: np.ndarray, period: int = 20) -> float:
        """
        Calculate trend strength using linear regression slope
        Formula: Slope of regression line normalized by price level
        """
        if len(prices) < period:
            return 0.0
        
        y = prices[-period:]
        x = np.arange(len(y), dtype=np.float64)
        
        # Linear regression: y = ax + b
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
        
        # Normalize by average price to get relative strength
        avg_price = np.mean(y)
        trend_strength = slope / avg_price if avg_price != 0 else 0.0
        
        # Multiply by R² to weight by statistical significance
        return trend_strength * (r_value ** 2)
    
    def calculate_statistical_probability(
        self,
        momentum_score: float,
        volatility_score: float, 
        trend_strength: float,
        adx_value: float,
        di_plus: float,
        di_minus: float
    ) -> Dict[str, float]:
        """
        Calculate entry probability using weighted statistical model
        Formula: Combined probability = w1*momentum + w2*volatility + w3*trend + w4*adx + w5*di_diff
        """
        # Normalize scores to 0-1 range
        momentum_norm = (momentum_score + 1) / 2 if abs(momentum_score) <= 1 else 0.5
        volatility_norm = (volatility_score + 1) / 2 if abs(volatility_score) <= 1 else 0.5
        trend_norm = (trend_strength + 1) / 2 if abs(trend_strength) <= 1 else 0.5
        
        # ADX normalized (0-100 range to 0-1)
        adx_norm = min(adx_value / 100.0, 1.0)
        
        # DI difference (positive for bullish, negative for bearish)
        di_diff = di_plus - di_minus
        di_norm = di_diff / 100.0  # Normalize to -1 to 1
        
        # Weighted combination
        weights = self.weights['probability']
        
        probability = (
            weights['momentum'] * max(0, momentum_norm) +
            weights['volatility'] * max(0, volatility_norm) +
            weights['trend'] * max(0, trend_norm) +
            weights['adx'] * adx_norm +
            weights['di_diff'] * max(0, di_norm)  # Only positive DI difference
        )
        
        return {
            'probability': min(probability, 1.0),
            'components': {
                'momentum_score': momentum_norm,
                'volatility_score': volatility_norm,
                'trend_strength': trend_norm,
                'adx_normalized': adx_norm,
                'di_difference': di_norm
            },
            'weights': weights
        }

class PositionSizer:
    """
    Mathematical position sizing using quantitative formulas
    """
    
    def __init__(self):
        self.default_kelly_fraction = 0.5  # Conservative approach: use half Kelly
        self.max_kelly_percentage = 0.1    # Max 10% of account
        self.max_sharpe_percentage = 0.05  # Max 5% risk
    
    def kelly_criterion(self, win_rate: float, avg_win_ratio: float, avg_loss_ratio: float) -> float:
        """
        Kelly Criterion formula for optimal position sizing
        Formula: K = (bp - q) / b
        where b = avg_win/avg_loss, p = win_rate, q = 1 - win_rate
        """
        if avg_loss_ratio == 0:
            return 0.1  # Conservative default
        
        b = avg_win_ratio / avg_loss_ratio
        p = win_rate
        q = 1 - p
        
        kelly_fraction = (b * p - q) / b if b > 0 else 0.05  # Conservative 5%
        
        # Conservative approach: use half Kelly
        return min(kelly_fraction * self.default_kelly_fraction, self.max_kelly_percentage)  # Max 10% of account
    
    def sharpe_ratio_position_size(
        self,
        returns: np.ndarray, 
        risk_free_rate: float = 0.02,
        max_risk_pct: float = 1.0
    ) -> float:
        """
        Position size based on Sharpe ratio optimization
        Formula: Optimal size = Sharpe * volatility_adjustment
        """
        if len(returns) < 30:  # Need sufficient data
            return max_risk_pct / 100.0  # Default 1% risk
        
        mean_return = np.mean(returns)
        volatility = np.std(returns) if len(returns) > 1 else 0.01
        
        if volatility == 0:
            return max_risk_pct / 100.0
        
        sharpe = (mean_return - risk_free_rate / 252) / (volatility / np.sqrt(252))  # Annualized
        
        # Adjust position size based on Sharpe ratio
        optimal_risk_pct = max_risk_pct * (1 + min(sharpe, 2.0))  # Cap at 3x risk
        return min(optimal_risk_pct / 100.0, self.max_sharpe_percentage)  # Max 5% risk

class QuantitativeOptimizer:
    """
    Mathematical optimization for trading parameters
    """
    
    def __init__(self):
        self.default_period = 20
        self.min_period = 10
        self.max_period = 30
        self.lookback_days = 90
    
    @staticmethod
    def _generate_breakout_signals(prices: np.ndarray, period: int) -> List[float]:
        """Generate hypothetical breakout signals for optimization"""
        signals = []
        for i in range(period, len(prices)):
            high_period = max(prices[i-period:i])
            low_period = min(prices[i-period:i])
            
            current_price = prices[i]
            
            # Simulate long signal
            if current_price > high_period:
                # Simulate return over next few periods
                future_return = (prices[min(i+5, len(prices)-1)] - current_price) / current_price
                signals.append(future_return)
            elif current_price < low_period:
                # Simulate short return (negative for short positions)
                future_return = (current_price - prices[min(i+5, len(prices)-1)]) / current_price
                signals.append(future_return)
        
        return signals
    
    @staticmethod
    def _calculate_signal_sharpe(signals: List[float]) -> float:
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
        periods_range: Tuple[int, int] = None,
        lookback_days: int = None
    ) -> int:
        """
        Optimize Donchian period using statistical performance
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
                prices[-lookback_days:], period
            )
            
            if len(signals) > 5:  # Need sufficient signals
                sharpe = QuantitativeOptimizer._calculate_signal_sharpe(signals)
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_period = period
        
        return best_period

class QuantitativeEngine:
    """
    Main quantitative trading engine combining all mathematical components
    """
    
    def __init__(self):
        self.analyzer = QuantitativeAnalyzer()
        self.sizer = PositionSizer()
        self.optimizer = QuantitativeOptimizer()
        self.historical_data = {}
        
    def calculate_entry_score(
        self,
        prices: np.ndarray,
        adx_value: float,
        di_plus: float,
        di_minus: float
    ) -> Dict[str, any]:
        """
        Calculate comprehensive entry score using quantitative formulas
        """
        # Calculate individual components
        momentum = self.analyzer.calculate_momentum_score(prices)
        volatility = self.analyzer.calculate_volatility_score(prices)
        trend = self.analyzer.calculate_trend_strength(prices)
        
        # Combine into probability
        probability_result = self.analyzer.calculate_statistical_probability(
            momentum, volatility, trend, adx_value, di_plus, di_minus
        )
        
        # Additional filters using statistical thresholds
        volatility_filter = abs(volatility) < 2.0  # Not too volatile
        trend_filter = abs(trend) > 0.001  # Meaningful trend
        
        final_score = probability_result['probability']
        if not volatility_filter:
            final_score *= 0.5  # Reduce score if too volatile
        if not trend_filter:
            final_score *= 0.3  # Reduce score if no clear trend
        
        return {
            'entry_score': final_score,
            'probability': probability_result['probability'],
            'components': probability_result['components'],
            'filters': {
                'volatility_filter': volatility_filter,
                'trend_filter': trend_filter
            },
            'recommendation': 'BUY' if final_score > 0.6 else 'SELL' if final_score < 0.4 else 'HOLD'
        }
    
    def calculate_optimal_position_size(
        self,
        account_balance: float,
        entry_score: float,
        historical_returns: Optional[np.ndarray] = None
    ) -> float:
        """
        Calculate optimal position size using quantitative formulas
        """
        # Base size from entry score (higher score = larger position)
        base_size = min(entry_score * 0.1, 0.05)  # Max 5% of account
        
        if historical_returns is not None and len(historical_returns) > 20:
            # Adjust using Sharpe-based sizing
            sharpe_size = self.sizer.sharpe_ratio_position_size(historical_returns)
            kelly_size = self.sizer.kelly_criterion(
                win_rate=0.55,  # Default assumption
                avg_win_ratio=2.0,
                avg_loss_ratio=1.0
            )
            
            # Combine approaches
            combined_size = (base_size + sharpe_size + kelly_size) / 3
        else:
            combined_size = base_size
        
        # Apply account balance
        optimal_lots = (account_balance * combined_size) / 1000  # Normalize to lot size
        
        # Ensure minimum and maximum limits
        return min(max(optimal_lots, 0.01), 0.3)  # Min 0.01, Max 0.3 lots

# Example usage and testing
if __name__ == "__main__":
    # Test the quantitative engine
    engine = QuantitativeEngine()
    
    # Simulate some price data
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.normal(0, 0.1, 100))  # Random walk
    
    # Test entry score calculation
    result = engine.calculate_entry_score(
        prices=prices,
        adx_value=25.0,
        di_plus=20.0,
        di_minus=15.0
    )
    
    print("Quantitative Analysis Result:")
    print(f"Entry Score: {result['entry_score']:.3f}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Components: {result['components']}")
    
    # Test position sizing
    optimal_size = engine.calculate_optimal_position_size(
        account_balance=10000,
        entry_score=result['entry_score']
    )
    print(f"Optimal Position Size: {optimal_size:.3f} lots")