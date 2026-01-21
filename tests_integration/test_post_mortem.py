#!/usr/bin/env python3
"""
Test script for post_mortem module in RoboQuant trading system.
"""

import os
import tempfile
from datetime import datetime, timedelta

import pandas as pd

from analysis.post_mortem import (
    analyze_recent_trades,
    generate_performance_report,
    log_trade,
)


def test_log_trade():
    """Test log_trade functionality."""
    print("Testing log_trade...")

    # Create a temporary trades file path (but don't create the file yet)
    temp_trades_file = tempfile.mkstemp(suffix=".csv")

    # Import post_mortem module
    from analysis import post_mortem

    # Store original file path
    original_file = post_mortem.TRADES_FILE

    try:
        # Temporarily override the TRADES_FILE path
        post_mortem.TRADES_FILE = temp_trades_file

        # Test logging a trade
        trade_data = {
            "timestamp_open": datetime.now().isoformat(),
            "timestamp_close": (datetime.now() + timedelta(minutes=30)).isoformat(),
            "ticket": 123456,
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": 0.01,
            "entry_price": 1234.56,
            "exit_price": 1235.78,
            "sl": 1230.00,
            "tp": 1240.00,
            "pnl": 12.22,
            "pnl_pct": 0.99,
            "duration_minutes": 30,
            "reason_closed": "TP reached",
        }

        log_trade(trade_data)

        # Verify the trade was logged
        df = pd.read_csv(temp_trades_file)
        assert len(df) == 1
        assert df.iloc[0]["ticket"] == 123456
        # Check that the pnl column exists
        assert "pnl" in df.columns
        assert df.iloc[0]["pnl"] == 12.22

        print("✓ log_trade tests passed")
        return True

    except Exception as e:
        print(f"✗ log_trade tests failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Restore original file path and clean up
        post_mortem.TRADES_FILE = original_file
        try:
            os.unlink(temp_trades_file)
        except OSError:
            pass


def test_analyze_recent_trades():
    """Test analyze_recent_trades functionality."""
    print("Testing analyze_recent_trades...")

    # Create a temporary trades file path (but don't create the file yet)
    temp_trades_file = tempfile.mkstemp(suffix=".csv")

    # Import post_mortem module
    from analysis import post_mortem

    # Store original file path
    original_file = post_mortem.TRADES_FILE

    try:
        # Temporarily override the TRADES_FILE path
        post_mortem.TRADES_FILE = temp_trades_file

        # Create test data with known characteristics
        test_data = []
        base_time = datetime.now()

        # Add winning trades
        for i in range(5):
            test_data.append(
                {
                    "timestamp_open": (base_time - timedelta(hours=i)).isoformat(),
                    "timestamp_close": (
                        base_time - timedelta(hours=i) + timedelta(minutes=30)
                    ).isoformat(),
                    "ticket": 1000 + i,
                    "symbol": "XAUUSD",
                    "side": "BUY" if i % 2 == 0 else "SELL",
                    "volume": 0.01,
                    "entry_price": 1234.56,
                    "exit_price": 1235.78,
                    "sl": 1230.00,
                    "tp": 1240.00,
                    "pnl": 12.22,
                    "pnl_pct": 0.99,
                    "duration_minutes": 30,
                    "reason_closed": "TP reached",
                    "hour_of_day": 14,
                },
            )

        # Add losing trades
        for i in range(3):
            test_data.append(
                {
                    "timestamp_open": (base_time - timedelta(hours=i + 5)).isoformat(),
                    "timestamp_close": (
                        base_time - timedelta(hours=i + 5) + timedelta(minutes=45)
                    ).isoformat(),
                    "ticket": 2000 + i,
                    "symbol": "XAUUSD",
                    "side": "SELL" if i % 2 == 0 else "BUY",
                    "volume": 0.01,
                    "entry_price": 1235.78,
                    "exit_price": 1234.56,
                    "sl": 1240.00,
                    "tp": 1230.00,
                    "pnl": -8.15,
                    "pnl_pct": -0.66,
                    "duration_minutes": 45,
                    "reason_closed": "SL hit",
                    "hour_of_day": 15,
                },
            )

        # Log all test trades
        for trade in test_data:
            log_trade(trade)

        # Analyze the trades
        metrics = analyze_recent_trades(n=10)

        # Verify metrics exist and have expected structure
        assert isinstance(metrics, dict)
        assert "n_trades" in metrics
        assert "wins" in metrics
        assert "losses" in metrics
        assert "win_rate" in metrics
        assert "total_pnl" in metrics
        assert "profit_factor" in metrics

        # Verify values (with some tolerance for floating point)
        assert metrics["n_trades"] == 8
        assert metrics["wins"] == 5
        assert metrics["losses"] == 3
        assert abs(metrics["win_rate"] - 0.625) < 0.001  # 62.5%
        expected_pnl = (5 * 12.22) + (3 * -8.15)  # 61.1 - 24.45 = 36.65
        assert (
            abs(metrics["total_pnl"] - expected_pnl) < 0.01
        )  # Allow for floating point precision
        assert metrics["profit_factor"] > 1.0  # Should be profitable

        print("✓ analyze_recent_trades tests passed")
        return True

    except Exception as e:
        print(f"✗ analyze_recent_trades tests failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Restore original file path and clean up
        post_mortem.TRADES_FILE = original_file
        try:
            os.unlink(temp_trades_file)
        except OSError:
            pass


def test_generate_performance_report():
    """Test generate_performance_report functionality."""
    print("Testing generate_performance_report...")

    # Create a temporary trades file path (but don't create the file yet)
    temp_fd, temp_trades_file = tempfile.mkstemp(suffix=".csv")
    os.close(temp_fd)  # Close the file descriptor immediately

    # Create a temporary report file for testing
    temp_fd2, temp_report_file = tempfile.mkstemp(suffix=".txt")
    os.close(temp_fd2)  # Close the file descriptor immediately

    # Import post_mortem module
    from analysis import post_mortem

    # Store original file path
    original_file = post_mortem.TRADES_FILE

    try:
        # Temporarily override the TRADES_FILE path
        post_mortem.TRADES_FILE = temp_trades_file

        # Create simple test data
        trade_data = {
            "timestamp_open": datetime.now().isoformat(),
            "timestamp_close": (datetime.now() + timedelta(minutes=30)).isoformat(),
            "ticket": 123456,
            "symbol": "XAUUSD",
            "side": "BUY",
            "volume": 0.01,
            "entry_price": 1234.56,
            "exit_price": 1235.78,
            "sl": 1230.00,
            "tp": 1240.00,
            "pnl": 12.22,
            "pnl_pct": 0.99,
            "duration_minutes": 30,
            "reason_closed": "TP reached",
        }

        log_trade(trade_data)

        # Generate performance report
        generate_performance_report(temp_report_file)

        # Verify report was created
        assert os.path.exists(temp_report_file)

        # Read and verify content
        with open(temp_report_file) as f:
            content = f.read()

        assert "ROBOQUANT PERFORMANCE REPORT" in content
        # The report may not have all the detailed metrics with just one trade

        print("✓ generate_performance_report tests passed")
        return True

    except Exception as e:
        print(f"✗ generate_performance_report tests failed: {e}")
        import traceback

        traceback.print_exc()
        return False
    finally:
        # Restore original file path and clean up
        post_mortem.TRADES_FILE = original_file
        try:
            os.unlink(temp_trades_file)
            os.unlink(temp_report_file)
        except OSError:
            pass


def test_mt5_metrics():
    """Test MT5 metrics functionality."""
    print("Testing MT5 metrics functionality...")

    try:
        # Import the MT5 metrics functions
        from analysis.post_mortem import (
            calculate_profit_factor_from_trades,
            calculate_sharpe_ratio_from_trades,
            calculate_win_rate_from_trades,
            get_mt5_performance_report,
        )

        # Test with empty trades (normal case when no MT5 connection)
        empty_trades = []
        pf = calculate_profit_factor_from_trades(empty_trades)
        sharpe = calculate_sharpe_ratio_from_trades(empty_trades)
        win_rate = calculate_win_rate_from_trades(empty_trades)

        assert pf == 0.0
        assert sharpe == 0.0
        assert win_rate == 0.0

        # Test with sample trades
        sample_trades = [
            {"profit": 100, "time": datetime.now()},
            {"profit": 50, "time": datetime.now()},
            {"profit": -30, "time": datetime.now()},
            {"profit": -20, "time": datetime.now()},
        ]

        pf = calculate_profit_factor_from_trades(sample_trades)
        sharpe = calculate_sharpe_ratio_from_trades(sample_trades)
        win_rate = calculate_win_rate_from_trades(sample_trades)

        # With sample trades: wins=150, losses=50, so PF=3.0
        assert pf == 3.0
        assert win_rate == 50.0  # 2 wins out of 4 trades

        # Test report generation with empty trades
        report = get_mt5_performance_report(days_back=1)
        assert "error" in report

        print("✓ MT5 metrics tests passed")
        return True

    except Exception as e:
        print(f"✗ MT5 metrics tests failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all post_mortem tests."""
    print("Running post_mortem component tests...\n")

    tests = [
        test_log_trade,
        test_analyze_recent_trades,
        test_generate_performance_report,
        test_mt5_metrics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            failed += 1
        print()  # Add spacing between tests

    print(f"Post-mortem tests completed: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All post-mortem tests passed!")
        return True
    print("❌ Some post-mortem tests failed!")
    return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
