#!/usr/bin/env python3
"""Test script for Forex Factory scraper"""

from forex_factory_scraper import fetch_upcoming_events_cached
import logging

logging.basicConfig(level=logging.INFO)

def test_scraper():
    print("="*60)
    print("Testing Forex Factory Scraper")
    print("="*60)
    
    # Test 1: Fetch events
    print("\nTest 1: Fetching upcoming events...")
    has_event, info = fetch_upcoming_events_cached(hours_ahead=24)
    
    if has_event:
        print(f"✅ Event detected: {info}")
    else:
        print("ℹ️  No high-impact events in next 24 hours")
    
    # Test 2: Verify cache
    print("\nTest 2: Testing cache...")
    has_event2, info2 = fetch_upcoming_events_cached(hours_ahead=24)
    print("✅ Cache working" if (has_event == has_event2) else "⚠️  Cache inconsistent")
    
    print("\n" + "="*60)
    print("Tests completed")

if __name__ == "__main__":
    test_scraper()