# security_manager.py
"""
Security manager for RoboQuant trading system with credential management,
input validation, rate limiting, and error sanitization.
"""

import hmac
import ipaddress
import logging
import os
import re
import time
from functools import wraps
from typing import Any

from dotenv import load_dotenv

# Try to import keyring for encrypted credential storage
KEYRING_AVAILABLE = False
keyring = None
try:
    import importlib

    keyring = importlib.import_module("keyring")
    importlib.import_module("keyring.errors")
    KEYRING_AVAILABLE = True
except ImportError:
    logging.warning(
        "Keyring not available. Credentials will be stored in environment variables.",
    )

# Configure logging for security module
security_logger = logging.getLogger("security")
security_logger.setLevel(logging.INFO)
if not security_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - SECURITY - %(levelname)s - %(message)s",
    )
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)


class SecureCredentialManager:
    """Securely loads and manages credentials with encryption support."""

    def __init__(
        self, env_file_path: str | None = None, use_encryption: bool = True,
    ):
        """
        Initialize the credential manager.

        Args:
            env_file_path: Path to the .env file. If None, uses default loading behavior.
            use_encryption: Whether to use encrypted storage for credentials

        """
        self._credentials = {}
        self._use_encryption = use_encryption and KEYRING_AVAILABLE
        self._load_credentials(env_file_path)

    def _load_credentials(self, env_file_path: str | None = None) -> None:
        """Load credentials from environment variables or encrypted storage."""
        try:
            # Load environment variables without logging their values
            if env_file_path:
                load_dotenv(env_file_path)
            else:
                load_dotenv()

            # Store credential keys (not values) for validation
            credential_keys = [
                "MT5_LOGIN",
                "MT5_PASSWORD",
                "MT5_SERVER",
                "WEBHOOK_SECRET_KEY",
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID",
            ]

            for key in credential_keys:
                if self._use_encryption and keyring:
                    # Try to get from encrypted storage first
                    try:
                        value = keyring.get_password("roboquant", key)
                        if value is not None:
                            # Store only non-sensitive information about credentials
                            self._credentials[key] = {
                                "exists": True,
                                "length": len(value) if key != "MT5_LOGIN" else None,
                                "first_char": value[0]
                                if value and key not in ["MT5_LOGIN", "MT5_PASSWORD"]
                                else None,
                            }
                            continue
                    except Exception:
                        pass  # Fall back to environment variables

                # Fall back to environment variables
                value = os.getenv(key)
                if value is not None:
                    # Store only non-sensitive information about credentials
                    self._credentials[key] = {
                        "exists": True,
                        "length": len(value) if key != "MT5_LOGIN" else None,
                        "first_char": value[0]
                        if value and key not in ["MT5_LOGIN", "MT5_PASSWORD"]
                        else None,
                    }
                else:
                    self._credentials[key] = {"exists": False}

            security_logger.info("Credentials loaded securely")
        except Exception as e:
            security_logger.error("Failed to load credentials: %s", str(e))
            raise

    def get_credential(self, key: str) -> str | None:
        """
        Get a credential value by key.

        Args:
            key: The credential key to retrieve

        Returns:
            The credential value or None if not found

        """
        if self._use_encryption and keyring:
            # Try to get from encrypted storage first
            try:
                value = keyring.get_password("roboquant", key)
                if value is not None:
                    return value
            except Exception:
                pass  # Fall back to environment variables

        # Fall back to environment variables
        return os.getenv(key)

    def set_credential(self, key: str, value: str) -> bool:
        """
        Set a credential value securely.

        Args:
            key: The credential key to set
            value: The credential value to store

        Returns:
            True if successful, False otherwise

        """
        if self._use_encryption and keyring:
            try:
                keyring.set_password("roboquant", key, value)
                return True
            except Exception as e:
                security_logger.error(
                    "Failed to store credential in keyring: %s", str(e),
                )
                return False
        else:
            # For non-encrypted storage, we can't actually set environment variables
            # This is just for compatibility
            security_logger.warning(
                "Non-encrypted credential storage requested or keyring not available - not setting environment variable",
            )
            return False

    def credential_exists(self, key: str) -> bool:
        """
        Check if a credential exists.

        Args:
            key: The credential key to check

        Returns:
            True if the credential exists, False otherwise

        """
        return self._credentials.get(key, {}).get("exists", False)

    def validate_webhook_secret(self) -> bool:
        """
        Validate that the webhook secret key meets security requirements.

        Returns:
            True if valid, False otherwise

        """
        secret = self.get_credential("WEBHOOK_SECRET_KEY")
        if not secret:
            security_logger.error("WEBHOOK_SECRET_KEY not configured")
            return False

        if len(secret) < 32:
            security_logger.error("WEBHOOK_SECRET_KEY must be at least 32 characters")
            return False

        return True


