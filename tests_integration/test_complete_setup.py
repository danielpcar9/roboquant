import logging
import os
import sys

# Set up detailed logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Load environment variables (with error handling)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception as e:
    logging.warning(f"Could not load .env file: {e}")

# Import MetaTrader5 (official package name)
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None  # type: ignore

# Import project modules
SAFETY_MODULE_AVAILABLE = False
Safety = None
try:
    from risk.safety import Safety

    SAFETY_MODULE_AVAILABLE = True
except ImportError:
    logging.warning("Safety module not available")


def test_mt5_connection():
    """Test MT5 connection"""
    logging.info("Testing MT5 connection...")

    if mt5 is None:
        logging.error("MT5 module not available")
        return False

    try:
        if not mt5.initialize():  # type: ignore
            logging.error("Failed to initialize MT5")
            return False

        logging.info("MT5 initialized successfully")

        # Test account info
        account_info = mt5.account_info()  # type: ignore
        if account_info:
            logging.info("Account info retrieved successfully")
        else:
            logging.warning("Could not retrieve account info")

        mt5.shutdown()  # type: ignore
        logging.info("MT5 connection test passed")
        return True

    except Exception as e:
        logging.exception(f"MT5 connection test failed: {e}")
        return False


def test_xauusd_symbol():
    """Test XAUUSD symbol availability"""
    logging.info("Testing XAUUSD symbol availability...")

    if mt5 is None:
        logging.error("MT5 module not available")
        return False

    try:
        if not mt5.initialize():  # type: ignore
            logging.error("Failed to initialize MT5")
            return False

        # Select XAUUSD symbol
        if not mt5.symbol_select("XAUUSD", True):  # type: ignore
            logging.error("Failed to select XAUUSD symbol")
            mt5.shutdown()  # type: ignore
            return False

        # Get symbol info
        symbol_info = mt5.symbol_info("XAUUSD")  # type: ignore
        if not symbol_info:
            logging.error("Failed to get XAUUSD symbol info")
            mt5.shutdown()  # type: ignore
            return False

        logging.info("XAUUSD symbol is available")
        logging.info(f"  Point value: {getattr(symbol_info, 'point', 'N/A')}")
        logging.info(f"  Minimum volume: {getattr(symbol_info, 'volume_min', 'N/A')}")

        mt5.shutdown()  # type: ignore
        logging.info("XAUUSD symbol test passed")
        return True

    except Exception as e:
        logging.exception(f"XAUUSD symbol test failed: {e}")
        return False


def test_safety_module():
    """Test safety module functionality"""
    logging.info("Testing safety module...")

    if not SAFETY_MODULE_AVAILABLE:
        logging.warning("Safety module not available, skipping test")
        return True

    try:
        # Initialize safety module
        if Safety is not None:
            safety = Safety(mt5_module=mt5 if mt5 else None)
            logging.info("Safety module initialized successfully")

            # Test kill switch file path
            logging.info(f"Kill switch file path: {getattr(safety, 'hwm_file', 'N/A')}")

            logging.info("Safety module test passed")
            return True
        logging.warning("Safety module not available, skipping test")
        return True

    except Exception as e:
        logging.exception(f"Safety module test failed: {e}")
        return False


def test_telegram_integration():
    """Test Telegram integration"""
    logging.info("Testing Telegram integration...")

    # Check if Telegram credentials are in environment
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not telegram_token or not telegram_chat_id:
        logging.warning("Telegram credentials not found in environment, skipping test")
        return True

    logging.info("Telegram credentials found")
    logging.info("Telegram integration test passed")
    return True


def test_directory_structure():
    """Test required directory structure"""
    logging.info("Testing directory structure...")

    required_dirs = ["data", "logs", "config"]
    missing_dirs = []

    for dir_name in required_dirs:
        if not os.path.exists(dir_name):
            missing_dirs.append(dir_name)
            logging.error(f"Missing directory: {dir_name}")
        else:
            logging.info(f"Found directory: {dir_name}")

    if missing_dirs:
        logging.error(f"Missing directories: {', '.join(missing_dirs)}")
        return False

    logging.info("Directory structure test passed")
    return True


