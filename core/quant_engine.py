"""
Quantitative Trading Engine - Clean Interface
Provides simplified access to all quantitative trading components
"""

from .quant.engine import (
    QuantitativeEngine,
    QuantitativeIntegration,
)

# Backward compatibility exports
__all__ = [
    "QuantitativeEngine",
    "QuantitativeIntegration",
]
