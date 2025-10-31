import metatrader5 as mt5
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get MT5 credentials
login = int(os.getenv('MT5_LOGIN', '0'))
password = os.getenv('MT5_PASSWORD', '')
server = os.getenv('MT5_SERVER', '')

print("MT5 Credentials:")
print(f"Login: {login}")
print(f"Server: {server}")
print(f"Password length: {len(password)}")

# Initialize MT5
print("\nInitializing MT5...")
if not mt5.initialize():
    print("Failed to initialize MT5")
    print("Error code:", mt5.last_error())
else:
    print("MT5 initialized successfully")
    
    # Try to login
    print("\nAttempting to login...")
    authorized = mt5.login(login, password=password, server=server)
    if authorized:
        print("Login successful!")
        account_info = mt5.account_info()
        if account_info:
            print(f"Balance: {account_info.balance}")
            print(f"Equity: {account_info.equity}")
    else:
        print("Login failed")
        print("Error code:", mt5.last_error())
    
    # Shutdown MT5
    mt5.shutdown()
    print("MT5 connection closed")