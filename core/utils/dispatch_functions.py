"""
Funciones genéricas de despacho único para reemplazar if-else masivos
"""

from collections.abc import Callable
from functools import singledispatch
from typing import Any


@singledispatch
def calculate_stop_loss(
    order_type: str, price: float, sl_points: float, point: float,
) -> float:
    """
    Calcula el precio de stop loss basado en el tipo de orden

    Args:
        order_type: Tipo de orden ("BUY" o "SELL")
        price: Precio de entrada
        sl_points: Distancia del stop loss en puntos
        point: Valor de punto del símbolo

    Returns:
        float: Precio del stop loss

    """
    raise NotImplementedError(f"No implementation for order type: {order_type}")


@calculate_stop_loss.register
def _(order_type: str, price: float, sl_points: float, point: float) -> float:
    """Implementación para órdenes BUY"""
    if order_type.upper() == "BUY":
        return price - sl_points * point
    if order_type.upper() == "SELL":
        return price + sl_points * point
    raise ValueError(f"Invalid order type: {order_type}")


@singledispatch
def calculate_take_profit(
    order_type: str, price: float, tp_points: float, point: float,
) -> float:
    """
    Calcula el precio de take profit basado en el tipo de orden

    Args:
        order_type: Tipo de orden ("BUY" o "SELL")
        price: Precio de entrada
        tp_points: Distancia del take profit en puntos
        point: Valor de punto del símbolo

    Returns:
        float: Precio del take profit

    """
    raise NotImplementedError(f"No implementation for order type: {order_type}")


@calculate_take_profit.register
def _(order_type: str, price: float, tp_points: float, point: float) -> float:
    """Implementación para órdenes BUY"""
    if order_type.upper() == "BUY":
        return price + tp_points * point
    if order_type.upper() == "SELL":
        return price - tp_points * point
    raise ValueError(f"Invalid order type: {order_type}")


def market_regime_dispatcher(
    regime: str,
) -> Callable[[dict[str, Any]], tuple[bool, str]]:
    """
    Dispatcher para diferentes regímenes de mercado

    Args:
        regime: Tipo de régimen ("TRENDING", "RANGING", "UNKNOWN")

    Returns:
        Callable: Función que maneja el régimen específico

    """
    regime_handlers = {
        "TRENDING": lambda data: (
            True,
            f"Market is TRENDING (ADX: {data.get('adx_value', 0):.2f} > {data.get('adx_threshold', 20)}, proceeding with strategy",
        ),
        "RANGING": lambda data: (
            False,
            f"Market is RANGING (ADX: {data.get('adx_value', 0):.2f}), skipping trade",
        ),
        "UNKNOWN": lambda data: (False, "Unable to determine market regime"),
        "default": lambda data: (True, "Market regime check bypassed"),
    }

    return regime_handlers.get(regime.upper(), regime_handlers["default"])


def risk_management_dispatcher(
    condition: str,
) -> Callable[[dict[str, Any]], tuple[bool, str]]:
    """
    Dispatcher para diferentes condiciones de gestión de riesgo

    Args:
        condition: Tipo de condición ("SPREAD_HIGH", "NEWS_EVENT", "OUTSIDE_HOURS", "OK")

    Returns:
        Callable: Función que maneja la condición específica

    """
    risk_handlers = {
        "SPREAD_HIGH": lambda data: (
            False,
            f"Spread too high: {data.get('spread', 0):.2f} points > {data.get('max_spread', 20)} points",
        ),
        "NEWS_EVENT": lambda data: (
            False,
            "News event detected, skipping trade execution",
        ),
        "OUTSIDE_HOURS": lambda data: (False, "Outside trading hours"),
        "ACCOUNT_ERROR": lambda data: (False, "Failed to get account info"),
        "OK": lambda data: (True, "Risk conditions satisfied"),
        "default": lambda data: (True, "Risk check passed"),
    }

    return risk_handlers.get(condition.upper(), risk_handlers["default"])