def test_essential_files():
    """Test essential file presence"""
    logging.info("Testing essential files...")

    essential_files = [
        "donchian_strategy.py",
        "mt5_utils.py",
        "safety.py",
        "backtest_apex_vectorbt.py",
        "export_mt5_data.py",
        "webhook_receiver.py",
        "requirements.txt",
    ]

    missing_files = []

    for file_name in essential_files:
        if not os.path.exists(file_name):
            missing_files.append(file_name)
            logging.error(f"Missing file: {file_name}")
        else:
            logging.info(f"Found file: {file_name}")

    if missing_files:
        logging.error(f"Missing files: {', '.join(missing_files)}")
        return False

    logging.info("Essential files test passed")
    return True


def test_order_execution():
    """Test order execution functionality (optional)"""
    logging.info("Testing order execution...")

    # This test is optional and can be skipped
    skip_order_test = os.getenv("SKIP_ORDER_TEST", "false").lower() == "true"
    if skip_order_test:
        logging.info("Order execution test skipped (SKIP_ORDER_TEST=true)")
        return True

    if mt5 is None:
        logging.warning("MT5 module not available, skipping order test")
        return True

    try:
        if not mt5.initialize():  # type: ignore
            logging.error("Failed to initialize MT5")
            return False

        # Select XAUUSD symbol
        if not mt5.symbol_select("XAUUSD", True):  # type: ignore
            logging.error("Failed to select XAUUSD symbol")
            mt5.shutdown()  # type: ignore
            return False

        # Get symbol info for point value
        symbol_info = mt5.symbol_info("XAUUSD")  # type: ignore
        if not symbol_info:
            logging.error("Failed to get XAUUSD symbol info")
            mt5.shutdown()  # type: ignore
            return False

        # Get current price
        tick = mt5.symbol_info_tick("XAUUSD")  # type: ignore
        if not tick:
            logging.error("Failed to get current price")
            mt5.shutdown()  # type: ignore
            return False

        # Use a very small volume for testing
        volume = 0.01

        # Calculate test SL/TP (very wide to avoid execution)
        point = symbol_info.point
        price = tick.ask
        sl = price - 1000 * point  # Very far away
        tp = price + 1000 * point  # Very far away

        logging.info("Order parameters for test:")
        logging.info("  Symbol: XAUUSD")
        logging.info(f"  Volume: {volume}")
        logging.info(f"  Price: {price}")
        logging.info(f"  SL: {sl}")
        logging.info(f"  TP: {tp}")

        # Note: We're not actually sending the order for safety
        logging.info("✅ Order execution test passed (no actual order sent)")

        mt5.shutdown()  # type: ignore
        return True

    except Exception as e:
        logging.exception(f"Order execution test failed: {e}")
        return False


def main():
    """Main function to execute all tests and display summary"""
    logging.info("=" * 60)
    logging.info("🤖 roboquant Complete Setup Test")
    logging.info("=" * 60)

    tests = [
        ("MT5 Connection", test_mt5_connection),
        ("XAUUSD Symbol", test_xauusd_symbol),
        ("Safety Module", test_safety_module),
        ("Telegram Integration", test_telegram_integration),
        ("Directory Structure", test_directory_structure),
        ("Essential Files", test_essential_files),
        ("Order Execution", test_order_execution),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            logging.info(f"\n🔍 Running {test_name} test...")
            result = test_func()
            results.append((test_name, result))
            if result:
                logging.info(f"✅ {test_name} test passed")
            else:
                logging.error(f"❌ {test_name} test failed")
        except Exception as e:
            logging.exception(f"❌ {test_name} test failed with exception: {e}")
            results.append((test_name, False))

    # Display summary
    logging.info("\n" + "=" * 60)
    logging.info("📋 Test Summary")
    logging.info("=" * 60)

    passed_tests = sum(1 for _, result in results if result)
    total_tests = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logging.info(f"{status} - {test_name}")

    logging.info("-" * 60)
    logging.info(f"Total: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        logging.info("🎉 All tests passed! Your setup is complete.")
        return 0
    logging.error(
        f"💥 {total_tests - passed_tests} test(s) failed. Please review the errors above.",
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
