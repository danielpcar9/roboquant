"""Quantitative Trading Engine - Modular Architecture
Main engine combining statistical analysis, position sizing, and optimization
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np

from .analyzers.statistical_analyzer import QuantitativeAnalyzer
from .optimizers.param_optimizer import QuantitativeOptimizer
from .sizers.position_sizer import PositionSizer


class RiskMetrics:
    """Track and calculate risk metrics for quantitative trading"""

    def __init__(self) -> None:
        self.daily_losses: list[float] = []
        self.max_daily_loss = 0.03  # 3% maximum daily loss
        self.drawdown_limit = 0.08   # 8% maximum drawdown

    def update_daily_loss(self, loss_percent: float) -> None:
        """Update daily loss tracking"""
        self.daily_losses.append(abs(loss_percent))
        if len(self.daily_losses) > 30:  # Keep last 30 days
            self.daily_losses.pop(0)

    def get_current_drawdown(self, current_balance: float, peak_balance: float) -> float:
        """Calculate current drawdown percentage"""
        if peak_balance <= 0:
            return 0.0
        return (peak_balance - current_balance) / peak_balance


class QuantitativeEngine:
    """Main quantitative trading engine combining all mathematical components
    """

    def __init__(self) -> None:
        self.analyzer = QuantitativeAnalyzer()
        self.sizer = PositionSizer()
        self.optimizer = QuantitativeOptimizer()
        self.risk_metrics = RiskMetrics()
        self.historical_data: dict[str, Any] = {}

        # Initialize quant trades tracking
        self.quant_trades_file = Path("data/quant_trades.json")
        self.quant_trades_file.parent.mkdir(exist_ok=True)

        # Initialize the file if it doesn't exist
        if not self.quant_trades_file.exists():
            with Path(self.quant_trades_file).open("w") as f:
                json.dump([], f)

    def calculate_entry_score(
        self,
        prices: np.ndarray,
        adx_value: float,
        di_plus: float,
        di_minus: float,
        periods: list[int] | None = None,
    ) -> dict[str, Any]:
        """Calculate comprehensive entry score using all quantitative indicators
        """
        # Calculate individual components
        momentum_score = self.analyzer.calculate_momentum_score(prices, periods)
        volatility_score = self.analyzer.calculate_volatility_score(prices)
        trend_strength = self.analyzer.calculate_trend_strength(prices)

        # Calculate combined probability
        probability_result = self.analyzer.calculate_statistical_probability(
            momentum_score, volatility_score, trend_strength, adx_value, di_plus, di_minus,
        )

        # Determine recommendation based on probability
        probability = probability_result["probability"]
        if probability >= 0.75:  # Aumentado de 0.7 a 0.75 para ser más selectivo
            recommendation = "STRONG_BUY" if di_plus > di_minus else "STRONG_SELL"
        elif probability >= 0.65:  # Aumentado de 0.6 a 0.65
            recommendation = "BUY" if di_plus > di_minus else "SELL"
        elif probability >= 0.45:  # Ajustado de 0.4 a 0.45
            recommendation = "HOLD"
        else:
            recommendation = "AVOID"

        return {
            "entry_score": probability,
            "recommendation": recommendation,
            "components": probability_result["components"],
            "weights": probability_result["weights"],
            "individual_scores": {
                "momentum": momentum_score,
                "volatility": volatility_score,
                "trend": trend_strength,
            },
        }

    def calculate_optimal_position_size(
        self,
        account_balance: float,
        entry_score: float,
        historical_returns: np.ndarray | None = None,
        historical_trades: list[float] | None = None,
    ) -> float:
        """Calculate optimal position size using quantitative formulas
        """
        # Load ONLY quant trades
        quant_trades = self._load_quant_trades()

        if len(quant_trades) >= 15:  # Mínimo 15 trades quant
            kelly_size = self.sizer.kelly_criterion_from_trades(quant_trades)
        else:
            # BOOTSTRAP: modo más agresivo para mayor riesgo
            kelly_size = max(0.01, min(0.04, entry_score * 0.025))
            logging.info(
                f"⚠️ Bootstrap mode AGGRESIVO: {len(quant_trades)}/15 quant trades",
            )

        # Base size from entry score (higher score = larger position)
        base_size = min(entry_score * 0.1, 0.05)  # Max 5% of account

        if historical_trades is not None and len(historical_trades) > 10:
            # Use Kelly criterion from actual trade history
            historical_kelly = self.sizer.kelly_criterion_from_trades(historical_trades)

            # Calculate Sharpe-based sizing if returns are also provided
            if historical_returns is not None and len(historical_returns) > 20:
                sharpe_size = self.sizer.sharpe_ratio_position_size(historical_returns)
                # Combine approaches
                combined_size = (
                    base_size + sharpe_size + kelly_size + historical_kelly
                ) / 4
            else:
                # Combine base and kelly approaches
                combined_size = (base_size + kelly_size + historical_kelly) / 3
        elif historical_returns is not None and len(historical_returns) > 20:
            # Adjust using Sharpe-based sizing
            sharpe_size = self.sizer.sharpe_ratio_position_size(historical_returns)

            # Combine approaches
            combined_size = (base_size + sharpe_size + kelly_size) / 3
        else:
            # Use the quant-based kelly size as primary
            combined_size = (base_size + kelly_size) / 2

        # Apply account balance
        optimal_lots = (account_balance * combined_size) / 1000  # Normalize to lot size

        # Ensure minimum and maximum limits
        min_lots = 0.01
        max_lots = 0.5  # Reducido de 1.0 a 0.5 para menor riesgo

        final_size = max(min_lots, min(optimal_lots, max_lots))

        logging.info(
            f"📊 Position sizing - Entry Score: {entry_score:.3f}, "
            f"Base Size: {base_size:.3f}, Kelly Size: {kelly_size:.3f}, "
            f"Final Lots: {final_size:.3f}",
        )

        return final_size

    def record_trade_result(
        self, return_pct: float, entry_score: float, investment: float,
    ) -> None:
        """Record trade result for future optimization and analysis
        """
        try:
            # Load existing trades
            trades_list = self._load_quant_trades_dicts()

            # Add new trade
            new_trade = {
                "timestamp": str(Path().resolve().stat().st_mtime) if hasattr(Path(), "stat") else "unknown",
                "return": return_pct,
                "entry_score": entry_score,
                "investment": investment,
                "pnl": return_pct * investment / 100,
            }
            trades_list.append(new_trade)

            # Keep only last 200 trades for performance
            if len(trades_list) > 200:
                trades_list = trades_list[-200:]

            # Save updated trades
            with Path(self.quant_trades_file).open("w") as f:
                json.dump(trades_list, f)

            logging.info(
                f"📊 Quant trade recorded: {return_pct:.2f}%, "
                f"score: {entry_score:.3f}, total: {len(trades_list)}",
            )
        except Exception as e:
            logging.exception("Error recording trade result: %s", e)

    def _load_quant_trades_dicts(self) -> list[dict[str, Any]]:
        """Load quant trades as dictionaries from persistence file"""
        try:
            if self.quant_trades_file.exists():
                with Path(self.quant_trades_file).open("r") as f:
                    return json.load(f)
            else:
                return []
        except Exception as e:
            logging.exception("Error loading quant trades: %s", e)
            return []

    def _load_quant_trades(self) -> list[float]:
        """Load only quant trades from persistence file"""
        try:
            if self.quant_trades_file.exists():
                with Path(self.quant_trades_file).open("r") as f:
                    trades = json.load(f)
                    # Return only the returns from the trades
                    return [float(trade["return"]) for trade in trades]
            else:
                return []
        except Exception as e:
            logging.exception("Error loading quant trades: %s", e)
            return []

    def get_performance_summary(self) -> dict[str, Any]:
        """Get performance summary of quantitative trading
        """
        quant_trades = self._load_quant_trades()

        if len(quant_trades) == 0:
            return {"message": "No quant trades recorded yet"}

        # Calculate basic statistics
        returns_array = np.array(quant_trades)
        positive_trades = returns_array[returns_array > 0]
        negative_trades = returns_array[returns_array <= 0]

        summary = {
            "total_trades": len(quant_trades),
            "win_rate": len(positive_trades) / len(quant_trades) if len(quant_trades) > 0 else 0,
            "average_win": np.mean(positive_trades) if len(positive_trades) > 0 else 0,
            "average_loss": np.mean(negative_trades) if len(negative_trades) > 0 else 0,
            "total_return": np.sum(returns_array),
            "sharpe_ratio": self.sizer.sharpe_ratio_position_size(returns_array) * np.sqrt(252) if len(returns_array) > 1 else 0,
            "max_drawdown": np.min(returns_array) if len(returns_array) > 0 else 0,
            "recent_performance": np.mean(returns_array[-20:]) if len(returns_array) >= 20 else np.mean(returns_array),
        }

        return summary


# Backward compatibility
QuantitativeIntegration = QuantitativeEngine