def signal_generation_dispatcher(
    signal_type: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Dispatcher para diferentes tipos de señales de trading

    Args:
        signal_type: Tipo de señal ("BUY", "SELL", "NONE", "ERROR")

    Returns:
        Callable: Función que genera la respuesta de señal específica

    """
    signal_handlers = {
        "BUY": lambda data: {
            "should_enter": True,
            "direction": "BUY",
            "reason": "Price above upper channel",
        },
        "SELL": lambda data: {
            "should_enter": True,
            "direction": "SELL",
            "reason": "Price below lower channel",
        },
        "NONE": lambda data: {"should_enter": False, "reason": "No breakout signal"},
        "ERROR": lambda data: {
            "should_enter": False,
            "reason": f"Signal generation failed: {data.get('error', 'Unknown error')}",
        },
        "default": lambda data: {
            "should_enter": False,
            "reason": "Invalid signal type",
        },
    }

    return signal_handlers.get(signal_type.upper(), signal_handlers["default"])


def trade_execution_dispatcher(result: bool | None) -> tuple[bool, str]:
    """
    Dispatcher para resultados de ejecución de trades

    Args:
        result: Resultado de la ejecución del trade

    Returns:
        tuple: (success, message)

    """
    if result is True:
        return (True, "Trade executed successfully")
    if result is False:
        return (False, "Trade execution failed")
    if result is None:
        return (False, "Failed to execute trade - build_and_send_order returned None")
    return (False, f"Unexpected execution result: {result}")


def account_validation_dispatcher(account_info) -> tuple[bool, str]:
    """
    Dispatcher para validación de información de cuenta

    Args:
        account_info: Información de la cuenta de trading

    Returns:
        tuple: (is_valid, message)

    """
    if account_info is None:
        return (False, "Failed to get account info")
    if not hasattr(account_info, "balance"):
        return (False, "Account info missing balance attribute")
    if account_info.balance <= 0:
        return (False, "Account balance is zero or negative")
    return (True, f"Account validated - Balance: ${account_info.balance:.2f}")


# Funciones auxiliares para uso común
def handle_market_regime(
    regime: str, adx_value: float = 0, adx_threshold: float = 20,
) -> tuple[bool, str]:
    """
    Handler completo para regímenes de mercado

    Args:
        regime: Tipo de régimen
        adx_value: Valor ADX actual
        adx_threshold: Umbral ADX

    Returns:
        tuple: (should_trade, reason)

    """
    handler = market_regime_dispatcher(regime)
    return handler({"adx_value": adx_value, "adx_threshold": adx_threshold})


def handle_risk_condition(condition: str, **kwargs) -> tuple[bool, str]:
    """
    Handler completo para condiciones de riesgo

    Args:
        condition: Tipo de condición
        **kwargs: Parámetros adicionales

    Returns:
        tuple: (is_valid, reason)

    """
    handler = risk_management_dispatcher(condition)
    return handler(kwargs)


def handle_signal_generation(signal_type: str, **kwargs) -> dict[str, Any]:
    """
    Handler completo para generación de señales

    Args:
        signal_type: Tipo de señal
        **kwargs: Parámetros adicionales

    Returns:
        Dict: Respuesta de señal

    """
    handler = signal_generation_dispatcher(signal_type)
    return handler(kwargs)


def handle_trade_execution(result) -> tuple[bool, str]:
    """
    Handler completo para ejecución de trades

    Args:
        result: Resultado de ejecución

    Returns:
        tuple: (success, message)

    """
    return trade_execution_dispatcher(result)


def handle_account_validation(account_info) -> tuple[bool, str]:
    """
    Handler completo para validación de cuenta

    Args:
        account_info: Información de cuenta

    Returns:
        tuple: (is_valid, message)

    """
    return account_validation_dispatcher(account_info)
