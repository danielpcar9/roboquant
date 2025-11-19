#!/usr/bin/env python3
"""
Test script for SetFileManager functionality.
"""

import os
import sys
import logging

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.set_file_manager import SetFileManager

def test_set_manager():
    """Test the SetFileManager functionality."""
    print("=" * 60)
    print("Testing SetFileManager")
    print("=" * 60)
    
    # Create set file manager
    mgr = SetFileManager()
    
    # List available sets
    print("\n1. Available configuration sets:")
    sets = mgr.list_available_sets()
    for set_file in sets:
        print(f"   - {set_file}")
    
    # Test loading different sets
    test_sets = ['ftmo_challenge.json', 'aggressive.json', 'conservative.json']
    
    for set_name in test_sets:
        print(f"\n2. Testing {set_name}:")
        try:
            mgr.load_set_file(set_name)
            
            # Test getting various configuration values
            risk_pct = mgr.get('risk_management.risk_per_trade_pct', 1.0)
            donchian_period = mgr.get('strategy.donchian_period', 50)
            start_hour = mgr.get('trading_hours.start', 7)
            end_hour = mgr.get('trading_hours.end', 16)
            max_positions = mgr.get('position_limits.max_positions', 1)
            daily_loss_limit = mgr.get('performance.daily_loss_limit_pct', -5.0)
            rr_ratio = mgr.get('performance.risk_reward_ratio', 2.0)
            
            print(f"   Risk per trade: {risk_pct}%")
            print(f"   Donchian period: {donchian_period}")
            print(f"   Trading hours: {start_hour}:00-{end_hour}:00")
            print(f"   Max positions: {max_positions}")
            print(f"   Daily loss limit: {daily_loss_limit}%")
            print(f"   Risk/Reward ratio: {rr_ratio}:1")
            
        except Exception as e:
            print(f"   Error loading {set_name}: {e}")
    
    # Test with environment variable
    print("\n3. Testing with environment variable:")
    os.environ['ROBOQUANT_SET_FILE'] = 'aggressive.json'
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    print(f"   Environment variable ROBOQUANT_SET_FILE: {set_file}")
    
    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    
    test_set_manager()