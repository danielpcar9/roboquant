import os
import json
from typing import Any, Dict, List
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


class SetFileManager:
    """Manages configuration sets loaded from JSON files."""

    def __init__(self, config_dir: str = "config"):
        """
        Initialize the SetFileManager.

        Args:
            config_dir: Directory where configuration files are stored
        """
        self.config_dir = config_dir
        self.current_config = {}
        self.loaded_file = None

        # Ensure config directory exists
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
            logger.info(f"Created config directory: {self.config_dir}")

    def load_set_file(self, filename: str) -> Dict[str, Any]:
        """
        Load a configuration set from a JSON file.

        Args:
            filename: Name of the JSON file to load

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If the file doesn't exist
            json.JSONDecodeError: If the file is not valid JSON
            ValueError: If the configuration structure is invalid
        """
        filepath = os.path.join(self.config_dir, filename)

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Configuration file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(
                f"Invalid JSON in {filepath}: {str(e)}", e.doc, e.pos
            )

        # Validate configuration structure
        self._validate_config(config)

        self.current_config = config
        self.loaded_file = filename
        logger.info(f"Loaded configuration from {filename}")

        return config

    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using dot notation.

        Args:
            key_path: Dot-separated path to the configuration value (e.g., 'risk_management.risk_per_trade_pct')
            default: Default value to return if key is not found

        Returns:
            Configuration value or default if not found
        """
        keys = key_path.split(".")
        value = self.current_config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.debug(
                f"Configuration key '{key_path}' not found, returning default: {default}"
            )
            return default

    def list_available_sets(self) -> List[str]:
        """
        List all available configuration set files.

        Returns:
            List of JSON filenames in the config directory
        """
        if not os.path.exists(self.config_dir):
            return []

        try:
            files = [f for f in os.listdir(self.config_dir) if f.endswith(".json")]
            logger.info(f"Found {len(files)} configuration files")
            return files
        except OSError as e:
            logger.error(f"Error listing configuration files: {e}")
            return []

    def _validate_config(self, config: Dict[str, Any]) -> bool:
        """
        Validate the configuration structure.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if valid

        Raises:
            ValueError: If the configuration structure is invalid
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a dictionary")

        # Basic structure validation - ensure required sections exist
        required_sections = []  # No required sections for now, but can be added

        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        logger.debug("Configuration validation passed")
        return True


# Global instance for easy access
_set_manager_instance = None


def get_set_manager() -> SetFileManager:
    """
    Get the global SetFileManager instance.

    Returns:
        SetFileManager instance
    """
    global _set_manager_instance
    if _set_manager_instance is None:
        _set_manager_instance = SetFileManager()
    return _set_manager_instance
