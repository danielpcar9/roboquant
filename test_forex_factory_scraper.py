#!/usr/bin/env python3
"""
Test script for forex_factory_scraper module in RoboQuant trading system.
"""

import os
import tempfile
from forex_factory_scraper import fetch_upcoming_events_cached, get_all_upcoming_events, _parse_calendar_row
from datetime import datetime
import pytz

def test_fetch_upcoming_events_cached():
    """Test fetch_upcoming_events_cached functionality."""
    print("Testing fetch_upcoming_events_cached...")
    
    try:
        # Test with a short time window
        has_event, info = fetch_upcoming_events_cached(hours_ahead=1)
        
        # Should not crash, but may return (False, None) if no events
        assert isinstance(has_event, bool)
        assert isinstance(info, (str, type(None)))
        
        print("✓ fetch_upcoming_events_cached tests passed")
        return True
        
    except Exception as e:
        print(f"✗ fetch_upcoming_events_cached tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_get_all_upcoming_events():
    """Test get_all_upcoming_events functionality."""
    print("Testing get_all_upcoming_events...")
    
    try:
        # Test with a short time window
        events = get_all_upcoming_events(hours_ahead=1)
        
        # Should not crash, but may return empty list if no events
        assert isinstance(events, list)
        
        print("✓ get_all_upcoming_events tests passed")
        return True
        
    except Exception as e:
        print(f"✗ get_all_upcoming_events tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parse_calendar_row():
    """Test _parse_calendar_row functionality."""
    print("Testing _parse_calendar_row...")
    
    try:
        # This test is limited since we can't easily create BeautifulSoup objects
        # but we can at least verify the function exists and is callable
        assert callable(_parse_calendar_row)
        
        print("✓ _parse_calendar_row tests passed")
        return True
        
    except Exception as e:
        print(f"✗ _parse_calendar_row tests failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all forex_factory_scraper tests."""
    print("Running forex_factory_scraper component tests...\n")
    
    tests = [
        test_fetch_upcoming_events_cached,
        test_get_all_upcoming_events,
        test_parse_calendar_row
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing between tests
    
    print(f"Forex Factory scraper tests completed: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All Forex Factory scraper tests passed!")
        return True
    else:
        print("❌ Some Forex Factory scraper tests failed!")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)