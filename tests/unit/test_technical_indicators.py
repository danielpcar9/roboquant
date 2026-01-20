"""
Tests unitarios para TechnicalIndicatorsCalculator
"""

import pytest
from unittest.mock import Mock, patch


class TestTechnicalIndicatorsCalculator:
    """Suite de tests para TechnicalIndicatorsCalculator"""

    def test_init_with_custom_mt5(self, mock_mt5, mock_config_manager):
        """Test de inicialización con módulo MT5 personalizado"""
        from core.donchian_components.calculators.technical_indicators import (
            TechnicalIndicatorsCalculator,
        )

        calculator = TechnicalIndicatorsCalculator(mt5_module=mock_mt5)

        assert calculator.mt5 == mock_mt5
        assert (
            calculator.timeframe == mock_mt5.TIMEFRAME_H1
        )  # Valor por defecto del mock

    def test_get_timeframe_from_config_h1(self, mock_mt5):
        """Test de conversión de timeframe H1 desde configuración"""
        from core.donchian_components.calculators.technical_indicators import (
            TechnicalIndicatorsCalculator,
        )
        from config.config_manager import config_manager

        # Test con timeframe válido (H1)
        with patch.object(config_manager, "get", return_value="H1"):
            calculator = TechnicalIndicatorsCalculator(mt5_module=mock_mt5)
            # Verificar que devuelve el valor correcto del mock
            assert calculator.timeframe == mock_mt5.TIMEFRAME_H1

    def test_get_timeframe_from_config_invalid(self, mock_mt5):
        """Test de conversión con timeframe inválido (debe usar default M5)"""
        from core.donchian_components.calculators.technical_indicators import (
            TechnicalIndicatorsCalculator,
        )
        from config.config_manager import config_manager

        # Test con timeframe inválido (debería usar default M5)
        with patch.object(config_manager, "get", return_value="INVALID"):
            calculator = TechnicalIndicatorsCalculator(mt5_module=mock_mt5)
            assert calculator.timeframe == mock_mt5.TIMEFRAME_M5

    def test_get_donchian_channels_success(self, clean_technical_calculator, mock_mt5):
        """Test exitoso de cálculo de canales Donchian"""
        technical_calculator = clean_technical_calculator
        symbol = "XAUUSD"
        period = 20

        upper, lower = technical_calculator.get_donchian_channels(symbol, period)

        # Verificar que se llamaron las funciones correctas
        mock_mt5.copy_rates_from_pos.assert_called_once_with(
            symbol, technical_calculator.timeframe, 1, period
        )

        # Verificar resultados (deben ser números válidos)
        assert isinstance(upper, float)
        assert isinstance(lower, float)
        assert upper > lower
        assert upper > 0
        assert lower > 0

    def test_get_donchian_channels_insufficient_data(
        self, technical_calculator, mock_mt5
    ):
        """Test de canales Donchian con datos insuficientes"""
        # Configurar mock para devolver menos datos de los necesarios
        mock_mt5.copy_rates_from_pos.return_value = [
            {"high": 2350.0, "low": 2340.0}
        ]  # Solo 1 vela

        upper, lower = technical_calculator.get_donchian_channels("XAUUSD", 20)

        # Debería retornar None, None cuando no hay suficientes datos
        assert upper is None
        assert lower is None

    def test_get_donchian_channels_mt5_error(self, technical_calculator, mock_mt5):
        """Test de canales Donchian cuando MT5 falla"""
        # Configurar mock para simular error de MT5
        mock_mt5.copy_rates_from_pos.return_value = None

        upper, lower = technical_calculator.get_donchian_channels("XAUUSD", 20)

        # Debería manejar el error gracefully
        assert upper is None
        assert lower is None

    def test_calculate_atr_success(self, technical_calculator, mock_mt5):
        """Test exitoso de cálculo de ATR"""
        symbol = "XAUUSD"
        period = 14

        atr = technical_calculator.calculate_atr(symbol, period)

        # Verificar llamada correcta
        mock_mt5.copy_rates_from_pos.assert_called_with(
            symbol, technical_calculator.timeframe, 1, period + 1
        )

        # Verificar resultado válido
        assert isinstance(atr, float)
        assert atr > 0

    def test_calculate_atr_insufficient_data(self, technical_calculator, mock_mt5):
        """Test de ATR con datos insuficientes"""
        # Solo una vela (necesita al menos 2 para calcular TR)
        mock_mt5.copy_rates_from_pos.return_value = [
            {"high": 2350.0, "low": 2340.0, "close": 2345.0}
        ]

        atr = technical_calculator.calculate_atr("XAUUSD", 14)

        assert atr is None

    def test_calculate_momentum_success(self, technical_calculator, mock_mt5):
        """Test exitoso de cálculo de momentum"""
        symbol = "XAUUSD"
        lookback = 10

        momentum = technical_calculator.calculate_momentum(symbol, lookback)

        # Verificar llamada correcta
        mock_mt5.copy_rates_from_pos.assert_called_with(
            symbol, technical_calculator.timeframe, 1, lookback
        )

        # Verificar resultado válido
        assert isinstance(momentum, float)
        assert momentum >= 0  # El momentum debería ser no negativo

    def test_calculate_momentum_empty_data(self, technical_calculator, mock_mt5):
        """Test de momentum con datos vacíos"""
        mock_mt5.copy_rates_from_pos.return_value = []

        momentum = technical_calculator.calculate_momentum("XAUUSD", 10)

        assert momentum == 0  # Debería retornar 0 cuando no hay datos

    def test_get_current_price_buy(self, technical_calculator, mock_mt5):
        """Test de obtención de precio actual para orden BUY"""
        symbol = "XAUUSD"
        order_type = "BUY"

        price = technical_calculator.get_current_price(symbol, order_type)

        # Verificar que se usa el precio ASK para BUY
        mock_mt5.symbol_info_tick.assert_called_once_with(symbol)
        assert price == mock_mt5.symbol_info_tick.return_value.ask

    def test_get_current_price_sell(self, technical_calculator, mock_mt5):
        """Test de obtención de precio actual para orden SELL"""
        symbol = "XAUUSD"
        order_type = "SELL"

        price = technical_calculator.get_current_price(symbol, order_type)

        # Verificar que se usa el precio BID para SELL
        mock_mt5.symbol_info_tick.assert_called_once_with(symbol)
        assert price == mock_mt5.symbol_info_tick.return_value.bid

    def test_get_current_price_mt5_error(self, technical_calculator, mock_mt5):
        """Test de precio actual cuando MT5 falla"""
        mock_mt5.symbol_info_tick.return_value = None

        price = technical_calculator.get_current_price("XAUUSD", "BUY")

        assert price is None

    def test_get_spread_success(self, technical_calculator, mock_mt5):
        """Test exitoso de obtención de spread"""
        symbol = "XAUUSD"

        spread = technical_calculator.get_spread(symbol)

        # Verificar llamadas correctas
        mock_mt5.symbol_info_tick.assert_called_once_with(symbol)
        mock_mt5.symbol_info.assert_called_once_with(symbol)

        # Verificar resultado válido
        assert isinstance(spread, float)
        assert spread >= 0

    def test_get_spread_mt5_errors(self, technical_calculator, mock_mt5):
        """Test de spread cuando MT5 falla"""
        # Test cuando symbol_info_tick falla
        mock_mt5.symbol_info_tick.return_value = None
        spread = technical_calculator.get_spread("XAUUSD")
        assert spread is None

        # Resetear mock y test cuando symbol_info falla
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2350.0, bid=2348.0)
        mock_mt5.symbol_info.return_value = None
        spread = technical_calculator.get_spread("XAUUSD")
        assert spread is None

    def test_get_volume_stats_success(self, technical_calculator, mock_mt5):
        """Test exitoso de estadísticas de volumen"""
        symbol = "XAUUSD"
        lookback = 20

        current_volume, avg_volume = technical_calculator.get_volume_stats(
            symbol, lookback
        )

        # Verificar llamada correcta
        mock_mt5.copy_rates_from_pos.assert_called_with(
            symbol, technical_calculator.timeframe, 1, lookback
        )

        # Verificar resultados válidos
        assert isinstance(current_volume, (int, float))
        assert isinstance(avg_volume, float)
        assert current_volume >= 0
        assert avg_volume >= 0

    def test_detect_engulfing_patterns(self, technical_calculator, mock_mt5):
        """Test de detección de patrones envolventes"""
        symbol = "XAUUSD"

        bullish, bearish = technical_calculator.detect_engulfing(symbol)

        # Verificar llamada correcta (necesita 3 velas)
        mock_mt5.copy_rates_from_pos.assert_called_with(
            symbol, technical_calculator.timeframe, 1, 3
        )

        # Verificar resultados booleanos
        assert isinstance(bullish, bool)
        assert isinstance(bearish, bool)

    def test_detect_engulfing_insufficient_data(self, technical_calculator, mock_mt5):
        """Test de detección de envolventes con datos insuficientes"""
        # Solo una vela
        mock_mt5.copy_rates_from_pos.return_value = [{"open": 2345.0, "close": 2348.0}]

        bullish, bearish = technical_calculator.detect_engulfing("XAUUSD")

        # Debería retornar False, False cuando no hay suficientes datos
        assert bullish is False
        assert bearish is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
