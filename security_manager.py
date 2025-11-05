# security_manager.py
"""
Security manager for RoboQuant trading system with credential management,
input validation, rate limiting, and error sanitization.
"""

import os
import time
import logging
import re
from typing import Any, Dict, Optional, Union
from dotenv import load_dotenv
import hashlib
import hmac
import ipaddress
from functools import wraps

# Configure logging for security module
security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)
if not security_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - SECURITY - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    security_logger.addHandler(handler)


class SecureCredentialManager:
    """Securely loads and manages credentials without exposing them in logs."""
    
    def __init__(self, env_file_path: Optional[str] = None):
        """
        Initialize the credential manager.
        
        Args:
            env_file_path: Path to the .env file. If None, uses default loading behavior.
        """
        self._credentials = {}
        self._load_credentials(env_file_path)
    
    def _load_credentials(self, env_file_path: Optional[str] = None) -> None:
        """Load credentials from environment variables."""
        try:
            # Load environment variables without logging their values
            if env_file_path:
                load_dotenv(env_file_path)
            else:
                load_dotenv()
            
            # Store credential keys (not values) for validation
            credential_keys = [
                'MT5_LOGIN',
                'MT5_PASSWORD',
                'MT5_SERVER',
                'WEBHOOK_SECRET_KEY',
                'TELEGRAM_BOT_TOKEN',
                'TELEGRAM_CHAT_ID'
            ]
            
            for key in credential_keys:
                value = os.getenv(key)
                if value is not None:
                    # Store only non-sensitive information about credentials
                    self._credentials[key] = {
                        'exists': True,
                        'length': len(value) if key != 'MT5_LOGIN' else None,
                        'first_char': value[0] if value and key not in ['MT5_LOGIN', 'MT5_PASSWORD'] else None
                    }
                else:
                    self._credentials[key] = {'exists': False}
                    
            security_logger.info("Credentials loaded securely")
        except Exception as e:
            security_logger.error("Failed to load credentials: %s", str(e))
            raise
    
    def get_credential(self, key: str) -> Optional[str]:
        """
        Get a credential value by key.
        
        Args:
            key: The credential key to retrieve
            
        Returns:
            The credential value or None if not found
        """
        return os.getenv(key)
    
    def credential_exists(self, key: str) -> bool:
        """
        Check if a credential exists.
        
        Args:
            key: The credential key to check
            
        Returns:
            True if the credential exists, False otherwise
        """
        return self._credentials.get(key, {}).get('exists', False)
    
    def validate_webhook_secret(self) -> bool:
        """
        Validate that the webhook secret key meets security requirements.
        
        Returns:
            True if valid, False otherwise
        """
        secret = self.get_credential('WEBHOOK_SECRET_KEY')
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
    SYMBOL_PATTERN = re.compile(r'^[A-Za-z0-9_./]+$')
    
    # Price validation (positive numbers with up to 5 decimal places)
    PRICE_PATTERN = re.compile(r'^\d+(\.\d{1,5})?$')
    
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
    def validate_volume(cls, volume: Union[float, int, str]) -> bool:
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
    def validate_price(cls, price: Union[float, int, str]) -> bool:
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
        return order_type.upper() in ['BUY', 'SELL']
    
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
            sanitized = re.sub(r'[<>"\']', '', data)
            # Limit length
            return sanitized[:1000]
        elif isinstance(data, (int, float)):
            return data
        elif isinstance(data, dict):
            return {k: cls.sanitize_input(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [cls.sanitize_input(item) for item in data]
        else:
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
    
    def is_allowed(self, ip_address: Optional[str] = None) -> bool:
        """
        Check if a request is allowed based on rate limiting rules.
        
        Args:
            ip_address: IP address of the requester (optional)
            
        Returns:
            True if allowed, False if rate limited
        """
        # Use a default key if no IP provided
        key = ip_address if ip_address else "default"
        
        now = time.time()
        
        # Initialize requests list for this IP if not exists
        if key not in self.requests:
            self.requests[key] = []
        
        # Remove old requests outside the time window
        self.requests[key] = [req_time for req_time in self.requests[key] if now - req_time < self.time_window]
        
        # Check if we're under the limit
        if len(self.requests[key]) < self.max_requests:
            self.requests[key].append(now)
            return True
        else:
            return False
    
    def get_retry_after(self) -> int:
        """
        Get the number of seconds to wait before the next allowed request.
        
        Returns:
            Seconds to wait
        """
        now = time.time()
        all_requests = []
        for ip_requests in self.requests.values():
            all_requests.extend(ip_requests)
        
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
    sanitized = re.sub(r'[A-Za-z0-9]{10,}', '***', error_msg)  # Remove long alphanumeric strings
    sanitized = re.sub(r'\d{5,}', '*****', sanitized)  # Remove long number sequences
    sanitized = re.sub(r'password|secret|key|token|login', '***', sanitized, flags=re.IGNORECASE)
    
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
    return hmac.compare_digest(a, b) if isinstance(a, str) and isinstance(b, str) else False


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
                    return flask.jsonify({'error': 'Unable to determine client IP'}), 403
                    
                try:
                    client_ip_obj = ipaddress.ip_address(client_ip)
                    for allowed_ip in allowed_ips:
                        try:
                            allowed_network = ipaddress.ip_network(allowed_ip, strict=False)
                            if client_ip_obj in allowed_network:
                                return func(*args, **kwargs)
                        except ValueError:
                            # If it's not a network, check if it's a single IP
                            if client_ip == allowed_ip:
                                return func(*args, **kwargs)
                except ValueError:
                    pass  # Invalid IP address
                
                security_logger.warning(f"Access denied from IP: {client_ip}")
                return flask.jsonify({'error': 'Access denied'}), 403
            
            # If not in Flask context, allow access
            return func(*args, **kwargs)
        return wrapper
    return decorator
