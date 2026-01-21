#!/usr/bin/env python3
"""
Script to test current risk configuration
"""

import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.config_manager import config_manager
from config.set_file_manager import get_set_manager


def test_risk_configuration():
    print("=" * 50)
    print("TESTING CURRENT RISK CONFIGURATION")
    print("=" * 50)

    # Test config_manager values
    print("\n1. ConfigManager values:")
    risk_percent = config_manager.get("RISK_PERCENT", "NOT_FOUND")
    print(f"   RISK_PERCENT: {risk_percent}")

    # Test set file manager
    print("\n2. SetFileManager values:")
    try:
        cfg = get_set_manager()

        # Check what set file is being used
        set_file_env = os.getenv("ROBOQUANT_SET_FILE")
        print(f"   ROBOQUANT_SET_FILE env var: {set_file_env}")

        # Try to load default configuration
        if set_file_env:
            cfg.load_set_file(set_file_env)
            print(f"   Loaded set file: {set_file_env}")
        else:
            # Try to load default.json
            try:
                cfg.load_set_file("default.json")
                print("   Loaded set file: default.json")
            except FileNotFoundError:
                print("   default.json not found")

        # Get risk configuration
        risk_from_set = cfg.get("risk_management.risk_per_trade_pct", "NOT_FOUND")
        print(f"   risk_management.risk_per_trade_pct: {risk_from_set}")

    except Exception as e:
        print(f"   Error testing set manager: {e}")

    print("\n" + "=" * 50)

if __name__ == "__main__":
    test_risk_configuration()
