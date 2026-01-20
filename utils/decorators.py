"""
Decoradores comunes para el proyecto RoboQuant
"""

import functools
import logging
import time
from typing import Any, Callable


def handle_exception(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorador para manejar excepciones de manera uniforme

    Args:
        func: Función a decorar

    Returns:
        Función decorada con manejo de excepciones
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            func_name = getattr(func, "__name__", "unknown")
            logging.error(f"Error in {func_name}: {str(e)}", exc_info=True)
            # Relanzar la excepción para que pueda ser manejada por el código llamador
            raise

    return wrapper


def performance_monitor(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorador para monitorear el rendimiento de funciones

    Args:
        func: Función a decorar

    Returns:
        Función decorada con monitoreo de rendimiento
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            func_name = getattr(func, "__name__", "unknown")
            logging.debug(f"{func_name} executed in {execution_time:.4f} seconds")
            return result
        except Exception:
            execution_time = time.time() - start_time
            func_name = getattr(func, "__name__", "unknown")
            logging.error(f"{func_name} failed after {execution_time:.4f} seconds")
            raise

    return wrapper
