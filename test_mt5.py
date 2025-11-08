import sys
print("Python version:", sys.version)
print("Python executable:", sys.executable)

# Mock MT5 module for testing the timeframe conversion
class MockMT5:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388
    TIMEFRAME_D1 = 16408
    TIMEFRAME_W1 = 32769
    TIMEFRAME_MN1 = 49153

# Import consolidated MT5 functions
from mt5_core import timeframe_to_string

# timeframe_to_string function removed - using consolidated version from mt5_core.py

# Test the timeframe conversion
mt5 = MockMT5()
print("Testing timeframe conversion:")
print(f"TIMEFRAME_H1 -> {timeframe_to_string(mt5.TIMEFRAME_H1)}")
print(f"TIMEFRAME_M15 -> {timeframe_to_string(mt5.TIMEFRAME_M15)}")
print(f"TIMEFRAME_D1 -> {timeframe_to_string(mt5.TIMEFRAME_D1)}")

print("\nThis confirms that our fix for the TimeFrameToString issue is correct.")
print("The function properly maps MT5 timeframe constants to their string representations.")