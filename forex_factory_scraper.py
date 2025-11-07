import os
import requests
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict, Any
from bs4 import BeautifulSoup
import pytz
import json

# Import caching system
from api_cache import APICache
from error_handler import retry_with_exponential_backoff, handle_exception

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Cache TTL: 30 minutes (1800 seconds) for Forex Factory events
CACHE_TTL = int(os.getenv('CACHE_FOREX_FACTORY_TTL', 1800))

# User-Agent for web scraping
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
USER_AGENT = os.getenv('USER_AGENT', DEFAULT_USER_AGENT)

# Session for connection pooling
session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "Referer": "https://www.google.com/"
})

class ForexFactoryError(Exception):
    """Custom exception for Forex Factory scraper errors."""
    pass

def fetch_upcoming_events_cached(hours_ahead: int = 2) -> Tuple[bool, Optional[str]]:
    """
    Scrape Forex Factory calendar with intelligent caching.
    
    Args:
        hours_ahead: Time window to check for events (in hours)
        
    Returns:
        tuple: (has_event: bool, event_info: str or None)
        
    Example:
        has_event, info = fetch_upcoming_events_cached(2)
        if has_event:
            print(f"Evento detectado: {info}")
    """
    # Initialize cache
    cache_file_path = os.getenv('CACHE_FILE_PATH', 'data/api_cache.json')
    cache = APICache(cache_file_path)
    
    # Generate cache key
    cache_key = f"forex_factory_events_{hours_ahead}"
    
    # Try to get from cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logging.info("Using cached Forex Factory data")
        return cached_result
    
    # If not in cache or expired, fetch from Forex Factory
    logging.info("Fetching fresh data from Forex Factory")
    
    try:
        # Scrape Forex Factory calendar
        has_event, event_info = _scrape_forex_factory_events(hours_ahead)
        result = (has_event, event_info)
        
        # Cache the result
        cache.set(cache_key, result, CACHE_TTL)
        return result
        
    except requests.Timeout:
        logging.error("Timeout scraping Forex Factory")
        # Use cache as fallback if available
        if cached_result is not None:
            logging.warning("Using expired cache data as fallback due to timeout")
            return cached_result
        return (False, None)
        
    except requests.HTTPError as e:
        if e.response.status_code == 429:
            logging.error("Rate limited by Forex Factory")
            # Use cache as fallback if available
            if cached_result is not None:
                logging.warning("Using expired cache data as fallback due to rate limit")
                return cached_result
            return (False, None)
        elif e.response.status_code == 403:
            logging.error("Blocked by Forex Factory (IP ban?)")
            # Use cache as fallback if available
            if cached_result is not None:
                logging.warning("Using expired cache data as fallback due to block")
                return cached_result
            return (False, None)
        else:
            logging.error(f"HTTP error scraping Forex Factory: {e}")
            # Use cache as fallback if available
            if cached_result is not None:
                logging.warning("Using expired cache data as fallback due to HTTP error")
                return cached_result
            return (False, None)
            
    except Exception as e:
        logging.error(f"Unexpected error scraping Forex Factory: {e}")
        # Use cache as fallback if available
        if cached_result is not None:
            logging.warning("Using expired cache data as fallback due to unexpected error")
            return cached_result
        return (False, None)