class InputValidator:
    """Validates inputs for trading operations."""

    # Symbol validation regex (alphanumeric, underscores, dots, slashes)
    SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9_./]+$")

    # Price validation (positive numbers with up to 5 decimal places)
    PRICE_PATTERN = re.compile(r"^\d+(\.\d{1,5})?$")

    @classmethod
    def validate_symbol(cls, symbol: str) -> bool:
        """
        Validate a trading symbol.

        Args:
            symbol: The symbol to validate

        Returns:
            True if valid, False otherwise

        """
        if not symbol or not isinstance(symbol, str):
            return False

        if len(symbol) > 20:  # Reasonable limit for symbol length
            return False

        return bool(cls.SYMBOL_PATTERN.match(symbol))

    @classmethod
    def validate_volume(cls, volume: float | int | str) -> bool:
        """
        Validate a trading volume.

        Args:
            volume: The volume to validate

        Returns:
            True if valid, False otherwise

        """
        try:
            vol = float(volume)
            return 0 < vol <= 1000  # Reasonable limits for volume
        except (ValueError, TypeError):
            return False

    @classmethod
    def validate_price(cls, price: float | int | str) -> bool:
        """
        Validate a price value.

        Args:
            price: The price to validate

        Returns:
            True if valid, False otherwise

        """
        try:
            prc = float(price)
            return 0 < prc <= 1000000  # Reasonable limits for price
        except (ValueError, TypeError):
            return False

    @classmethod
    def validate_order_type(cls, order_type: str) -> bool:
        """
        Validate an order type.

        Args:
            order_type: The order type to validate

        Returns:
            True if valid, False otherwise

        """
        if not order_type or not isinstance(order_type, str):
            return False
        return order_type.upper() in ["BUY", "SELL"]

    @classmethod
    def sanitize_input(cls, data: Any) -> Any:
        """
        Sanitize input data to prevent injection attacks.

        Args:
            data: The data to sanitize

        Returns:
            Sanitized data

        """
        if isinstance(data, str):
            # Remove potentially dangerous characters
            sanitized = re.sub(r'[<>"\']', "", data)
            # Limit length
            return sanitized[:1000]
        if isinstance(data, (int, float)):
            return data
        if isinstance(data, dict):
            return {k: cls.sanitize_input(v) for k, v in data.items()}
        if isinstance(data, list):
            return [cls.sanitize_input(item) for item in data]
        return str(data)[:1000] if data is not None else None


class RateLimiter:
    """Rate limiter to prevent abuse of trading endpoints."""

    def __init__(self, max_requests: int = 10, time_window: int = 60):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed
            time_window: Time window in seconds

        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = {}  # Dictionary of IP -> list of timestamps
        self.global_requests = []  # List of all request timestamps for global limiting

    def is_allowed(self, ip_address: str | None = None) -> bool:
        """
        Check if a request is allowed based on rate limiting rules.

        Args:
            ip_address: IP address of the requester (optional)

        Returns:
            True if allowed, False if rate limited

        """
        now = time.time()

        # Global rate limiting
        self.global_requests = [
            req_time
            for req_time in self.global_requests
            if now - req_time < self.time_window
        ]
        if len(self.global_requests) >= self.max_requests:
            return False

        # Per-IP rate limiting
        if ip_address:
            # Initialize requests list for this IP if not exists
            if ip_address not in self.requests:
                self.requests[ip_address] = []

            # Remove old requests outside the time window
            self.requests[ip_address] = [
                req_time
                for req_time in self.requests[ip_address]
                if now - req_time < self.time_window
            ]

            # Check if we're under the limit
            if len(self.requests[ip_address]) >= self.max_requests:
                return False

            # Add the new request
            self.requests[ip_address].append(now)

        # Add to global requests
        self.global_requests.append(now)
        return True

    def get_retry_after(self) -> int:
        """
        Get the number of seconds to wait before the next allowed request.

        Returns:
            Seconds to wait

        """
        now = time.time()
        all_requests = self.global_requests[:]

        if not all_requests:
            return 0

        oldest_request = min(all_requests)
        return max(0, int(self.time_window - (now - oldest_request)))


def sanitize_error_message(error_msg: str) -> str:
    """
    Sanitize error messages to prevent information leakage.

    Args:
        error_msg: The error message to sanitize

    Returns:
        Sanitized error message

    """
    if not error_msg or not isinstance(error_msg, str):
        return "An error occurred"

    # Remove sensitive information
    sanitized = re.sub(
        r"[A-Za-z0-9]{10,}", "***", error_msg,
    )  # Remove long alphanumeric strings
    sanitized = re.sub(r"\d{5,}", "*****", sanitized)  # Remove long number sequences
    sanitized = re.sub(
        r"password|secret|key|token|login", "***", sanitized, flags=re.IGNORECASE,
    )

    # Limit length
    return sanitized[:500]


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string
        b: Second string

    Returns:
        True if strings are equal, False otherwise

    """
    return (
        hmac.compare_digest(a, b)
        if isinstance(a, str) and isinstance(b, str)
        else False
    )


def ip_whitelist(allowed_ips: list):
    """
    Decorator to restrict access based on IP whitelist.

    Args:
        allowed_ips: List of allowed IP addresses or networks

    Returns:
        Decorator function

    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the request object if available (for Flask routes)
            import flask

            if flask.has_request_context():
                client_ip = flask.request.remote_addr
                if client_ip is None:
                    security_logger.warning("Unable to determine client IP address")
                    return flask.jsonify(
                        {"error": "Unable to determine client IP"},
                    ), 403

                try:
                    client_ip_obj = ipaddress.ip_address(client_ip)
                    for allowed_ip in allowed_ips:
                        try:
                            allowed_network = ipaddress.ip_network(
                                allowed_ip, strict=False,
                            )
                            if client_ip_obj in allowed_network:
                                return func(*args, **kwargs)
                        except ValueError:
                            # If it's not a network, check if it's a single IP
                            if client_ip == allowed_ip:
                                return func(*args, **kwargs)
                except ValueError:
                    pass  # Invalid IP address

                security_logger.warning(f"Access denied from IP: {client_ip}")
                return flask.jsonify({"error": "Access denied"}), 403

            # If not in Flask context, allow access
            return func(*args, **kwargs)

        return wrapper

    return decorator
