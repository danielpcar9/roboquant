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