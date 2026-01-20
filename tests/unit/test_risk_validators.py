"""
Tests unitarios para RiskValidator
"""

import pytest
from unittest.mock import Mock


class TestRiskValidator:
    """Suite de tests para RiskValidator"""

    @pytest.fixture
    def risk_validator(self, mock_mt5, technical_calculator):
        """Fixture para crear instancia de RiskValidator"""
        from core.donchian_components.validators.risk_market_validators import (
            RiskValidator,
        )

        return RiskValidator(
            market_data_service=technical_calculator, mt5_module=mock_mt5
        )

    def test_init_with_custom_mt5(self, mock_mt5, technical_calculator):
        """Test de inicialización con módulo MT5 personalizado"""
        from core.donchian_components.validators.risk_market_validators import (
            RiskValidator,
        )

        validator = RiskValidator(
            market_data_service=technical_calculator, mt5_module=mock_mt5
        )

        assert validator.mt5 == mock_mt5
        assert validator.market_data == technical_calculator

    def test_calculate_dynamic_stops_buy_order(self, risk_validator, mock_mt5):
        """Test de cálculo de stops dinámicos para orden BUY"""
        symbol = "XAUUSD"
        entry_price = 2345.0
        order_type = "BUY"
        atr = 2.5

        sl, tp = risk_validator.calculate_dynamic_stops(
            symbol, entry_price, order_type, atr
        )

        # Para BUY: SL debe ser menor que entry_price, TP mayor
        assert sl < entry_price
        assert tp > entry_price
        assert isinstance(sl, float)
        assert isinstance(tp, float)

    def test_calculate_dynamic_stops_sell_order(self, risk_validator, mock_mt5):
        """Test de cálculo de stops dinámicos para orden SELL"""
        symbol = "XAUUSD"
        entry_price = 2345.0
        order_type = "SELL"
        atr = 2.5

        sl, tp = risk_validator.calculate_dynamic_stops(
            symbol, entry_price, order_type, atr
        )

        # Para SELL: SL debe ser mayor que entry_price, TP menor
        assert sl > entry_price
        assert tp < entry_price
        assert isinstance(sl, float)
        assert isinstance(tp, float)

    def test_calculate_dynamic_stops_with_zero_atr(self, risk_validator):
        """Test de stops dinámicos con ATR cero"""
        symbol = "XAUUSD"
        entry_price = 2345.0
        order_type = "BUY"
        atr = 0.0

        sl, tp = risk_validator.calculate_dynamic_stops(
            symbol, entry_price, order_type, atr
        )

        # Con ATR cero, debería usar valores mínimos por defecto
        assert sl != entry_price  # No deberían ser iguales
        assert tp != entry_price
        assert isinstance(sl, float)
        assert isinstance(tp, float)

    def test_compute_lot_size_normal_conditions(self, risk_validator, mock_mt5):
        """Test de cálculo de tamaño de lote en condiciones normales"""
        balance = 10000.0
        risk_pct = 1.0  # 1% de riesgo
        sl_distance = 20.0  # 20 puntos de stop loss
        symbol = "XAUUSD"

        lot_size = risk_validator.compute_lot_size(
            balance, risk_pct, sl_distance, symbol
        )

        # El tamaño debe ser positivo y razonable
        assert isinstance(lot_size, float)
        assert lot_size > 0
        assert lot_size <= 100.0  # Límite razonable

    def test_compute_lot_size_zero_balance(self, risk_validator):
        """Test de cálculo de lote con balance cero"""
        balance = 0.0
        risk_pct = 1.0
        sl_distance = 20.0
        symbol = "XAUUSD"

        lot_size = risk_validator.compute_lot_size(
            balance, risk_pct, sl_distance, symbol
        )

        # Con balance cero, debería retornar tamaño mínimo
        assert lot_size >= 0.01  # Tamaño mínimo típico

    def test_compute_lot_size_zero_sl_distance(self, risk_validator):
        """Test de cálculo de lote con distancia de SL cero"""
        balance = 10000.0
        risk_pct = 1.0
        sl_distance = 0.0
        symbol = "XAUUSD"

        lot_size = risk_validator.compute_lot_size(
            balance, risk_pct, sl_distance, symbol
        )

        # Con SL distance cero, debería manejarlo gracefulmente
        assert isinstance(lot_size, float)
        assert lot_size > 0

    def test_compute_lot_size_high_risk(self, risk_validator):
        """Test de cálculo de lote con alto porcentaje de riesgo"""
        balance = 10000.0
        risk_pct = 5.0  # 5% de riesgo (alto)
        sl_distance = 20.0
        symbol = "XAUUSD"

        lot_size = risk_validator.compute_lot_size(
            balance, risk_pct, sl_distance, symbol
        )

        # El tamaño debería ser mayor con más riesgo
        assert isinstance(lot_size, float)
        assert lot_size > 0

    def test_validate_stop_loss_distance_valid(self, risk_validator):
        """Test de validación de distancia de stop loss válida"""
        sl_points = 25.0
        symbol = "XAUUSD"

        is_valid, message = risk_validator.validate_stop_loss_distance(
            sl_points, symbol
        )

        assert is_valid is True
        assert isinstance(message, str)
        assert len(message) > 0

    def test_validate_stop_loss_distance_too_small(self, risk_validator):
        """Test de validación de stop loss demasiado pequeño"""
        sl_points = 2.0  # Muy pequeño
        symbol = "XAUUSD"

        is_valid, message = risk_validator.validate_stop_loss_distance(
            sl_points, symbol
        )

        # Podría ser válido o no dependiendo de la configuración
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

    def test_validate_take_profit_ratio_valid(self, risk_validator):
        """Test de validación de ratio TP/SL válido"""
        tp_points = 60.0
        sl_points = 30.0

        is_valid, message = risk_validator.validate_take_profit_ratio(
            tp_points, sl_points
        )

        assert is_valid is True
        assert isinstance(message, str)

    def test_validate_take_profit_ratio_too_low(self, risk_validator):
        """Test de validación de ratio TP/SL muy bajo"""
        tp_points = 15.0  # Ratio 1:2, podría ser bajo
        sl_points = 30.0

        is_valid, message = risk_validator.validate_take_profit_ratio(
            tp_points, sl_points
        )

        # Dependiendo de configuración, podría ser válido o no
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

    def test_validate_take_profit_ratio_zero_sl(self, risk_validator):
        """Test de validación de ratio con SL cero"""
        tp_points = 60.0
        sl_points = 0.0

        is_valid, message = risk_validator.validate_take_profit_ratio(
            tp_points, sl_points
        )

        # Con SL cero, debería manejarlo
        assert isinstance(is_valid, bool)
        assert isinstance(message, str)

    def test_check_account_risk_limits_within_limits(self, risk_validator, mock_mt5):
        """Test de verificación de límites de riesgo dentro de límites"""
        balance = 10000.0
        risk_amount = 100.0  # 1% del balance
        max_risk_percent = 2.0

        is_within_limits, message = risk_validator.check_account_risk_limits(
            balance, risk_amount, max_risk_percent
        )

        assert is_within_limits is True
        assert isinstance(message, str)

    def test_check_account_risk_limits_exceeds_limits(self, risk_validator):
        """Test de verificación de límites de riesgo excedidos"""
        balance = 10000.0
        risk_amount = 300.0  # 3% del balance, excede 2%
        max_risk_percent = 2.0

        is_within_limits, message = risk_validator.check_account_risk_limits(
            balance, risk_amount, max_risk_percent
        )

        assert is_within_limits is False
        assert isinstance(message, str)
        assert "exceeds" in message.lower()

    def test_get_account_exposure_no_positions(self, risk_validator, mock_mt5):
        """Test de obtención de exposición con ninguna posición"""
        # Mock para devolver lista vacía de posiciones
        mock_mt5.positions_get.return_value = []

        exposure = risk_validator.get_account_exposure()

        assert exposure == 0.0

    def test_get_account_exposure_with_positions(self, risk_validator, mock_mt5):
        """Test de obtención de exposición con posiciones abiertas"""
        # Mock para devolver posiciones
        mock_positions = [
            Mock(volume=1.0, type=0),  # BUY position
            Mock(volume=0.5, type=1),  # SELL position
        ]
        mock_mt5.positions_get.return_value = mock_positions

        exposure = risk_validator.get_account_exposure()

        # Debería calcular la exposición total
        assert isinstance(exposure, float)
        assert exposure >= 0.0

    def test_get_account_exposure_mt5_error(self, risk_validator, mock_mt5):
        """Test de exposición cuando MT5 falla"""
        mock_mt5.positions_get.return_value = None

        exposure = risk_validator.get_account_exposure()

        # Debería manejar el error gracefully
        assert exposure == 0.0

    def test_validate_position_sizing_valid(self, risk_validator):
        """Test de validación de sizing de posición válida"""
        lot_size = 1.0
        max_lot_size = 5.0
        min_lot_size = 0.01

        is_valid, message = risk_validator.validate_position_sizing(
            lot_size, max_lot_size, min_lot_size
        )

        assert is_valid is True
        assert isinstance(message, str)

    def test_validate_position_sizing_too_large(self, risk_validator):
        """Test de validación de sizing demasiado grande"""
        lot_size = 10.0  # Mayor que máximo permitido
        max_lot_size = 5.0
        min_lot_size = 0.01

        is_valid, message = risk_validator.validate_position_sizing(
            lot_size, max_lot_size, min_lot_size
        )

        assert is_valid is False
        assert isinstance(message, str)
        assert "maximum" in message.lower()

    def test_validate_position_sizing_too_small(self, risk_validator):
        """Test de validación de sizing demasiado pequeño"""
        lot_size = 0.001  # Menor que mínimo permitido
        max_lot_size = 5.0
        min_lot_size = 0.01

        is_valid, message = risk_validator.validate_position_sizing(
            lot_size, max_lot_size, min_lot_size
        )

        assert is_valid is False
        assert isinstance(message, str)
        assert "minimum" in message.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
