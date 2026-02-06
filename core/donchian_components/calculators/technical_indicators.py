"""
Calculadores técnicos para la estrategia Donchian Channel

Contiene todas las funciones de cálculo de indicadores técnicos,
análisis de mercado y generación de señales.

Extraído de MarketDataService de donchian_strategy.py
"""

import logging

import numpy as np
import pandas as pd

from config.config_manager import config_manager
from core.mt5_compat import mt5
from utils.decorators import handle_exception, performance_monitor


class TechnicalIndicatorsCalculator:
    """Calculador especializado en indicadores técnicos"""

    def __init__(self, mt5_module=mt5):
        self.mt5 = mt5_module
        self.timeframe = self._get_timeframe_from_config()

    def _get_timeframe_from_config(self):
        """Convert timeframe name to MT5 constant"""
        timeframe_name = config_manager.get("TIMEFRAME")
        timeframe_map = {
            "M1": self.mt5.TIMEFRAME_M1,
            "M5": self.mt5.TIMEFRAME_M5,
            "M15": self.mt5.TIMEFRAME_M15,
            "M30": self.mt5.TIMEFRAME_M30,
            "H1": self.mt5.TIMEFRAME_H1,
            "H4": self.mt5.TIMEFRAME_H4,
            "D1": self.mt5.TIMEFRAME_D1,
            "W1": self.mt5.TIMEFRAME_W1,
            "MN1": self.mt5.TIMEFRAME_MN1,
        }
        return timeframe_map.get(timeframe_name.upper(), self.mt5.TIMEFRAME_M5)

    @handle_exception
    @performance_monitor
    def calculate_adx(self, symbol: str, period: int = 14) -> dict[str, float] | None:
        """Calculate ADX (Average Directional Index) with +DI and -DI"""
        logging.debug(f"Calculating ADX for {symbol} with period {period}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period * 3)
        if rates is None or len(rates) < period * 2:
            logging.error(
                f"Failed to get rate data for ADX calculation. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return None

        # Convert to pandas for easier manipulation
        import numpy as np
        import pandas as pd

        df = pd.DataFrame(rates)

        # Calculate True Range
        df['high_low'] = df['high'] - df['low']
        df['high_close'] = abs(df['high'] - df['close'].shift())
        df['low_close'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1)

        # Calculate Directional Movement
        df['up_move'] = df['high'] - df['high'].shift()
        df['down_move'] = df['low'].shift() - df['low']

        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)

        # Smooth using Wilder's smoothing (EMA with alpha = 1/period)
        alpha = 1 / period
        df['atr'] = df['tr'].ewm(alpha=alpha, adjust=False).mean()
        df['plus_dm_smooth'] = df['plus_dm'].ewm(alpha=alpha, adjust=False).mean()
        df['minus_dm_smooth'] = df['minus_dm'].ewm(alpha=alpha, adjust=False).mean()

        # Calculate DI+
        df['plus_di'] = 100 * (df['plus_dm_smooth'] / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm_smooth'] / df['atr'])

        # Calculate DX
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])

        # Calculate ADX
        df['adx'] = df['dx'].ewm(alpha=alpha, adjust=False).mean()

        # Get latest values
        adx_value = float(df['adx'].iloc[-1])
        di_plus = float(df['plus_di'].iloc[-1])
        di_minus = float(df['minus_di'].iloc[-1])

        logging.debug(f"ADX for {symbol}: {adx_value:.2f}, DI+: {di_plus:.2f}, DI-: {di_minus:.2f}")

        return {
            'adx': adx_value,
            'di_plus': di_plus,
            'di_minus': di_minus
        }

    @handle_exception
    @performance_monitor
    def get_donchian_channels(
        self, symbol: str, period: int,
    ) -> tuple[float | None, float | None]:
        """Calculate Donchian channels"""
        logging.debug(
            f"Calculating Donchian channels for {symbol} with period {period}",
        )
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period)
        if rates is None or len(rates) < period:
            logging.error(
                f"Failed to get rate data for Donchian calculation. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return None, None

        highs = [rate["high"] for rate in rates]
        lows = [rate["low"] for rate in rates]

        upper_channel = max(highs)
        lower_channel = min(lows)

        logging.debug(
            f"Calculated channels - Upper: {upper_channel}, Lower: {lower_channel}",
        )
        return upper_channel, lower_channel

    @handle_exception
    @performance_monitor
    def calculate_momentum(self, symbol: str, lookback: int) -> float:
        """Calculate average momentum over a lookback period"""
        logging.debug(f"Calculating momentum for {symbol} with lookback {lookback}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, lookback)
        if rates is None or len(rates) < lookback:
            logging.error(
                f"Failed to get rate data for momentum calculation. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return 0

        sum_momentum = 0
        for rate in rates:
            body = abs(rate["close"] - rate["open"])
            sum_momentum += body

        momentum = sum_momentum / lookback if lookback > 0 else 0
        logging.debug(f"Calculated momentum: {momentum}")
        return momentum

    @handle_exception
    @performance_monitor
    def calculate_atr(self, symbol: str, period: int = 14) -> float | None:
        """Calculate Average True Range"""
        logging.debug(f"Calculating ATR for {symbol} with period {period}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period + 1)
        if rates is None or len(rates) < period + 1:
            logging.error(
                f"Failed to get rate data for ATR calculation. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return None

        atr_values = []
        for i in range(1, len(rates)):
            tr1 = rates[i]["high"] - rates[i]["low"]
            tr2 = abs(rates[i]["high"] - rates[i - 1]["close"])
            tr3 = abs(rates[i]["low"] - rates[i - 1]["close"])
            tr = max(tr1, tr2, tr3)
            atr_values.append(tr)

        atr = sum(atr_values) / len(atr_values) if atr_values else 0
        logging.debug(f"ATR for {symbol}: {atr:.5f}")
        return float(atr)

    @handle_exception
    @performance_monitor
    def calculate_rsi(self, symbol: str, period: int = 14) -> float | None:
        """Calculate Relative Strength Index"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period * 2)
        if rates is None or len(rates) < period + 1:
            return None

        df = pd.DataFrame(rates)
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    @handle_exception
    @performance_monitor
    def calculate_slope(self, symbol: str, period: int = 30) -> float | None:
        """Calculate price slope using linear regression"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period)
        if rates is None or len(rates) < period:
            return None

        closes = np.array([rate["close"] for rate in rates])
        x = np.arange(len(closes))
        slope, _ = np.polyfit(x, closes, 1)
        return float(slope)

    @handle_exception
    @performance_monitor
    def calculate_sma(self, symbol: str, period: int) -> float | None:
        """Calculate Simple Moving Average"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period)
        if rates is None or len(rates) < period:
            return None

        closes = [rate["close"] for rate in rates]
        return sum(closes) / len(closes)

    @handle_exception
    @performance_monitor
    def get_current_price(self, symbol: str, order_type: str) -> float | None:
        """Get current price based on order type"""
        logging.debug(f"Getting current price for {symbol}, order type: {order_type}")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return None

        price = tick.ask if order_type == "BUY" else tick.bid
        logging.debug(f"Current price for {symbol}: {price}")
        return price

    @handle_exception
    @performance_monitor
    def get_spread(self, symbol: str) -> float | None:
        """Get current spread"""
        logging.debug(f"Calculating spread for {symbol}")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return None

        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return None

        point = symbol_info.point
        # Adjust point value for NASDAQ
        if "NASDAQ" in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        spread_points = (tick.ask - tick.bid) / point if point > 0 else 0
        logging.debug(f"Spread for {symbol}: {spread_points:.2f} points")
        return spread_points

    @handle_exception
    @performance_monitor
    def get_volume_stats(
        self, symbol: str, lookback: int = 20,
    ) -> tuple[float | None, float | None]:
        """Get volume statistics"""
        logging.debug(f"Calculating volume stats for {symbol} with lookback {lookback}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, lookback)
        if rates is None or len(rates) < lookback:
            logging.error(
                f"Failed to get rate data for volume calculation. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return None, None

        volumes = [rate["tick_volume"] for rate in rates]
        current_volume = volumes[-1] if volumes else 0
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        logging.debug(
            f"Volume stats for {symbol} - Current: {current_volume}, Average: {avg_volume:.2f}",
        )
        return current_volume, avg_volume

    @handle_exception
    @performance_monitor
    def detect_engulfing(self, symbol: str) -> tuple[bool, bool]:
        """Detect bullish and bearish engulfing patterns"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, 3)
        if rates is None or len(rates) < 2:
            logging.error(
                f"Failed to get rate data for engulfing pattern detection. Rates: {rates}, Length: {len(rates) if rates else 0}",
            )
            return False, False

        prev, current = rates[-2], rates[-1]

        # Envolvente alcista (bullish)
        bullish = (
            prev["close"] < prev["open"]
            and current["close"] > current["open"]
            and current["open"] < prev["close"]
            and current["close"] > prev["open"]
        )

        # Envolvente bajista (bearish)
        bearish = (
            prev["close"] > prev["open"]
            and current["close"] < current["open"]
            and current["open"] > prev["close"]
            and current["close"] < prev["open"]
        )

        return bullish, bearish
