import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("Environment Variables:")
print(f"MT5_LOGIN: {os.getenv('MT5_LOGIN')}")
print(f"MT5_PASSWORD: {os.getenv('MT5_PASSWORD')}")
print(f"MT5_SERVER: {os.getenv('MT5_SERVER')}")

# Check if variables are loaded
if os.getenv('MT5_LOGIN') and os.getenv('MT5_PASSWORD') and os.getenv('MT5_SERVER'):
    print("\n✅ All MT5 credentials found in environment")
else:
    print("\n❌ Missing MT5 credentials in environment")