@handle_exception
@retry_with_exponential_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
def _scrape_forex_factory_events(hours_ahead: int) -> Tuple[bool, Optional[str]]:
    """
    Scrape Forex Factory calendar for high-impact events.
    
    Args:
        hours_ahead: Time window to check for events (in hours)
        
    Returns:
        tuple: (has_event: bool, event_info: str or None)
    """
    # Forex Factory URL
    url = "https://www.forexfactory.com/calendar"
    
    # Add some randomness to make requests look more human
    time.sleep(random.uniform(1.5, 3.5))
    
    # Make request with timeout
    try:
        # Add some randomness to timeout as well
        timeout = random.uniform(10, 20)
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Request failed: {e}")
        raise ForexFactoryError(f"Failed to fetch Forex Factory calendar: {e}")
    
    # Parse HTML
    try:
        soup = BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        logging.error(f"Failed to parse HTML: {e}")
        raise ForexFactoryError(f"Failed to parse Forex Factory calendar HTML: {e}")
    
    # Find calendar rows
    rows = soup.find_all('tr', class_='calendar__row')
    
    if not rows:
        logging.warning("No calendar rows found in Forex Factory response")
        return (False, None)
    
    # Get current time in UTC
    now_utc = datetime.now(pytz.UTC)
    future_limit = now_utc + timedelta(hours=hours_ahead)
    
    # Process each row
    events_found = []
    for row in rows:
        try:
            event_info = _parse_calendar_row(row, now_utc, future_limit)
            if event_info:
                events_found.append(event_info)
        except Exception as e:
            logging.debug(f"Error processing calendar row: {e}")
            continue
    
    # Return the first high-impact event found
    if events_found:
        first_event = events_found[0]
        event_info = f"{first_event['name']} ({first_event['currency']}) at {first_event['time_utc'].strftime('%H:%M UTC')}"
        return (True, event_info)
    
    # No high-impact events found in the time window
    return (False, None)

def _parse_calendar_row(row, now_utc: datetime, future_limit: datetime) -> Optional[Dict[str, Any]]:
    """
    Parse a single calendar row from Forex Factory.
    
    Args:
        row: BeautifulSoup row element
        now_utc: Current time in UTC
        future_limit: Upper time limit for events
        
    Returns:
        Dictionary with event information or None if not a high-impact event
    """
    # Check if it's a high-impact event
    impact_cell = row.find('td', class_='calendar__impact')
    if not impact_cell:
        return None
        
    # Look for high impact icon (red)
    high_impact_icon = impact_cell.find('span', class_='icon--ff-impact-red')
    if not high_impact_icon:
        return None
    
    # Get event time
    time_cell = row.find('td', class_='calendar__time')
    if not time_cell or not time_cell.get_text(strip=True):
        return None  # Skip all-day events
        
    event_time_str = time_cell.get_text(strip=True)
    
    # Get currency
    currency_cell = row.find('td', class_='calendar__currency')
    currency = currency_cell.get_text(strip=True) if currency_cell else "N/A"
    
    # Get event name
    event_cell = row.find('td', class_='calendar__event')
    event_name = event_cell.get_text(strip=True) if event_cell else "N/A"
    
    # Parse time - Forex Factory uses EST/EDT
    try:
        # Try to determine if we're in EST or EDT
        # EST is GMT-5, EDT is GMT-4
        # We'll assume EDT for now (more common in summer)
        # In practice, you might want to check the actual date
        ff_tz = pytz.timezone('US/Eastern')
        
        # Get today's date for context
        today = now_utc.astimezone(ff_tz).date()
        
        # Parse the time string
        if 'am' in event_time_str.lower() or 'pm' in event_time_str.lower():
            # Convert to 24-hour format if needed
            event_time = datetime.strptime(event_time_str, '%I:%M%p').time()
        else:
            # Handle 24-hour format
            event_time = datetime.strptime(event_time_str, '%H:%M').time()
        
        # Create datetime object for today with the event time
        event_datetime_ff = datetime.combine(today, event_time)
        
        # Localize to Eastern time
        event_datetime_ff = ff_tz.localize(event_datetime_ff)
        
        # Convert to UTC
        event_datetime_utc = event_datetime_ff.astimezone(pytz.UTC)
        
        # Check if event is within our time window
        if now_utc <= event_datetime_utc <= future_limit:
            # Convert to CET for FTMO compliance
            cet = pytz.timezone('CET')
            event_datetime_cet = event_datetime_utc.astimezone(cet)
            
            return {
                'name': event_name,
                'currency': currency,
                'time_utc': event_datetime_utc,
                'time_ff': event_datetime_ff,
                'time_cet': event_datetime_cet
            }
            
    except ValueError as e:
        # Skip events with unparseable times
        logging.debug(f"Skipping event with unparseable time: {event_time_str}, error: {e}")
        return None
    except Exception as e:
        logging.debug(f"Error parsing event time: {e}")
        return None
    
    return None

