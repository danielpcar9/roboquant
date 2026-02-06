"""
MT5 Compatibility Layer for Cross-Platform Development.

This module provides a compatibility layer that allows the roboquant project
to run on macOS for development and backtesting, while maintaining full
MetaTrader5 functionality on Windows for live trading.

Usage:
    Replace: import MetaTrader5 as mt5
    With:    from core.mt5_compat import mt5, MT5_AVAILABLE

The MT5_AVAILABLE flag can be used to conditionally execute MT5-only code:
    if MT5_AVAILABLE:
        # Live trading code
    else:
        # Mock/simulation code
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as _mt5
    mt5: Any = _mt5
    MT5_AVAILABLE = True
    logger.info("✅ MetaTrader5 disponible - modo trading real")
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False  # noqa: F811
    logger.warning("⚠️ MetaTrader5 no disponible - modo desarrollo/backtesting")


# ============================================================================
# MT5 Mock Classes and Constants (used when MT5 is not available)
# ============================================================================

class MT5Mock:
    """
    Mock implementation of MetaTrader5 for development on non-Windows platforms.

    This provides stub implementations of MT5 functions that return sensible
    defaults, allowing the codebase to run without errors on Mac/Linux.
    """

    # Timeframes
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440
    TIMEFRAME_W1 = 10080
    TIMEFRAME_MN1 = 43200

    # Order types
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1
    ORDER_TYPE_BUY_LIMIT = 2
    ORDER_TYPE_SELL_LIMIT = 3
    ORDER_TYPE_BUY_STOP = 4
    ORDER_TYPE_SELL_STOP = 5

    # Trade actions
    TRADE_ACTION_DEAL = 1
    TRADE_ACTION_PENDING = 5
    TRADE_ACTION_SLTP = 6
    TRADE_ACTION_MODIFY = 7
    TRADE_ACTION_REMOVE = 8

    # Trade return codes
    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_PLACED = 10008
    TRADE_RETCODE_ERROR = 10006

    # Copy ticks flags
    COPY_TICKS_ALL = 0
    COPY_TICKS_INFO = 1
    COPY_TICKS_TRADE = 2

    # Position type
    POSITION_TYPE_BUY = 0
    POSITION_TYPE_SELL = 1

    # Order filling modes
    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    # Order time types
    ORDER_TIME_GTC = 0
    ORDER_TIME_DAY = 1
    ORDER_TIME_SPECIFIED = 2
    ORDER_TIME_SPECIFIED_DAY = 3

    # Symbol info flags
    SYMBOL_TRADE_MODE_DISABLED = 0
    SYMBOL_TRADE_MODE_LONGONLY = 1
    SYMBOL_TRADE_MODE_SHORTONLY = 2
    SYMBOL_TRADE_MODE_CLOSEONLY = 3
    SYMBOL_TRADE_MODE_FULL = 4

    def __init__(self):
        self._initialized = False
        self._last_error = (0, "No error")

    def initialize(self, path: str | None = None, login: int | None = None,
                   password: str | None = None, server: str | None = None,
                   timeout: int | None = None, portable: bool = False) -> bool:
        """Mock initialize - always returns False on non-Windows."""
        logger.warning("MT5 Mock: initialize() called - MT5 no disponible en esta plataforma")
        self._initialized = False
        self._last_error = (1, "MT5 no disponible en macOS/Linux - usar Windows para trading real")
        return False

    def shutdown(self) -> None:
        """Mock shutdown."""
        self._initialized = False

    def last_error(self) -> tuple:
        """Return last error."""
        return self._last_error

    def terminal_info(self) -> Any | None:
        """Mock terminal info."""
        return None

    def account_info(self) -> Any | None:
        """Mock account info."""
        return None

    def symbol_info(self, symbol: str) -> Any | None:
        """Mock symbol info."""
        return None

    def symbol_info_tick(self, symbol: str) -> Any | None:
        """Mock symbol tick info."""
        return None

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        """Mock symbol select."""
        return False

    def copy_rates_from(self, symbol: str, timeframe: int,
                        date_from: datetime, count: int) -> Any | None:
        """Mock copy rates from date."""
        logger.warning(f"MT5 Mock: copy_rates_from({symbol}) - retornando None")
        return None

    def copy_rates_from_pos(self, symbol: str, timeframe: int,
                            start_pos: int, count: int) -> Any | None:
        """Mock copy rates from position."""
        logger.warning(f"MT5 Mock: copy_rates_from_pos({symbol}) - retornando None")
        return None

    def copy_rates_range(self, symbol: str, timeframe: int,
                         date_from: datetime, date_to: datetime) -> Any | None:
        """Mock copy rates range."""
        logger.warning(f"MT5 Mock: copy_rates_range({symbol}) - retornando None")
        return None

    def copy_ticks_from(self, symbol: str, date_from: datetime,
                        count: int, flags: int) -> Any | None:
        """Mock copy ticks from date."""
        return None

    def copy_ticks_range(self, symbol: str, date_from: datetime,
                         date_to: datetime, flags: int) -> Any | None:
        """Mock copy ticks range."""
        return None

    def orders_total(self) -> int:
        """Mock orders total."""
        return 0

    def orders_get(self, symbol: str | None = None,
                   ticket: int | None = None) -> tuple | None:
        """Mock get orders."""
        return None

    def positions_total(self) -> int:
        """Mock positions total."""
        return 0

    def positions_get(self, symbol: str | None = None,
                      ticket: int | None = None) -> tuple | None:
        """Mock get positions."""
        return None

    def history_orders_total(self, date_from: datetime, date_to: datetime) -> int:
        """Mock history orders total."""
        return 0

    def history_orders_get(self, date_from: datetime, date_to: datetime,
                           group: str | None = None) -> tuple | None:
        """Mock get history orders."""
        return None

    def history_deals_total(self, date_from: datetime, date_to: datetime) -> int:
        """Mock history deals total."""
        return 0

    def history_deals_get(self, date_from: datetime, date_to: datetime,
                          group: str | None = None) -> tuple | None:
        """Mock get history deals."""
        return None

    def order_send(self, request: dict) -> Any:
        """Mock order send - returns error result."""
        logger.warning("MT5 Mock: order_send() called - operación no ejecutada")

        class MockOrderResult:
            retcode = MT5Mock.TRADE_RETCODE_ERROR
            comment = "MT5 Mock - use Windows for real trading"
            order = 0
            deal = 0
            volume = 0.0
            price = 0.0

        return MockOrderResult()

    def order_check(self, request: dict) -> Any:
        """Mock order check."""
        class MockCheckResult:
            retcode = MT5Mock.TRADE_RETCODE_ERROR
            comment = "MT5 Mock - use Windows for real trading"

        return MockCheckResult()

    def order_calc_margin(self, action: int, symbol: str,
                          volume: float, price: float) -> float | None:
        """Mock margin calculation."""
        return None

    def order_calc_profit(self, action: int, symbol: str, volume: float,
                          price_open: float, price_close: float) -> float | None:
        """Mock profit calculation."""
        return None


# Use mock if MT5 is not available
if not MT5_AVAILABLE:
    mt5 = MT5Mock()


def is_mt5_available() -> bool:
    """Check if MetaTrader5 is available on this platform."""
    return MT5_AVAILABLE


def require_mt5(func):
    """
    Decorator that warns when MT5-only functions are called without MT5.

    Usage:
        @require_mt5
        def my_trading_function():
            # This function requires MT5
            pass
    """
    def wrapper(*args, **kwargs):
        if not MT5_AVAILABLE:
            logger.warning(
                f"⚠️ {func.__name__}() requiere MT5 - "
                "función no disponible en modo desarrollo"
            )
            return None
        return func(*args, **kwargs)
    return wrapper
