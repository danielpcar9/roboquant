"""
Tests unitarios para MarketValidator
"""

from unittest.mock import Mock, patch

import pytest


class TestMarketValidator:
    """Suite de tests para MarketValidator"""

    @pytest.fixture
    def market_validator(self, mock_mt5, technical_calculator):
        """Fixture para crear instancia de MarketValidator"""
        from core.donchian_components.validators.risk_market_validators import (
            MarketValidator,
        )

        return MarketValidator(
            mt5_module=mock_mt5, market_data_service=technical_calculator,
        )

    def test_init_with_custom_mt5(self, mock_mt5):
        """Test de inicialización con módulo MT5 personalizado"""
        from core.donchian_components.validators.risk_market_validators import (
            MarketValidator,
        )

        validator = MarketValidator(mt5_module=mock_mt5, market_data_service=Mock())

        assert validator.mt5 == mock_mt5

    def test_is_trading_session_active_during_hours(
        self, market_validator, mock_config_manager,
    ):
        """Test de sesión de trading activa durante horas permitidas"""

        # Mock configuración para horas de trading
        with patch.object(
            mock_config_manager,
            "get",
            side_effect=lambda key, default=None: {
                "TRADING_HOUR_START": 0,  # 00:00
                "TRADING_HOUR_END": 23,  # 23:59
            }.get(key, default),
        ):
            is_active, message = market_validator.is_trading_session_active()

            assert is_active is True
            assert isinstance(message, str)

    def test_is_trading_session_active_outside_hours(
        self, market_validator, mock_config_manager,
    ):
        """Test de sesión de trading fuera de horas permitidas"""

        # Mock configuración para horas restringidas
        with patch.object(
            mock_config_manager,
            "get",
            side_effect=lambda key, default=None: {
                "TRADING_HOUR_START": 14,  # 14:00
                "TRADING_HOUR_END": 16,  # 16:00
            }.get(key, default),
        ):
            # Mock time para simular hora fuera de rango (10:00 AM)
            # El código usa datetime.fromtimestamp(time.time())
            with patch("time.time", return_value=1738749600): # timestamp for 10:00 AM some day
                is_active, message = market_validator.is_trading_session_active()

                assert is_active is False
                assert isinstance(message, str)
                assert "outside" in message.lower()

    def test_check_spread_acceptable_normal_spread(self, market_validator, mock_mt5):
        """Test de verificación de spread aceptable"""
        symbol = "XAUUSD"

        # Mock para devolver spread normal
        with patch.object(market_validator.market_data, "get_spread", return_value=10.0):
            is_acceptable, message = market_validator.check_spread(symbol)

            assert is_acceptable is True
            assert isinstance(message, str)

    def test_check_spread_too_wide(
        self, market_validator, mock_mt5, mock_config_manager,
    ):
        """Test de verificación de spread demasiado amplio"""
        symbol = "XAUUSD"

        # Mock para devolver spread muy amplio
        with patch.object(market_validator.market_data, "get_spread", return_value=150.0):
            # Mock configuración de spread máximo
            with patch.object(mock_config_manager, "get", side_effect=lambda key, default=None: 50 if key == "MAX_SPREAD_POINTS" else default):
                is_acceptable, message = market_validator.check_spread(symbol)

                assert is_acceptable is False
                assert isinstance(message, str)
                assert "wide" in message.lower()

    def test_check_spread_mt5_errors(self, market_validator, mock_mt5):
        """Test de verificación de spread cuando MT5 falla"""
        symbol = "XAUUSD"

        # Test cuando symbol_info_tick falla
        mock_mt5.symbol_info_tick.return_value = None
        is_acceptable, message = market_validator.check_spread(symbol)
        assert is_acceptable is False

        # Test cuando symbol_info falla
        mock_mt5.symbol_info_tick.return_value = Mock(ask=2348.5, bid=2348.0)
        mock_mt5.symbol_info.return_value = None
        is_acceptable, message = market_validator.check_spread(symbol)
        assert is_acceptable is False

    def test_is_market_volatile_acceptable(self, market_validator, mock_mt5):
        """Test de verificación de volatilidad aceptable"""
        symbol = "XAUUSD"
        atr_threshold = 5.0

        # Mock para devolver ATR bajo (mercado estable)
        with patch.object(market_validator.market_data, "calculate_atr", return_value=1.5):
            is_stable, message = market_validator.is_market_volatile(symbol, atr_threshold)

            assert is_stable is True  # Mercado estable
            assert isinstance(message, str)

    def test_is_market_volatile_excessive(self, market_validator, mock_mt5):
        """Test de verificación de volatilidad excesiva"""
        symbol = "XAUUSD"
        atr_threshold = 2.0

        # Mock para devolver ATR alto (mercado volátil)
        with patch.object(market_validator.market_data, "calculate_atr", return_value=5.0):
            is_stable, message = market_validator.is_market_volatile(symbol, atr_threshold)

            assert is_stable is False  # Mercado volátil
            assert isinstance(message, str)
            assert "volatile" in message.lower()

    def test_is_market_volatile_insufficient_data(self, market_validator, mock_mt5):
        """Test de verificación de volatilidad con datos insuficientes"""
        symbol = "XAUUSD"
        atr_threshold = 5.0

        # Mock para devolver pocos datos (None)
        with patch.object(market_validator.market_data, "calculate_atr", return_value=None):
            is_stable, message = market_validator.is_market_volatile(symbol, atr_threshold)

            # Con pocos datos, debería considerarse estable por defecto
            assert is_stable is True
            assert isinstance(message, str)

    def test_has_recent_news_events_no_news(self, market_validator):
        """Test de verificación de eventos recientes (sin noticias)"""
        symbol = "XAUUSD"

        # Por ahora, retornamos False (sin eventos) ya que no tenemos
        # implementación de verificación de noticias
        has_events, message = market_validator.has_recent_news_events(symbol)

        assert has_events is False
        assert isinstance(message, str)

    def test_validate_price_action_normal(self, market_validator, mock_mt5):
        """Test de validación de acción de precios normal"""
        symbol = "XAUUSD"
        lookback = 20

        # Mock para datos de precio normales
        mock_rates = []
        base_price = 2345.0
        for i in range(lookback):
            price = base_price + (i * 0.5)  # Tendencia suave
            mock_rates.append(
                {
                    "open": price,
                    "high": price + 2,
                    "low": price - 2,
                    "close": price + 0.3,
                },
            )

        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        is_normal, message = market_validator.validate_price_action(symbol, lookback)

        assert is_normal is True
        assert isinstance(message, str)

    def test_validate_price_action_extreme_movement(self, market_validator, mock_mt5):
        """Test de validación de movimiento extremo de precios"""
        symbol = "XAUUSD"
        lookback = 10

        # Mock para movimiento extremo de precios
        mock_rates = []
        for i in range(lookback):
            if i < 5:
                # Precios normales
                mock_rates.append(
                    {"open": 2345.0, "high": 2347.0, "low": 2343.0, "close": 2345.5},
                )
            else:
                # Movimiento extremo
                mock_rates.append(
                    {
                        "open": 2345.5,
                        "high": 2380.0,  # +35 puntos de repente
                        "low": 2345.0,
                        "close": 2375.0,
                    },
                )

        mock_mt5.copy_rates_from_pos.return_value = mock_rates

        is_normal, message = market_validator.validate_price_action(symbol, lookback)

        assert is_normal is False
        assert isinstance(message, str)
        assert "extreme" in message.lower()

    def test_validate_price_action_insufficient_data(self, market_validator, mock_mt5):
        """Test de validación de acción de precios con datos insuficientes"""
        symbol = "XAUUSD"
        lookback = 20

        # Mock para pocos datos
        mock_mt5.copy_rates_from_pos.return_value = [{"open": 2345.0, "close": 2346.0}]

        is_normal, message = market_validator.validate_price_action(symbol, lookback)

        # Con pocos datos, debería considerarse normal por defecto
        assert is_normal is True
        assert isinstance(message, str)

    def test_is_liquidity_sufficient_good_volume(self, market_validator, mock_mt5):
        """Test de verificación de liquidez suficiente"""
        symbol = "XAUUSD"
        lookback = 20
        min_avg_volume = 50

        # Mock para volumen bueno
        with patch.object(market_validator.market_data, "get_volume_stats", return_value=(100.0, 100.0)):
            is_sufficient, message = market_validator.is_liquidity_sufficient(
                symbol, lookback, min_avg_volume,
            )

            assert is_sufficient is True
            assert isinstance(message, str)

    def test_is_liquidity_sufficient_low_volume(self, market_validator, mock_mt5):
        """Test de verificación de liquidez baja"""
        symbol = "XAUUSD"
        lookback = 20
        min_avg_volume = 100

        # Mock para volumen bajo
        with patch.object(market_validator.market_data, "get_volume_stats", return_value=(30.0, 30.0)):
            is_sufficient, message = market_validator.is_liquidity_sufficient(
                symbol, lookback, min_avg_volume,
            )

            assert is_sufficient is False
            assert isinstance(message, str)
            assert "insufficient" in message.lower()

    def test_is_liquidity_sufficient_insufficient_data(
        self, market_validator, mock_mt5,
    ):
        """Test de verificación de liquidez con datos insuficientes"""
        symbol = "XAUUSD"
        lookback = 20
        min_avg_volume = 50

        # Mock para pocos datos
        with patch.object(market_validator.market_data, "get_volume_stats", return_value=(None, None)):
            is_sufficient, message = market_validator.is_liquidity_sufficient(
                symbol, lookback, min_avg_volume,
            )

            # Con pocos datos, debería considerarse suficiente por defecto
            assert is_sufficient is True
            assert isinstance(message, str)

    def test_get_market_regime_normal(self, market_validator, mock_mt5):
        """Test de obtención de régimen de mercado normal"""
        symbol = "XAUUSD"
        period = 50

        # Mock para datos que indican régimen normal
        with patch.object(market_validator.market_data, "calculate_atr", return_value=0.001):
            regime, volatility = market_validator.get_market_regime(symbol, period)

            assert isinstance(regime, str)
            assert isinstance(volatility, float)
            assert regime in ["trending", "ranging", "volatile"]
            assert volatility >= 0

    def test_get_market_regime_mt5_error(self, market_validator, mock_mt5):
        """Test de régimen de mercado cuando MT5 falla"""
        symbol = "XAUUSD"
        period = 50

        # Mock para fallo en obtención de datos
        with patch.object(market_validator.market_data, "calculate_atr", return_value=None):
            regime, volatility = market_validator.get_market_regime(symbol, period)

            # Debería manejar el error gracefully
            assert regime == "ranging"  # Valor por defecto
            assert volatility == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
