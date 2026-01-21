"""Launcher/Entry point for Donchian Strategy - Redirects to core implementation"""

# Import classes for backward compatibility
from core.donchian_strategy import DonchianStrategy

# Re-export for backward compatibility
__all__ = [
    "DonchianStrategy",
]

if __name__ == "__main__":
    # Import and run main from core
    from core.donchian_strategy import DonchianStrategy

    strategy = DonchianStrategy()
    strategy.main()
