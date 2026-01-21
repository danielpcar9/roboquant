"""Mathematical Position Sizing Engine
Implements quantitative formulas for optimal position sizing
"""


import numpy as np


class PositionSizer:
    """Mathematical position sizing using quantitative formulas
    """

    def __init__(self):
        self.default_kelly_fraction = 0.5  # Conservative approach: use half Kelly
        self.max_kelly_percentage = 0.1  # Max 10% of account
        self.max_sharpe_percentage = 0.05  # Max 5% risk

    def kelly_criterion(
        self, win_rate: float, avg_win_ratio: float, avg_loss_ratio: float,
    ) -> float:
        """Kelly Criterion formula for optimal position sizing
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
        return min(
            kelly_fraction * self.default_kelly_fraction, self.max_kelly_percentage,
        )  # Max 10% of account

    def kelly_criterion_from_trades(self, trade_returns: list[float]) -> float:
        """Calculate Kelly Criterion from historical trade returns
        """
        if len(trade_returns) < 10:  # Need sufficient data
            # Default to conservative approach
            return self.kelly_criterion(0.55, 2.0, 1.0)

        # Calculate win rate
        wins = [r for r in trade_returns if r > 0]
        win_rate = len(wins) / len(trade_returns)

        # Calculate average win and loss
        win_returns = [r for r in wins if r > 0]
        loss_returns = [r for r in trade_returns if r <= 0]

        if len(win_returns) == 0:
            avg_win = 0.0
        else:
            avg_win = sum(win_returns) / len(win_returns)

        if len(loss_returns) == 0:
            avg_loss = 0.0
        else:
            avg_loss = abs(sum(loss_returns) / len(loss_returns))  # Use absolute value

        # Calculate ratios
        if avg_loss == 0:
            avg_win_ratio = 2.0  # Default ratio
            avg_loss_ratio = 1.0
        else:
            avg_win_ratio = avg_win
            avg_loss_ratio = avg_loss

        return self.kelly_criterion(win_rate, avg_win_ratio, avg_loss_ratio)

    def sharpe_ratio_position_size(
        self,
        returns: np.ndarray,
        risk_free_rate: float = 0.02,
        max_risk_pct: float = 1.0,
    ) -> float:
        """Position size based on Sharpe ratio optimization
        Formula: Optimal size = Sharpe * volatility_adjustment
        """
        if len(returns) < 30:  # Need sufficient data
            return max_risk_pct / 100.0  # Default 1% risk

        mean_return = np.mean(returns)
        volatility = np.std(returns) if len(returns) > 1 else 0.01

        if volatility == 0:
            return max_risk_pct / 100.0

        sharpe = (mean_return - risk_free_rate / 252) / (
            volatility / np.sqrt(252)
        )  # Annualized

        # Adjust position size based on Sharpe ratio
        optimal_risk_pct = max_risk_pct * (1 + min(sharpe, 2.0))  # Cap at 3x risk
        return min(optimal_risk_pct / 100.0, self.max_sharpe_percentage)  # Max 5% risk

    def calculate_optimal_position_size(
        self,
        account_balance: float,
        entry_score: float,
        historical_returns: np.ndarray | None = None,
        historical_trades: list[float] | None = None,
    ) -> float:
        """Calculate optimal position size using quantitative formulas
        """
        # Base size from entry score (higher score = larger position)
        base_size = min(entry_score * 0.1, 0.05)  # Max 5% of account

        if historical_trades is not None and len(historical_trades) > 10:
            # Use Kelly criterion from actual trade history
            historical_kelly = self.kelly_criterion_from_trades(historical_trades)

            # Calculate Sharpe-based sizing if returns are also provided
            if historical_returns is not None and len(historical_returns) > 20:
                sharpe_size = self.sharpe_ratio_position_size(historical_returns)
                # Combine approaches
                combined_size = (
                    base_size + sharpe_size + historical_kelly
                ) / 3
            else:
                # Combine base and kelly approaches
                combined_size = (base_size + historical_kelly) / 2
        elif historical_returns is not None and len(historical_returns) > 20:
            # Adjust using Sharpe-based sizing
            sharpe_size = self.sharpe_ratio_position_size(historical_returns)
            # Combine approaches
            combined_size = (base_size + sharpe_size) / 2
        else:
            # Use base size only
            combined_size = base_size

        # Apply account balance
        optimal_lots = (account_balance * combined_size) / 1000  # Normalize to lot size

        # Ensure minimum and maximum limits
        min_lots = 0.01
        max_lots = 1.0  # Conservative maximum

        return max(min_lots, min(optimal_lots, max_lots))


# Utility functions for risk calculations
def calculate_value_at_risk(returns: np.ndarray, confidence_level: float = 0.95) -> float:
    """Calculate Value at Risk (VaR) for risk management
    """
    if len(returns) < 10:
        return 0.0

    # Sort returns
    sorted_returns = np.sort(returns)

    # Calculate VaR at specified confidence level
    var_index = int((1 - confidence_level) * len(sorted_returns))
    return abs(sorted_returns[var_index])


def calculate_expected_shortfall(returns: np.ndarray, confidence_level: float = 0.95) -> float:
    """Calculate Expected Shortfall (Conditional VaR) for risk management
    """
    if len(returns) < 10:
        return 0.0

    # Sort returns
    sorted_returns = np.sort(returns)

    # Calculate ES at specified confidence level
    var_index = int((1 - confidence_level) * len(sorted_returns))
    tail_losses = sorted_returns[:var_index]

    if len(tail_losses) == 0:
        return 0.0

    return abs(np.mean(tail_losses))
