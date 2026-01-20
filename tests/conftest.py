"""
Configuración de tests para la suite unitaria de RoboQuant
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch
import pytest
import numpy as np


# Añadir el directorio raíz al path para imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "core"))
sys.path.insert(0, str(project_root / "utils"))


@pytest.fixture
def mock_mt5():
    """Mock de MetaTrader5 para tests"""
    import MetaTrader5 as mt5

    with patch.object(mt5, "initialize", return_value=True):
        with patch.object(mt5, "terminal_info", return_value=Mock()):
            with patch.object(
                mt5,
                "account_info",
                return_value=Mock(
                    balance=10000.0, equity=10000.0, margin=0.0, free_margin=10000.0
                ),
            ):
                # Mock para datos de mercado
                mock_rates = [
                    {
                        "time": 1234567890,
                        "open": 2345.0,
                        "high": 2350.0,
                        "low": 2340.0,
                        "close": 2348.0,
                        "tick_volume": 100,
                        "spread": 2,
                    }
                    for _ in range(100)  # 100 velas de ejemplo
                ]

                with patch.object(mt5, "copy_rates_from_pos", return_value=mock_rates):
                    # Mock para tick data
                    mock_tick = Mock(
                        ask=2348.5,
                        bid=2348.0,
                        last=2348.2,
                        volume=1000,
                        time=1234567890,
                    )
                    with patch.object(mt5, "symbol_info_tick", return_value=mock_tick):
                        # Mock para symbol info
                        mock_symbol_info = Mock(
                            point=0.1,
                            volume_min=0.01,
                            volume_max=100.0,
                            volume_step=0.01,
                        )
                        with patch.object(
                            mt5, "symbol_info", return_value=mock_symbol_info
                        ):
                            # Mock para positions_get
                            with patch.object(mt5, "positions_get", return_value=[]):
                                # Mock para constantes de timeframe
                                mt5.TIMEFRAME_M1 = 1
                                mt5.TIMEFRAME_M5 = 5
                                mt5.TIMEFRAME_M15 = 15
                                mt5.TIMEFRAME_M30 = 30
                                mt5.TIMEFRAME_H1 = 16385
                                mt5.TIMEFRAME_H4 = 16388
                                mt5.TIMEFRAME_D1 = 16408
                                mt5.TIMEFRAME_W1 = 32769
                                mt5.TIMEFRAME_MN1 = 49153

                                yield mt5


@pytest.fixture
def sample_price_data():
    """Datos de precios de ejemplo para tests"""
    # Generar datos OHLC realistas
    np.random.seed(42)  # Para reproducibilidad
    base_price = 2345.0
    returns = np.random.normal(0, 0.005, 100)  # 0.5% volatilidad diaria

    prices = [base_price]
    for ret in returns:
        prices.append(prices[-1] * (1 + ret))

    # Convertir a formato OHLC
    ohlc_data = []
    for i, price in enumerate(prices[:-1]):
        high = price * (1 + abs(np.random.normal(0, 0.002)))
        low = price * (1 - abs(np.random.normal(0, 0.002)))
        close = prices[i + 1]
        open_price = price

        ohlc_data.append(
            {
                "time": 1234567890 + i * 3600,  # Una hora de diferencia
                "open": round(open_price, 2),
                "high": round(max(high, open_price, close), 2),
                "low": round(min(low, open_price, close), 2),
                "close": round(close, 2),
                "tick_volume": np.random.randint(50, 200),
                "spread": 2,
            }
        )

    return ohlc_data


@pytest.fixture
def mock_config_manager():
    """Mock del administrador de configuración"""
    with patch("config.config_manager.config_manager") as mock_config:
        mock_config.get.side_effect = lambda key, default=None: {
            "SYMBOL": "XAUUSD",
            "TIMEFRAME": "H1",
            "PERIOD": 50,
            "LOOKBACK": 10,
            "RISK_PERCENT": 1.0,
            "USE_RISK_MANAGEMENT": True,
            "MAX_SPREAD_POINTS": 20,
            "TRADING_HOUR_START": 0,
            "TRADING_HOUR_END": 23,
            "MAGIC_NUMBER": 123456,
            "SL_ATR_MULTIPLIER": 3.0,
            "TP_ATR_MULTIPLIER": 6.0,
        }.get(key, default)
        yield mock_config


@pytest.fixture
def technical_calculator(mock_mt5, mock_config_manager):
    """Instancia del calculador técnico con mocks"""
    from core.donchian_components.calculators.technical_indicators import (
        TechnicalIndicatorsCalculator,
    )

    return TechnicalIndicatorsCalculator(mt5_module=mock_mt5)


@pytest.fixture
def clean_technical_calculator(mock_mt5):
    """Instancia del calculador técnico sin configuración específica"""
    from core.donchian_components.calculators.technical_indicators import (
        TechnicalIndicatorsCalculator,
    )

    # Crear calculador sin depender del config manager mock
    return TechnicalIndicatorsCalculator(mt5_module=mock_mt5)
