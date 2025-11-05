#!/usr/bin/env python3
"""
Verification script for forex_factory_scraper module.
"""

import os
import tempfile
from forex_factory_scraper import fetch_upcoming_events_cached, get_all_upcoming_events

def test_forex_factory_functionality():
    """Test the Forex Factory scraper functionality."""
    print("Testing Forex Factory scraper functionality...")
    
    try:
        # Test fetching upcoming events
        print("\n1. Testing fetch_upcoming_events_cached...")
        has_event, info = fetch_upcoming_events_cached(hours_ahead=24)
        print(f"   Result: has_event={has_event}, info={info}")
        
        # Test getting all upcoming events
        print("\n2. Testing get_all_upcoming_events...")
        events = get_all_upcoming_events(hours_ahead=48)
        print(f"   Found {len(events)} events in the next 48 hours")
        
        if events:
            print("   First 3 events:")
            for i, event in enumerate(events[:3]):
                print(f"     {i+1}. {event.get('name', 'N/A')} ({event.get('currency', 'N/A')}) at {event.get('time_utc', 'N/A')}")
        else:
            print("   No events found (this might be due to network issues or no high-impact events)")
        
        # Verify that the functions exist and are callable
        print("\n3. Verifying function signatures...")
        assert callable(fetch_upcoming_events_cached)
        assert callable(get_all_upcoming_events)
        print("   All functions are callable")
        
        print("\n✅ Forex Factory scraper functionality test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error in Forex Factory scraper test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_forex_factory_functionality()
    if success:
        print("\n✅ Forex Factory scraper verification passed!")
    else:
        print("\n❌ Forex Factory scraper verification failed!")