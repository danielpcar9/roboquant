import os
import json
import time
import logging
from typing import Any, Optional, Dict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

class APICache:
    """A simple file-based cache system for API responses with TTL support."""
    
    def __init__(self, cache_file_path: str = "data/api_cache.json"):
        """Initialize the cache with a file path."""
        self.cache_file_path = cache_file_path
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cache from JSON file."""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, 'r') as f:
                    self.cache = json.load(f)
                logging.debug(f"Cache loaded from {self.cache_file_path}")
            else:
                logging.debug(f"Cache file {self.cache_file_path} not found, starting with empty cache")
        except Exception as e:
            logging.warning(f"Failed to load cache from {self.cache_file_path}: {e}")
            self.cache = {}
    
    def _save_cache(self) -> None:
        """Save cache to JSON file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file_path), exist_ok=True)
            
            # Limit cache size to 100 entries, remove oldest if needed
            if len(self.cache) > 100:
                # Sort by timestamp and remove oldest entries
                sorted_entries = sorted(self.cache.items(), key=lambda x: x[1].get('timestamp', 0))
                # Keep only the most recent 90 entries
                self.cache = dict(sorted_entries[-90:])
            
            with open(self.cache_file_path, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logging.debug(f"Cache saved to {self.cache_file_path}")
        except Exception as e:
            logging.error(f"Failed to save cache to {self.cache_file_path}: {e}")
    
    def _get_cache_key(self, *args, **kwargs) -> str:
        """Generate a unique cache key from function arguments."""
        # Create a string representation of args and kwargs
        key_parts = [str(arg) for arg in args]
        key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
        return "|".join(key_parts)
    
    def is_expired(self, key: str) -> bool:
        """Check if a cache entry has expired."""
        if key not in self.cache:
            return True
        
        entry = self.cache[key]
        timestamp = entry.get('timestamp', 0)
        ttl = entry.get('ttl', 0)
        
        return time.time() > (timestamp + ttl)
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached data if it exists and hasn't expired."""
        if key not in self.cache:
            return None
        
        if self.is_expired(key):
            logging.debug(f"Cache entry expired for key: {key}")
            return None
        
        logging.debug(f"Cache HIT for key: {key}")
        return self.cache[key].get('data')
    
    def set(self, key: str, data: Any, ttl: int) -> None:
        """Set cache data with TTL."""
        self.cache[key] = {
            'timestamp': time.time(),
            'ttl': ttl,
            'data': data
        }
        logging.debug(f"Cache SET for key: {key} with TTL: {ttl}")
        self._save_cache()
    
    def clear_expired(self) -> None:
        """Remove expired entries from cache."""
        keys_to_remove = [key for key in self.cache if self.is_expired(key)]
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            logging.info(f"Removed {len(keys_to_remove)} expired cache entries")
            self._save_cache()

# Initialize global cache instance
CACHE_FILE_PATH = os.getenv('CACHE_FILE_PATH', 'data/api_cache.json')
cache = APICache(CACHE_FILE_PATH)

# Get TTL values from environment variables
CACHE_TRADINGECONOMICS_TTL = int(os.getenv('CACHE_TRADINGECONOMICS_TTL', 3600))  # 1 hour default
CACHE_FRED_TTL = int(os.getenv('CACHE_FRED_TTL', 21600))  # 6 hours default

def fetch_upcoming_high_impact_cached(minutes_window: int = 120) -> tuple:
    """
    Fetch upcoming high impact events from TradingEconomics API with caching.
    
    Args:
        minutes_window: Time window to check for events (in minutes)
        
    Returns:
        tuple: (has_event: bool, event_info: str or None)
    """
    import requests
    from datetime import datetime, timezone, timedelta
    
    # Generate cache key
    cache_key = cache._get_cache_key("tradingeconomics", minutes_window)
    
    # Try to get from cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logging.info("Using cached TradingEconomics data")
        return cached_result
    
    # If not in cache or expired, fetch from API
    logging.info("Fetching fresh data from TradingEconomics API")
    te_key = os.getenv('TRADINGECONOMICS_KEY')
    if not te_key:
        logging.warning("No TradingECONOMICS_KEY found in environment")
        return False, None
    
    try:
        url = f"https://api.tradingeconomics.com/calendar?c={te_key}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        events = r.json()
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(minutes=minutes_window)
        
        for ev in events:
            impact = str(ev.get("Importance", ""))
            date_str = ev.get("Date")
            if not date_str:
                continue
            try:
                ev_time = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except:
                continue
            if impact in ["High", "3"] and now <= ev_time <= window_end:
                result = (True, f"{ev.get('Event', '')} at {ev_time.strftime('%H:%M UTC')}")
                # Cache the result
                cache.set(cache_key, result, CACHE_TRADINGECONOMICS_TTL)
                return result
        
        result = (False, None)
        # Cache the result
        cache.set(cache_key, result, CACHE_TRADINGECONOMICS_TTL)
        return result
    except Exception as e:
        logging.error(f"Error fetching TradingEconomics data: {e}")
        # If we have expired cache data, use it as fallback
        if cached_result is not None:
            logging.warning("Using expired cache data as fallback")
            return cached_result
        return False, None

def fetch_fred_series_cached(series_id: str, observations: int = 1) -> Optional[float]:
    """
    Fetch FRED series data with caching.
    
    Args:
        series_id: The FRED series identifier
        observations: Number of observations to fetch
        
    Returns:
        float or None: The latest value or None if failed
    """
    import requests
    
    # Generate cache key
    cache_key = cache._get_cache_key("fred", series_id, observations)
    
    # Try to get from cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        logging.info("Using cached FRED data")
        return cached_result
    
    # If not in cache or expired, fetch from API
    logging.info("Fetching fresh data from FRED API")
    key = os.getenv('FRED_KEY')
    if not key:
        logging.warning("No FRED_KEY found in environment")
        return None
    
    try:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={key}&file_type=json&limit={observations}&sort_order=desc"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        obs = r.json().get("observations", [])
        if obs and obs[0].get("value") != ".":
            result = float(obs[0]["value"])
            # Cache the result
            cache.set(cache_key, result, CACHE_FRED_TTL)
            return result
    except Exception as e:
        logging.error(f"Error fetching FRED data: {e}")
        # If we have expired cache data, use it as fallback
        if cached_result is not None:
            logging.warning("Using expired cache data as fallback")
            return cached_result
        return None

def test_cache() -> bool:
    """
    Test the cache functionality.
    
    Returns:
        bool: True if cache is working correctly
    """
    logging.info("Testing cache functionality...")
    
    # Test basic cache operations
    test_key = "test_key"
    test_data = {"test": "data"}
    test_ttl = 60  # 1 minute
    
    # Test set
    cache.set(test_key, test_data, test_ttl)
    
    # Test get
    retrieved_data = cache.get(test_key)
    if retrieved_data != test_data:
        logging.error("Cache SET/GET test failed")
        return False
    
    # Test is_expired (should not be expired yet)
    if cache.is_expired(test_key):
        logging.error("Cache expiration test failed")
        return False
    
    # Test cache key generation
    key1 = cache._get_cache_key("test", 1, a=2)
    key2 = cache._get_cache_key("test", 1, a=2)
    key3 = cache._get_cache_key("test", 2, a=2)
    
    if key1 != key2:
        logging.error("Cache key generation consistency test failed")
        return False
    
    if key1 == key3:
        logging.error("Cache key generation uniqueness test failed")
        return False
    
    logging.info("All cache tests passed!")
    return True

if __name__ == "__main__":
    # Run cache tests when executed directly
    test_cache()