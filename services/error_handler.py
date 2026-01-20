# error_handler.py
"""
Error handling framework for RoboQuant trading system with custom exceptions,
circuit breaker pattern, and retry logic.
"""

import time
import logging
import os
from enum import Enum
from typing import Optional, Callable, Any, Type, Tuple, Union
from functools import wraps
import random
import traceback
import json

# Configure logging for error handling
error_logger = logging.getLogger('error_handling')
error_logger.setLevel(logging.INFO)
if not error_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - ERROR_HANDLING - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    error_logger.addHandler(handler)


# Custom Exception Hierarchy
class RoboQuantError(Exception):
    """Base exception for all RoboQuant errors."""
    pass


class MT5ConnectionError(RoboQuantError):
    """Exception raised when MT5 connection fails."""
    pass


class OrderExecutionError(RoboQuantError):
    """Exception raised when order execution fails."""
    def __init__(self, message: str, retcode: Optional[int] = None):
        super().__init__(message)
        self.retcode = retcode


class SafetyViolationError(RoboQuantError):
    """Exception raised when safety checks fail."""
    def __init__(self, message: str, violation_type: str):
        super().__init__(message)
        self.violation_type = violation_type


class CircuitBreakerError(RoboQuantError):
    """Exception raised when circuit breaker is open."""
    pass


class ConfigurationError(RoboQuantError):
    """Exception raised when configuration is invalid."""
    pass


class DataError(RoboQuantError):
    """Exception raised when data processing fails."""
    pass


class NetworkError(RoboQuantError):
    """Exception raised when network operations fail."""
    pass


class CircuitState(Enum):
    """States for the circuit breaker."""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, requests are allowed
    - OPEN: Failure threshold exceeded, requests are blocked
    - HALF_OPEN: Testing if service is restored
    """

    def __init__(self,
                 failure_threshold: int = 3,
                 timeout: int = 60,
                 expected_exception: Union[Type[Exception], Tuple[Type[Exception], ...]] = Exception):
        """
        Initialize the circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time in seconds before attempting to close circuit
            expected_exception: Exception type(s) that trigger circuit breaker
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call a function through the circuit breaker.
        
        Args:
            func: Function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            Result of the function call
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Any exception raised by the function (if circuit allows it)
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            # Check if this exception matches our expected exception types
            if isinstance(e, self.expected_exception) or \
               (isinstance(self.expected_exception, tuple) and isinstance(e, self.expected_exception)):
                self._on_failure()
                raise e
            else:
                # Re-raise unexpected exceptions without changing circuit state
                raise e

    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit."""
        if self.last_failure_time is None:
            return False
        return time.time() - self.last_failure_time >= self.timeout

    def _on_success(self) -> None:
        """Handle successful operation."""
        self.failure_count = 0
        self.last_failure_time = None
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
            error_logger.info("Circuit breaker closed after successful operation")

    def _on_failure(self) -> None:
        """Handle failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            error_logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.state == CircuitState.CLOSED

    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.state == CircuitState.HALF_OPEN

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state


def retry_with_exponential_backoff(max_retries: int = 3,
                                 base_delay: float = 1.0,
                                 max_delay: float = 60.0,
                                 exceptions: Tuple[Type[Exception], ...] = (Exception,)):
    """
    Decorator for retrying function calls with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied by 2^attempt)
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions that trigger retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception: Optional[Exception] = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        # Calculate delay with exponential backoff and jitter
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.1)  # 10% jitter
                        total_delay = delay + jitter

                        error_logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {total_delay:.2f} seconds..."
                        )

                        time.sleep(total_delay)
                    else:
                        error_logger.error(
                            f"All {max_retries + 1} attempts failed for {func.__name__}: {str(e)}"
                        )
                        error_logger.debug(
                            f"Full traceback:\n{traceback.format_exc()}"
                        )

            # If we get here, all retries failed
            if last_exception is not None:
                raise last_exception
            else:
                raise RuntimeError("All retry attempts failed but no exception was captured")
        return wrapper
    return decorator


# Predefined circuit breakers for common MT5 operations
mt5_connection_circuit = CircuitBreaker(
    failure_threshold=3,
    timeout=60,
    expected_exception=MT5ConnectionError
)

order_execution_circuit = CircuitBreaker(
    failure_threshold=5,
    timeout=30,
    expected_exception=OrderExecutionError
)

market_data_circuit = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    expected_exception=(ConnectionError, TimeoutError)
)

webhook_circuit = CircuitBreaker(
    failure_threshold=3,
    timeout=30,
    expected_exception=(NetworkError, ConnectionError, TimeoutError)
)


def safe_mt5_call(func: Callable):
    """
    Decorator to wrap MT5 calls with circuit breaker and retry logic.
    
    Args:
        func: MT5 function to wrap
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Determine which circuit breaker to use based on function name
        if 'initialize' in func.__name__ or 'login' in func.__name__:
            circuit = mt5_connection_circuit
        elif 'order' in func.__name__ or 'position' in func.__name__:
            circuit = order_execution_circuit
        else:
            circuit = market_data_circuit

        # Wrap with retry logic and circuit breaker
        @retry_with_exponential_backoff(
            max_retries=3,
            base_delay=1.0,
            max_delay=30.0,
            exceptions=(MT5ConnectionError, OrderExecutionError, ConnectionError, TimeoutError)
        )
        def protected_call():
            return circuit.call(func, *args, **kwargs)

        return protected_call()

    return wrapper