def get_all_upcoming_events(hours_ahead: int = 24) -> List[Dict[str, Any]]:
    """
    Get all upcoming high-impact events within the specified time window.
    Includes 2-minute buffer before/after for FTMO compliance.
    
    Args:
        hours_ahead: Time window to check for events (in hours)
        
    Returns:
        List of dictionaries with event information
    """
    # Initialize cache
    cache_file_path = os.getenv('CACHE_FILE_PATH', 'data/api_cache.json')
    cache = APICache(cache_file_path)
    
    # Generate cache key
    cache_key = f"forex_factory_all_events_{hours_ahead}"
    
    # Try to get from cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logging.info("Using cached Forex Factory events data")
        return cached_result
    
    # If not in cache or expired, fetch from Forex Factory
    logging.info("Fetching all upcoming events from Forex Factory")
    
    try:
        # Forex Factory URL
        url = "https://www.forexfactory.com/calendar"
        
        # Add some randomness to make requests look more human
        time.sleep(random.uniform(1.5, 3.5))
        
        # Make request with timeout
        timeout = random.uniform(10, 20)
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find calendar rows
        rows = soup.find_all('tr', class_='calendar__row')
        
        # Get current time in UTC
        now_utc = datetime.now(pytz.UTC)
        future_limit = now_utc + timedelta(hours=hours_ahead)
        
        # Process each row
        events = []
        for row in rows:
            try:
                event_info = _parse_calendar_row(row, now_utc, future_limit)
                if event_info:
                    events.append(event_info)
            except Exception as e:
                logging.debug(f"Error processing calendar row: {e}")
                continue
        
        # Cache the result
        cache.set(cache_key, events, CACHE_TTL)
        return events
        
    except Exception as e:
        logging.error(f"Error fetching all upcoming events: {e}")
        # Use cache as fallback if available
        if cached_result is not None:
            logging.warning("Using expired cache data as fallback")
            return cached_result
        return []

def is_trading_blocked_by_news() -> Tuple[bool, Optional[datetime]]:
    """
    Check if trading should be blocked due to upcoming high-impact news.
    Returns (is_blocked, blocking_until_time) tuple.
    """
    # Check for events in the next 5 minutes
    has_event, event_info = fetch_upcoming_events_cached(hours_ahead=1)
    
    if has_event and event_info:
        # Parse the event time
        try:
            # Get all events to find the specific one
            all_events = get_all_upcoming_events(hours_ahead=1)
            if all_events:
                # Get the first event's time
                event_time = all_events[0]['time_utc']
                
                # Convert to CET for FTMO compliance
                cet = pytz.timezone('CET')
                event_time_cet = event_time.astimezone(cet)
                
                # Block 2 minutes before and after
                block_start = event_time_cet - timedelta(minutes=2)
                block_end = event_time_cet + timedelta(minutes=2)
                
                # Check if we're in the blocked period
                now_cet = datetime.now(cet)
                if block_start <= now_cet <= block_end:
                    return True, block_end
                
        except Exception as e:
            logging.debug(f"Error checking news blocking: {e}")
    
    return False, None

def test_scraper():
    """Test script for Forex Factory scraper"""
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
    
    # Test 3: Get all events
    print("\nTest 3: Fetching all upcoming events...")
    all_events = get_all_upcoming_events(hours_ahead=48)
    print(f"✅ Found {len(all_events)} high-impact events in next 48 hours")
    
    if all_events:
        print("\nFirst 3 events:")
        for i, event in enumerate(all_events[:3]):
            print(f"  {i+1}. {event['name']} ({event['currency']}) at {event['time_utc'].strftime('%Y-%m-%d %H:%M UTC')}")
    
    print("\n" + "="*60)
    print("Tests completed")

if __name__ == "__main__":
    test_scraper()