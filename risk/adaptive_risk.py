import logging

# Import MetaTrader5 (official package name)
from core.mt5_compat import mt5, MT5_AVAILABLE


class AdaptiveRiskManager:
    """Adaptive risk management with dynamic SL/TP based on ATR"""

    def __init__(self, mt5_module=None):
        self.mt5 = mt5_module or mt5

    def calculate_dynamic_stops(
        self,
        symbol: str,
        entry_price: float,
        order_type: str,
        atr: float | None = None,
        atr_period: int = 14,
        risk_reward_ratio: float = 2.0,
    ) -> tuple[float, float]:
        """
        Calculate dynamic stop loss and take profit levels based on ATR

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            order_type: "BUY" or "SELL"
            atr: Pre-calculated ATR value (optional)
            atr_period: ATR calculation period (if atr not provided)
            risk_reward_ratio: Desired risk/reward ratio

        Returns:
            Tuple of (stop_loss_price, take_profit_price)

        """
        try:
            # Get ATR if not provided
            if atr is None:
                atr = self.calculate_atr(symbol, atr_period)
                if atr is None:
                    logging.warning(
                        f"Failed to calculate ATR for {symbol}, using default values",
                    )
                    atr = 5.0  # Default fallback value

            # Get symbol information for point value
            symbol_info = self.mt5.symbol_info(symbol)  # type: ignore
            if symbol_info is None:
                logging.error(f"Failed to get symbol info for {symbol}")
                # Fallback values
                point = 0.01 if "JPY" not in symbol else 0.1
            else:
                point = symbol_info.point

            # Calculate stop loss distance in points (2x ATR as default)
            sl_distance_points = (atr * 2) / point

            # Calculate take profit distance based on risk/reward ratio
            tp_distance_points = sl_distance_points * risk_reward_ratio

            # Calculate actual prices
            if order_type == "BUY":
                stop_loss_price = entry_price - (sl_distance_points * point)
                take_profit_price = entry_price + (tp_distance_points * point)
            else:  # SELL
                stop_loss_price = entry_price + (sl_distance_points * point)
                take_profit_price = entry_price - (tp_distance_points * point)

            logging.info(
                f"Dynamic stops for {symbol} {order_type}: "
                f"SL={stop_loss_price:.5f}, TP={take_profit_price:.5f} "
                f"(ATR={atr:.5f}, RR={risk_reward_ratio})",
            )

            return stop_loss_price, take_profit_price
        except Exception as e:
            logging.exception(f"Error calculating dynamic stops for {symbol}: {e}")
            # Return default values
            default_sl = entry_price * 0.01  # 1% stop loss
            default_tp = entry_price * 0.02  # 2% take profit
            if order_type == "BUY":
                return entry_price - default_sl, entry_price + default_tp
            return entry_price + default_sl, entry_price - default_tp

    def calculate_atr(self, symbol: str, period: int = 14) -> float | None:
        """
        Calculate Average True Range

        Args:
            symbol: Trading symbol
            period: ATR calculation period

        Returns:
            ATR value or None if calculation fails

        """
        try:
            rates = self.mt5.copy_rates_from_pos(
                symbol, self.mt5.TIMEFRAME_H1, 1, period + 1,
            )  # type: ignore
            if rates is None or len(rates) < period + 1:
                logging.warning(f"Insufficient data to calculate ATR for {symbol}")
                return None

            atr_values = []
            for i in range(1, len(rates)):
                tr1 = rates[i]["high"] - rates[i]["low"]
                tr2 = abs(rates[i]["high"] - rates[i - 1]["close"])
                tr3 = abs(rates[i]["low"] - rates[i - 1]["close"])
                tr = max(tr1, tr2, tr3)
                atr_values.append(tr)

            atr = sum(atr_values) / len(atr_values) if atr_values else 0
            return atr
        except Exception as e:
            logging.exception(f"Error calculating ATR for {symbol}: {e}")
            return None

    def adjust_position_size_by_volatility(
        self, base_lots: float, atr: float, avg_atr: float,
    ) -> float:
        """
        Adjust position size based on current volatility relative to average

        Args:
            base_lots: Base position size
            atr: Current ATR
            avg_atr: Average ATR

        Returns:
            Adjusted position size

        """
        if avg_atr is None or avg_atr == 0:
            logging.warning("Invalid average ATR, returning base lots")
            return base_lots

        # Calculate volatility ratio
        volatility_ratio = atr / avg_atr

        # Adjust position size inversely to volatility
        # Higher volatility = smaller position size
        # Lower volatility = larger position size
        adjusted_lots = base_lots / volatility_ratio

        # Ensure we don't exceed reasonable limits
        max_lots = base_lots * 2  # Maximum 2x base size
        min_lots = base_lots * 0.5  # Minimum 0.5x base size

        adjusted_lots = max(min(adjusted_lots, max_lots), min_lots)

        logging.info(
            f"Position size adjustment: {base_lots:.2f} -> {adjusted_lots:.2f} "
            f"(volatility ratio: {volatility_ratio:.2f})",
        )

        return adjusted_lots


# Global instance for easy access
adaptive_risk_manager = AdaptiveRiskManager()

if __name__ == "__main__":
    # Example usage
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(message)s",
    )

    # Test calculations (would require MT5 to be running)
    # sl, tp = adaptive_risk_manager.calculate_dynamic_stops("XAUUSD", 1950.0, "BUY")
    # print(f"Dynamic stops: SL={sl:.5f}, TP={tp:.5f}")
    pass
