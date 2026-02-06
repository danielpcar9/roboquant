import logging
from datetime import UTC, datetime

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5


class SessionFilter:
    """Filter trades based on historical performance by session"""

    def __init__(self, mt5_module=None):
        self.mt5 = mt5_module or mt5
        # Define trading sessions
        self.sessions = {
            "ASIAN": (0, 7),  # 00:00-07:00 UTC
            "EUROPEAN": (7, 15),  # 07:00-15:00 UTC
            "AMERICAN": (13, 21),  # 13:00-21:00 UTC
            "OVERLAP": (7, 10),  # 07:00-10:00 UTC (London/NY overlap)
            "LATE_NY": (20, 23),  # 20:00-23:00 UTC
        }

    def get_current_session(self) -> str:
        """
        Get the current trading session based on UTC time

        Returns:
            Current session name

        """
        current_hour = datetime.now(UTC).hour

        for session_name, (start, end) in self.sessions.items():
            if start <= current_hour < end:
                return session_name

        return "OTHER"

    def get_session_performance(
        self, symbol: str, hours_back: int = 240,
    ) -> dict[str, dict[str, float]]:
        """
        Analyze historical performance by session

        Args:
            symbol: Trading symbol
            hours_back: Number of hours to look back for analysis

        Returns:
            Dictionary with session performance statistics

        """
        try:
            # Get historical hourly data
            rates = self.mt5.copy_rates_from_pos(
                symbol, self.mt5.TIMEFRAME_H1, 1, hours_back,
            )  # type: ignore
            if rates is None or len(rates) == 0:
                logging.warning(
                    f"Insufficient data to analyze session performance for {symbol}",
                )
                return {}

            # Initialize session statistics
            session_stats: dict[str, dict[str, float]] = {
                session: {
                    "total_bars": 0.0,
                    "up_bars": 0.0,
                    "down_bars": 0.0,
                    "total_movement": 0.0,
                    "avg_movement": 0.0,
                }
                for session in self.sessions
            }

            # Analyze each bar and categorize by session
            for rate in rates:
                # Convert timestamp to hour
                bar_time = datetime.fromtimestamp(rate["time"])
                bar_hour = bar_time.hour

                # Determine which session this bar belongs to
                for session_name, (start, end) in self.sessions.items():
                    if start <= bar_hour < end:
                        # Update statistics for this session
                        session_stats[session_name]["total_bars"] += 1.0

                        # Calculate price movement
                        movement = abs(rate["high"] - rate["low"])
                        session_stats[session_name]["total_movement"] += movement

                        # Count up/down bars
                        if rate["close"] > rate["open"]:
                            session_stats[session_name]["up_bars"] += 1.0
                        else:
                            session_stats[session_name]["down_bars"] += 1.0

            # Calculate average movement per session
            for session_name in session_stats:
                stats = session_stats[session_name]
                if stats["total_bars"] > 0:
                    stats["avg_movement"] = (
                        stats["total_movement"] / stats["total_bars"]
                    )
                    stats["up_ratio"] = stats["up_bars"] / stats["total_bars"]
                    stats["down_ratio"] = stats["down_bars"] / stats["total_bars"]

            return session_stats
        except Exception as e:
            logging.exception(f"Error analyzing session performance for {symbol}: {e}")
            return {}

    def is_favorable_session(
        self, symbol: str, session_name: str | None = None,
    ) -> tuple[bool, float]:
        """
        Determine if the current or specified session is favorable for trading

        Args:
            symbol: Trading symbol
            session_name: Specific session to check (if None, uses current session)

        Returns:
            Tuple of (is_favorable, confidence_score)

        """
        if session_name is None:
            session_name = self.get_current_session()

        # Get session performance data
        performance = self.get_session_performance(symbol)
        if not performance or session_name not in performance:
            logging.warning(f"No performance data for session {session_name}")
            return True, 0.5  # Neutral if no data

        session_data = performance[session_name]

        # Calculate confidence score based on multiple factors
        total_bars = session_data["total_bars"]
        if total_bars == 0:
            return True, 0.5  # Neutral if no bars

        # Factors for confidence calculation:
        # 1. Strength of trend (up/down ratio)
        up_ratio = session_data.get("up_ratio", 0.5)
        trend_strength = abs(up_ratio - 0.5) * 2  # 0-1 scale

        # 2. Volatility (average movement compared to overall average)
        all_avg_movements = [
            data["avg_movement"]
            for data in performance.values()
            if data["total_bars"] > 0
        ]
        if all_avg_movements:
            overall_avg_movement = sum(all_avg_movements) / len(all_avg_movements)
            if overall_avg_movement > 0:
                volatility_ratio = session_data["avg_movement"] / overall_avg_movement
                # Normalize volatility ratio (0.5-2.0 is good range)
                volatility_score = max(0.0, min(1.0, (volatility_ratio - 0.5) / 1.5))
            else:
                volatility_score = 0.5
        else:
            volatility_score = 0.5

        # 3. Sample size weighting (more data = higher confidence)
        sample_weight = min(1.0, total_bars / 100.0)  # Cap at 100 bars

        # Combined confidence score (0-1)
        confidence = trend_strength * 0.4 + volatility_score * 0.4 + sample_weight * 0.2

        # Session is favorable if confidence > 0.6
        is_favorable = confidence > 0.6

        logging.info(
            f"Session {session_name} favorable: {is_favorable} (confidence: {confidence:.2f})",
        )

        return is_favorable, confidence

    def get_best_sessions(self, symbol: str, top_n: int = 3) -> list[tuple[str, float]]:
        """
        Get the top N best performing sessions for a symbol

        Args:
            symbol: Trading symbol
            top_n: Number of top sessions to return

        Returns:
            List of (session_name, confidence_score) tuples

        """
        performance = self.get_session_performance(symbol)
        if not performance:
            return []

        # Calculate confidence scores for all sessions
        session_scores = []
        for session_name in performance:
            is_favorable, confidence = self.is_favorable_session(symbol, session_name)
            session_scores.append((session_name, confidence))

        # Sort by confidence score (descending)
        session_scores.sort(key=lambda x: x[1], reverse=True)

        return session_scores[:top_n]


# Global instance for easy access
session_filter = SessionFilter()

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s",
    )

    # Test session detection
    current_session = session_filter.get_current_session()
    print(f"Current session: {current_session}")

    # Test session performance (would require MT5 to be running)
    # performance = session_filter.get_session_performance("XAUUSD")
    # print(f"Session performance: {performance}")
    pass
