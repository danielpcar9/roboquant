"""
MT5 Connection Manager - Singleton pattern for centralized connection handling
Eliminates duplication across the codebase and provides consistent error handling
"""

import logging
from typing import Optional, Tuple
from security_manager import SecureCredentialManager, sanitize_error_message
from error_handler import handle_exception, MT5ConnectionError

try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

logger = logging.getLogger(__name__)


class MT5ConnectionManager:
    """Singleton manager for MT5 connections"""

    _instance: Optional['MT5ConnectionManager'] = None
    _initialized: bool = False

    def __new__(cls) -> 'MT5ConnectionManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.credential_manager = SecureCredentialManager()
            self._is_connected = False
            MT5ConnectionManager._initialized = True

    @handle_exception
    def connect(self) -> bool:
        """
        Initialize MT5 connection with credentials

        Returns:
            bool: True if connection successful, False otherwise
        """
        if self._is_connected:
            logger.debug("MT5 already connected, skipping initialization")
            return True

        logger.info("Attempting to initialize MT5...")

        login = self.credential_manager.get_credential('MT5_LOGIN')
        password = self.credential_manager.get_credential('MT5_PASSWORD')
        server = self.credential_manager.get_credential('MT5_SERVER')

        if login and password and server:
            try:
                login_int = int(login)
                logger.info(f"Initializing MT5 with credentials for account {login_int} on server {server}")

                if not mt5.initialize(login=login_int, password=password, server=server):  # type: ignore
                    error = mt5.last_error()  # type: ignore
                    logger.error(f"MT5 initialization failed: {error}")
                    raise MT5ConnectionError(f"Failed to initialize MT5: {error}")

                self._is_connected = True
                logger.info("MT5 connection established successfully")
                return True

            except ValueError as e:
                error_msg = sanitize_error_message(str(e))
                logger.error(f"Invalid login format: {login}. Error: {error_msg}")
                raise MT5ConnectionError(f"Invalid credentials: {error_msg}")
        else:
            logger.info("No credentials provided, attempting to initialize without authentication")
            if not mt5.initialize():  # type: ignore
                error = mt5.last_error()  # type: ignore
                logger.error(f"MT5 initialization failed: {error}")
                raise MT5ConnectionError(f"Failed to initialize MT5: {error}")

            self._is_connected = True
            logger.info("MT5 initialized without credentials")
            return True

    def disconnect(self) -> None:
        """Close MT5 connection gracefully"""
        if self._is_connected:
            try:
                mt5.shutdown()  # type: ignore
                self._is_connected = False
                logger.info("MT5 connection closed")
            except Exception as e:
                logger.error(f"Error closing MT5 connection: {sanitize_error_message(str(e))}")

    def is_connected(self) -> bool:
        """Check if MT5 is connected"""
        return self._is_connected

    def select_symbol(self, symbol: str) -> bool:
        """
        Select a symbol for trading

        Args:
            symbol: Symbol to select (e.g., 'XAUUSD')

        Returns:
            bool: True if successful
        """
        if not self._is_connected:
            logger.error("MT5 not connected, cannot select symbol")
            return False

        try:
            if not mt5.symbol_select(symbol, True):  # type: ignore
                logger.error(f"Failed to select symbol {symbol}")
                return False
            logger.debug(f"Symbol {symbol} selected")
            return True
        except Exception as e:
            logger.error(f"Error selecting symbol {symbol}: {sanitize_error_message(str(e))}")
            return False

    def get_mt5_module(self):
        """Get the underlying MT5 module for direct access"""
        return mt5

    def __del__(self):
        """Cleanup on object destruction"""
        self.disconnect()


# Global instance accessor
def get_mt5_manager() -> MT5ConnectionManager:
    """Get the singleton MT5ConnectionManager instance"""
    return MT5ConnectionManager()