def handle_exception(func: Callable):
    """
    Decorator to provide centralized exception handling.
    
    Args:
        func: Function to wrap with exception handling
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ConfigurationError as e:
            error_logger.error(f"Configuration error in {func.__name__}: {str(e)}")
            raise
        except SafetyViolationError as e:
            error_logger.error(f"Safe violation in {func.__name__}: {str(e)}")
            raise
        except MT5ConnectionError as e:
            error_logger.error(f"MT5 connection error in {func.__name__}: {str(e)}")
            raise
        except OrderExecutionError as e:
            error_logger.error(f"Order execution error in {func.__name__}: {str(e)}")
            raise
        except CircuitBreakerError as e:
            error_logger.error(f"Circuit breaker error in {func.__name__}: {str(e)}")
            raise
        except DataError as e:
            error_logger.error(f"Data error in {func.__name__}: {str(e)}")
            raise
        except NetworkError as e:
            error_logger.error(f"Network error in {func.__name__}: {str(e)}")
            raise
        except Exception as e:
            error_logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            error_logger.debug(f"Full traceback:\n{traceback.format_exc()}")
            raise

    return wrapper


# Error mapping for common MT5 return codes
MT5_ERROR_CODES = {
    10001: "No error returned",
    10002: "Wrong parameters",
    10003: "Trading prohibited",
    10004: "Account disabled",
    10005: "Not enough money",
    10006: "Price changed",
    10007: "Off quotes",
    10008: "Order locked",
    10009: "Too many requests",
    10010: "No changes",
    10011: "Order activated",
    10012: "Order deactivated",
    10013: "Order deleted",
    10014: "Order closed",
    10015: "Order converted",
    10016: "Invalid stops",
    10017: "Invalid trade parameters",
    10018: "Server busy",
    10019: "Invalid account",
    10020: "Trade timeout",
    10021: "Order double",
    10022: "Invalid volume",
    10023: "Invalid price",
    10024: "Invalid stops level",
    10025: "Low margin",
    10026: "Market closed",
    10027: "Trade disabled",
    10028: "Insufficient funds",
    10029: "Price timeout",
    10030: "Unsupported filling mode",
    10031: "Invalid order total net volume",
    10032: "Incorrect series array flags",
    10033: "Incorrect data type",
    10034: "Incorrect history data request",
    10035: "Invalid trade operation",
    10036: "Invalid trade type",
    10037: "Invalid order expiration",
    10038: "Order locked by pending order",
    10039: "Invalid order modification",
    10040: "Invalid close volume",
    10041: "Invalid trade operation for position",
    10042: "Invalid trade operation for order",
    10043: "Invalid trade operation for symbol",
    10044: "Invalid trade operation for account",
    10045: "Invalid trade operation for group",
    10046: "Invalid trade operation for margin",
    10047: "Invalid trade operation for commission",
    10048: "Invalid trade operation for swap",
    10049: "Invalid trade operation for profit",
    10050: "Invalid trade operation for spread",
    10051: "Invalid trade operation for digits",
    10052: "Invalid trade operation for stop level",
    10053: "Invalid trade operation for expiration",
    10054: "Invalid trade operation for freeze level",
    10055: "Invalid trade operation for lot step",
    10056: "Invalid trade operation for lot minimum",
    10057: "Invalid trade operation for lot maximum",
    10058: "Invalid trade operation for contract size",
    10059: "Invalid trade operation for tick value",
    10060: "Invalid trade operation for tick size",
    10061: "Invalid trade operation for profit calculation mode",
    10062: "Invalid trade operation for margin calculation mode",
    10063: "Invalid trade operation for swap calculation mode",
    10064: "Invalid trade operation for commission calculation mode",
    10065: "Invalid trade operation for alligator calculation mode",
    10066: "Invalid trade operation for bands calculation mode",
    10067: "Invalid trade operation for fractals calculation mode",
    10068: "Invalid trade operation for ichimoku calculation mode",
    10069: "Invalid trade operation for ma calculation mode",
    10070: "Invalid trade operation for macd calculation mode",
    10071: "Invalid trade operation for momentum calculation mode",
    10072: "Invalid trade operation for oscillator calculation mode",
    10073: "Invalid trade operation for rsi calculation mode",
    10074: "Invalid trade operation for sar calculation mode",
    10075: "Invalid trade operation for stochastics calculation mode",
    10076: "Invalid trade operation for wpr calculation mode"
}


def log_error_to_file(error_info: dict, log_file: str = "error_log.json"):
    """
    Log error information to a JSON file for later analysis.
    
    Args:
        error_info: Dictionary containing error information
        log_file: Path to the log file
    """
    try:
        # Read existing log file if it exists
        existing_logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                try:
                    existing_logs = json.load(f)
                except json.JSONDecodeError:
                    existing_logs = []

        # Add new error info
        existing_logs.append(error_info)

        # Keep only the last 1000 errors to prevent file from growing too large
        if len(existing_logs) > 1000:
            existing_logs = existing_logs[-1000:]

        # Write back to file
        with open(log_file, 'w') as f:
            json.dump(existing_logs, f, indent=2)
    except Exception as e:
        error_logger.error(f"Failed to log error to file: {e}")
