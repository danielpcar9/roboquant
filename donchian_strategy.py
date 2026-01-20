"""Backward compatibility wrapper - redirects to core.donchian_strategy"""

from core.donchian_components.calculators.technical_indicators import *
from core.donchian_components.validators.risk_market_validators import *
from core.donchian_components.managers.position_managers import *

if __name__ == "__main__":
    # Import and run main from core
    from core.donchian_strategy import main

    main()
