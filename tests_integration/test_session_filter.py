import logging
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from session_filter import session_filter

def test_session_filter():
    """Test the SessionFilter implementation"""
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    
    # Test current session detection
    current_session = session_filter.get_current_session()
    print(f"Current session: {current_session}")
    
    # Test session performance analysis (mock data)
    # In a real scenario, this would connect to MT5
    print("Testing session filter components...")
    
    # Test favorable session detection
    is_favorable, confidence = session_filter.is_favorable_session("XAUUSD")
    print(f"Is current session favorable: {is_favorable} (confidence: {confidence:.2f})")
    
    # Test best sessions
    best_sessions = session_filter.get_best_sessions("XAUUSD", 3)
    print(f"Best sessions: {best_sessions}")

if __name__ == "__main__":
    test_session_filter()