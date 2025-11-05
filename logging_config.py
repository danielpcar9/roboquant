"""
Centralized logging configuration for RoboQuant trading system
Provides structured logging with proper formatting and rotation
"""

import logging
import logging.handlers
import os
from datetime import datetime


class LoggerSetup:
    """Centralized logger configuration"""

    _configured = False

    @classmethod
    def setup(cls, name: str = "RoboQuant", level=logging.INFO) -> logging.Logger:
        """
        Configure and return a logger instance

        Args:
            name: Logger name
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Returns:
            Configured logger instance
        """
        logger = logging.getLogger(name)

        if cls._configured:
            return logger

        # Create logs directory if it doesn't exist
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)

        # Set logger level
        logger.setLevel(level)

        # Clear existing handlers to avoid duplicates
        logger.handlers.clear()

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # File handler with rotation
        log_file = os.path.join(log_dir, f'roboquant_{datetime.now().strftime("%Y%m%d")}.log')
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Error file handler
        error_log_file = os.path.join(log_dir, f'roboquant_errors_{datetime.now().strftime("%Y%m%d")}.log')
        error_handler = logging.FileHandler(error_log_file)
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        logger.addHandler(error_handler)

        cls._configured = True
        logger.info(f"Logger {name} initialized successfully")

        return logger


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance"""
    return LoggerSetup.setup(name)
