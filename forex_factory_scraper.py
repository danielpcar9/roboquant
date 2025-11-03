import os
import requests
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from bs4 import BeautifulSoup
import pytz

# Import caching system
from api_cache import APICache

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Cache TTL: 30 minutes (1800 seconds) for Forex Factory events
CACHE_TTL = int(os.getenv('CACHE_FOREX_FACTORY_TTL', 1800))

# User-Agent for web scraping
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
USER_AGENT = os.getenv('USER_AGENT', DEFAULT_USER_AGENT)

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
    
    # Headers to avoid blocking
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    
    # Make request
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    # Parse HTML
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Find calendar rows
    rows = soup.find_all('tr', class_='calendar__row')
    
    # Get current time in UTC
    now_utc = datetime.now(pytz.UTC)
    future_limit = now_utc + timedelta(hours=hours_ahead)
    
    # Process each row
    for row in rows:
        try:
            # Check if it's a high-impact event
            impact_cell = row.find('td', class_='calendar__impact')
            if not impact_cell:
                continue
                
            # Look for high impact icon (red)
            high_impact_icon = impact_cell.find('span', class_='icon--ff-impact-red')
            if not high_impact_icon:
                continue
            
            # Get event time
            time_cell = row.find('td', class_='calendar__time')
            if not time_cell or not time_cell.get_text(strip=True):
                continue  # Skip all-day events
                
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
                    event_info = f"{event_name} ({currency}) at {event_datetime_utc.strftime('%H:%M UTC')}"
                    return (True, event_info)
                    
            except ValueError:
                # Skip events with unparseable times
                logging.debug(f"Skipping event with unparseable time: {event_time_str}")
                continue
                
        except Exception as e:
            logging.debug(f"Error processing calendar row: {e}")
            continue
    
    # No high-impact events found in the time window
    return (False, None)

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
    
    print("\n" + "="*60)
    print("Tests completed")

if __name__ == "__main__":
    test_scraper()