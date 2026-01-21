"""Backward compatibility wrapper - redirects to core.donchian_strategy"""

from core.donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,  # noqa: F401
)
from core.donchian_components.managers.position_managers import (  # noqa: F401
    PositionManager,
    RiskValidator,
    TradeTracker,
)
from core.donchian_components.validators.risk_market_validators import (
    MarketValidator,  # noqa: F401
)

if __name__ == "__main__":
    # Import and run main from core
    from core.donchian_strategy import DonchianStrategy

    strategy = DonchianStrategy()
    strategy.main()
