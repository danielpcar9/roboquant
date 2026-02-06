"""
MT5 Utilities - Clean Consolidated Interface
Provides access to all MT5 trading functions with proper type hints
"""

# Import from new modular structure
from core.mt5_compat import mt5

from .mt5_core import (
    initialize_mt5,
)
from .orders.order_executor import (
    build_and_send_order,
    cancel_expired_pending_orders,
    place_pending_order,
)
from .orders.stop_management import (
    monitor_and_update_stops,
    update_trailing_stops,
)
from .positions.position_manager import (
    close_all_positions,
    close_position_by_ticket,
    get_net_position_by_symbol,
    get_open_positions,
    get_position_pnl,
    get_total_exposure,
)
from .risk_calculator import estimate_lots_by_risk


class MT5Gateway:
    """Object-oriented wrapper around MT5 utility functions.
    Preserves existing behavior by delegating to module-level functions.
    """

    def initialize(self) -> bool:
        """Initialize MT5 connection."""
        return initialize_mt5()

    def shutdown(self) -> None:
        """Shutdown MT5 connection."""
        mt5.shutdown()  # type: ignore

    def build_and_send_order(
        self,
        symbol: str,
        side: str,
        volume: float,
        sl: float | None = None,
        tp: float | None = None,
        deviation: int = 30,
        retries: int = 1,
        magic: int = 123456,
        mt5_module=None,
    ):
        return build_and_send_order(
            symbol, side, volume, sl, tp, deviation, retries, magic, mt5_module,
        )

    def place_pending_order(
        self,
        symbol,
        order_type,
        volume,
        price,
        sl=None,
        tp=None,
        deviation=30,
        expiration_hours=4,
        magic=123456,
        mt5_module=None,
    ):
        return place_pending_order(
            symbol,
            order_type,
            volume,
            price,
            sl,
            tp,
            deviation,
            expiration_hours,
            magic,
            mt5_module,
        )

    def cancel_expired_pending_orders(self, magic=123456, mt5_module=None):
        return cancel_expired_pending_orders(magic, mt5_module)

    def update_trailing_stops(self, mt5_module=None):
        return update_trailing_stops(mt5_module)

    def monitor_and_update_stops(self, mt5_module=None):
        return monitor_and_update_stops(mt5_module)

    def close_position_by_ticket(
        self, ticket, deviation=30, retries=1, mt5_module=None,
    ):
        return close_position_by_ticket(ticket, deviation, retries, mt5_module)

    def get_open_positions(self, mt5_module=None):
        """Get all open positions"""
        if mt5_module is None:
            mt5_module = mt5
        positions = mt5_module.positions_get()
        return [] if positions is None else positions

    def close_all_positions(self, mt5_module=None):
        """Close all open positions. Returns (closed_count, error_count)"""
        if mt5_module is None:
            mt5_module = mt5

        positions = self.get_open_positions(mt5_module)
        if not positions:
            return 0, 0

        closed_count = 0
        error_count = 0

        for position in positions:
            ticket = position.ticket
            try:
                success = self.close_position_by_ticket(ticket, mt5_module=mt5_module)
                if success:
                    closed_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        return closed_count, error_count

# Export everything for backward compatibility
__all__ = [
    # Order functions
    "build_and_send_order",
    "place_pending_order",
    "cancel_expired_pending_orders",

    # Stop management
    "update_trailing_stops",
    "monitor_and_update_stops",

    # Position functions
    "close_position_by_ticket",
    "get_open_positions",
    "close_all_positions",
    "get_position_pnl",
    "get_total_exposure",
    "get_net_position_by_symbol",

    # Core functions
    "initialize_mt5",
    "MT5Gateway",
    "estimate_lots_by_risk",
]
