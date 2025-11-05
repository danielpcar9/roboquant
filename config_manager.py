# config_manager.py
"""
Centralized configuration management for RoboQuant trading system.
"""

import os
from typing import Any, Optional
from security_manager import SecureCredentialManager

class ConfigManager:
    """Manages all configuration parameters for the trading system."""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._credential_manager = SecureCredentialManager()
            self._config = {}
            self._load_config()
            ConfigManager._initialized = True
    
    def _load_config(self):
        """Load all configuration parameters."""
        # Trading parameters
        self._config.update({
            'DONCHIAN_PERIOD': int(os.getenv('DONCHIAN_PERIOD', '50')),
            'MOMENTUM_PERIOD': int(os.getenv('MOMENTUM_PERIOD', '40')),
            'SAMPLE_PERIOD': int(os.getenv('SAMPLE_PERIOD', '1000')),
            'RISK_PERCENT': float(os.getenv('RISK_PERCENT', '1.0')),
            'USE_RISK_MANAGEMENT': os.getenv('USE_RISK_MANAGEMENT', 'True').lower() == 'true',
            'LOTS': float(os.getenv('LOTS', '0.01')),
            'STOP_LOSS_POINTS': int(os.getenv('STOP_LOSS_POINTS', '150')),
            'TAKE_PROFIT_POINTS': int(os.getenv('TAKE_PROFIT_POINTS', '300')),
            'MAX_SPREAD_POINTS': int(os.getenv('MAX_SPREAD_POINTS', '150')),
            'TRADING_HOUR_START': int(os.getenv('TRADING_HOUR_START', '13')),
            'TRADING_HOUR_END': int(os.getenv('TRADING_HOUR_END', '22')),
            'MAGIC_NUMBER': int(os.getenv('MAGIC_NUMBER', '123456')),
            
            # Event-driven trading parameters
            'EVENT_WAIT_CANDLES': int(os.getenv('EVENT_WAIT_CANDLES', '3')),
            'EVENT_SIZE_FACTOR': float(os.getenv('EVENT_SIZE_FACTOR', '0.25')),
            'EVENT_SL_ATR_MULTIPLIER': float(os.getenv('EVENT_SL_ATR_MULTIPLIER', '2.5')),
            'EVENT_BREAKOUT_ATR_THRESHOLD': float(os.getenv('EVENT_BREAKOUT_ATR_THRESHOLD', '0.3')),
            'EVENT_VOLUME_SPIKE_FACTOR': float(os.getenv('EVENT_VOLUME_SPIKE_FACTOR', '1.7')),
            
            # Webhook parameters
            'WEBHOOK_PORT': int(os.getenv('WEBHOOK_PORT', '5000')),
            'WEBHOOK_HOST': os.getenv('WEBHOOK_HOST', '0.0.0.0'),
            
            # ML Engine parameters
            'ML_ENABLED': os.getenv('ML_ENABLED', 'False').lower() == 'true',
            'ML_MODEL_PATH': os.getenv('ML_MODEL_PATH', 'models/trading_model.json'),
            'ML_TRAINING_DATA_PATH': os.getenv('ML_TRAINING_DATA_PATH', 'data/training_data.csv'),
            
            # Backtesting parameters
            'BACKTEST_INITIAL_CAPITAL': float(os.getenv('BACKTEST_INITIAL_CAPITAL', '10000.0')),
            'BACKTEST_DAYS_BACK': int(os.getenv('BACKTEST_DAYS_BACK', '1825')),  # ~5 years
            
            # Performance dashboard parameters
            'DASHBOARD_OUTPUT_FILE': os.getenv('DASHBOARD_OUTPUT_FILE', 'dashboard.html'),
            
            # API Cache parameters
            'CACHE_TTL': int(os.getenv('CACHE_TTL', '1800')),  # 30 minutes
            'CACHE_FILE_PATH': os.getenv('CACHE_FILE_PATH', 'data/api_cache.json'),
        })
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    def get_credential(self, key: str) -> Optional[str]:
        """
        Get a credential value.
        
        Args:
            key: Credential key
            
        Returns:
            Credential value or None if not found
        """
        return self._credential_manager.get_credential(key)
    
    def set_credential(self, key: str, value: str) -> bool:
        """
        Set a credential value securely.
        
        Args:
            key: Credential key
            value: Credential value
            
        Returns:
            True if successful, False otherwise
        """
        return self._credential_manager.set_credential(key, value)
    
    def validate_webhook_secret(self) -> bool:
        """
        Validate webhook secret key.
        
        Returns:
            True if valid, False otherwise
        """
        return self._credential_manager.validate_webhook_secret()

# Global configuration manager instance
config_manager = ConfigManager()