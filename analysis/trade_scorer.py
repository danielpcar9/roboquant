import logging
from datetime import UTC, datetime
from typing import Any

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5


class TradeScorer:
    """Trade setup quality scorer with 0-100 point system"""

    def __init__(self, mt5_module=None):
        self.mt5 = mt5_module or mt5

    def score_trade_setup(
        self,
        symbol: str,
        price: float,
        upper_channel: float,
        lower_channel: float,
        current_momentum: float,
        historical_momentum: float,
        atr: float | None = None,
        avg_atr: float | None = None,
    ) -> dict[str, Any]:
        """
        Score a trade setup based on multiple heuristics

        Args:
            symbol: Trading symbol
            price: Current price
            upper_channel: Donchian upper channel
            lower_channel: Donchian lower channel
            current_momentum: Current momentum value
            historical_momentum: Historical momentum average
            atr: Current ATR value (optional)
            avg_atr: Average ATR value (optional)

        Returns:
            Dict with score, grade, and recommendation

        """
        score = 0
        details = {}

        # H1: Breakout strength (25pts)
        breakout_strength = self._calculate_breakout_strength(
            price, upper_channel, lower_channel,
        )
        h1_score = self._score_breakout_strength(breakout_strength)
        score += h1_score
        details["breakout_strength"] = {
            "value": breakout_strength,
            "score": h1_score,
            "max_points": 25,
        }
        logging.debug(
            f"H1 Breakout Strength: {breakout_strength:.4f}, Score: {h1_score}/25",
        )

        # H2: Momentum ratio (25pts)
        momentum_ratio = (
            current_momentum / historical_momentum if historical_momentum > 0 else 0
        )
        h2_score = self._score_momentum_ratio(momentum_ratio)
        score += h2_score
        details["momentum_ratio"] = {
            "value": momentum_ratio,
            "score": h2_score,
            "max_points": 25,
        }
        logging.debug(f"H2 Momentum Ratio: {momentum_ratio:.2f}, Score: {h2_score}/25")

        # H3: Time session (20pts)
        h3_score = self._score_time_session()
        score += h3_score
        details["time_session"] = {"score": h3_score, "max_points": 20}
        logging.debug(f"H3 Time Session Score: {h3_score}/20")

        # H4: ATR volatility (15pts)
        if atr is not None and avg_atr is not None:
            atr_ratio = atr / avg_atr if avg_atr > 0 else 0
            h4_score = self._score_atr_volatility(atr_ratio)
            score += h4_score
            details["atr_volatility"] = {
                "value": atr_ratio,
                "score": h4_score,
                "max_points": 15,
            }
            logging.debug(f"H4 ATR Volatility: {atr_ratio:.2f}, Score: {h4_score}/15")
        else:
            details["atr_volatility"] = {"value": None, "score": 0, "max_points": 15}

        # H5: Spread (15pts)
        spread_score = self._score_spread(symbol)
        score += spread_score
        details["spread"] = {"score": spread_score, "max_points": 15}
        logging.debug(f"H5 Spread Score: {spread_score}/15")

        # Determine grade and recommendation
        grade = self._get_grade(score)
        trade_recommended = score >= 60

        result = {
            "score": score,
            "grade": grade,
            "trade_recommended": trade_recommended,
            "details": details,
        }

        logging.info(
            f"Trade Setup Score: {score}/100, Grade: {grade}, Recommended: {trade_recommended}",
        )
        return result

    def _calculate_breakout_strength(
        self, price: float, upper_channel: float, lower_channel: float,
    ) -> float:
        """Calculate breakout strength as percentage from channel"""
        channel_width = upper_channel - lower_channel
        if channel_width == 0:
            return 0

        # For buy breakout (price above upper channel)
        if price > upper_channel:
            return (price - upper_channel) / channel_width
        # For sell breakout (price below lower channel)
        if price < lower_channel:
            return (lower_channel - price) / channel_width
        return 0

    def _score_breakout_strength(self, breakout_strength: float) -> int:
        """Score breakout strength (0-25 points)"""
        if breakout_strength > 0.15:  # >15% breakout
            return 25
        if breakout_strength > 0.10:  # 10-15% breakout
            return 20
        if breakout_strength > 0.05:  # 5-10% breakout
            return 15
        if breakout_strength > 0.02:  # 2-5% breakout
            return 10
        return 0

    def _score_momentum_ratio(self, momentum_ratio: float) -> int:
        """Score momentum ratio (0-25 points) - refined for better quality"""
        # Require positive momentum (current > historical) for full points
        if momentum_ratio >= 1.5:
            return 25
        if momentum_ratio >= 1.2:
            return 20
        if momentum_ratio >= 1.0:
            return 15  # Still allow trades at breakeven momentum
        if momentum_ratio >= 0.9:  # Slightly below historical
            return 12  # Reduced but still tradeable
        if momentum_ratio >= 0.8:
            return 8
        return 5  # Very low score for weak momentum

    def _score_time_session(self) -> int:
        """Score based on trading session (0-20 points) - enhanced for overlap periods"""
        current_hour_utc = datetime.now(UTC).hour

        # Best sessions: London/NY overlap 13-16h UTC (highest liquidity)
        if 13 <= current_hour_utc <= 16:
            return 20
        # Good: London open 7-10h UTC
        if 7 <= current_hour_utc <= 10:
            return 18
        # Acceptable: Late London/Early NY 10-13h, 16-17h UTC
        if (10 <= current_hour_utc <= 12) or (16 <= current_hour_utc <= 17):
            return 12
        # Moderate: Extended hours 6-7h, 17-20h UTC
        if (6 <= current_hour_utc <= 6) or (17 <= current_hour_utc <= 20):
            return 8
        return 0  # Low liquidity periods

    def _score_atr_volatility(self, atr_ratio: float) -> int:
        """Score ATR volatility (0-15 points)"""
        if 1.0 < atr_ratio < 1.5:  # Optimal volatility
            return 15
        if 0.8 < atr_ratio < 2.0:  # Acceptable volatility
            return 10
        if 0.5 < atr_ratio < 2.5:  # Moderate volatility
            return 5
        return 0

    def _score_spread(self, symbol: str) -> int:
        """Score based on spread (0-15 points)"""
        try:
            tick = self.mt5.symbol_info_tick(symbol)  # type: ignore
            if tick:
                symbol_info = self.mt5.symbol_info(symbol)  # type: ignore
                if symbol_info:
                    point = symbol_info.point
                    spread_points = (tick.ask - tick.bid) / point if point > 0 else 0

                    if spread_points < 20:  # Excellent spread
                        return 15
                    if spread_points < 30:  # Good spread
                        return 12
                    if spread_points < 50:  # Acceptable spread
                        return 8
                    if spread_points < 100:  # High spread
                        return 4
                    # Very high spread
                    return 0
        except Exception as e:
            logging.debug(f"Error calculating spread score: {e}")

        # Default score if unable to calculate
        return 8

    def _get_grade(self, score: int) -> str:
        """Convert score to letter grade"""
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"
