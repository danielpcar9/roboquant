#!/usr/bin/env python3
"""
Validation script to check if the environment is properly set up for the roboquant system.
This script verifies:
1. Required Python packages are installed
2. Python version compatibility
3. MT5 connection can be established
4. Environment variables are properly configured
5. Data directories exist
"""

import sys
import os
import importlib.util
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    print("🔍 Checking Python version...")
    major, minor = sys.version_info[:2]
    if major < 3 or (major == 3 and minor < 7):
        print(f"❌ Python version {sys.version} is not supported. Required: Python 3.7+")
        return False
    print(f"✅ Python version {sys.version_info.major}.{sys.version_info.minor} is supported")
    return True

def check_required_packages():
    """Check if all required packages are installed"""
    print("\n🔍 Checking required packages...")
    
    # Read requirements from requirements.txt
    requirements_file = Path("requirements.txt")
    if not requirements_file.exists():
        print("❌ requirements.txt file not found")
        return False
    
    with open(requirements_file, "r") as f:
        required_packages = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    
    missing_packages = []
    for package_line in required_packages:
        # Handle version specifiers
        package_name = package_line.split("==")[0].split(">=")[0].split("<=")[0].split(">")[0].split("<")[0]
        
        try:
            importlib.util.find_spec(package_name)
            print(f"✅ {package_line}")
        except ImportError:
            print(f"❌ {package_line}")
            missing_packages.append(package_line)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Please install them using: pip install -r requirements.txt")
        return False
    
    print("✅ All required packages are installed")
    return True

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔍 Checking environment variables...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  .env file not found. Using default values or environment variables.")
        print("   Please create .env file from .env.example template.")
    
    # Check MT5 credentials (optional check)
    mt5_login = os.getenv("MT5_LOGIN")
    mt5_password = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    
    if mt5_login and mt5_password and mt5_server:
        print("✅ MT5 credentials found in environment variables")
    else:
        print("⚠️  MT5 credentials not found in environment variables")
        print("   Trading functionality will be limited without them")
    
    # Check webhook secret key (optional)
    webhook_secret = os.getenv("WEBHOOK_SECRET_KEY")
    if webhook_secret:
        print("✅ Webhook secret key found")
    else:
        print("⚠️  Webhook secret key not found")
        print("   Webhook functionality will be limited without it")
    
    return True

def check_directories():
    """Check if required directories exist"""
    print("\n🔍 Checking directories...")
    
    required_dirs = ["data", "logs", "config"]
    missing_dirs = []
    
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            print(f"❌ Directory '{dir_name}' not found")
            missing_dirs.append(dir_name)
        else:
            print(f"✅ Directory '{dir_name}' exists")
    
    # Try to create missing directories
    for dir_name in missing_dirs:
        try:
            Path(dir_name).mkdir(exist_ok=True)
            print(f"✅ Created directory '{dir_name}'")
        except Exception as e:
            print(f"❌ Failed to create directory '{dir_name}': {e}")
            return False
    
    return True

def check_mt5_connection():
    """Check if MT5 connection can be established (basic check)"""
    print("\n🔍 Checking MT5 connection...")
    
    try:
        # Try to import MT5
        mt5_available = False
        try:
            import MetaTrader5  # type: ignore
            mt5_available = True
        except ImportError:
            pass
        
        if mt5_available:
            print("✅ MT5 package imported successfully")
            print("ℹ️  Note: Full MT5 connection test requires MT5 terminal to be running")
            return True
        else:
            print("❌ MT5 package not found")
            print("   Please install it using: pip install metatrader5")
            return False
    except Exception as e:
        print(f"❌ Failed to import MT5 package: {e}")
        print("   Please ensure metatrader5 package is installed")
        return False

def check_data_files():
    """Check if required data files exist"""
    print("\n🔍 Checking data files...")
    
    data_dir = Path("data")
    if not data_dir.exists():
        print("⚠️  Data directory not found")
        return True
    
    # Look for any CSV files in data directory
    csv_files = list(data_dir.glob("*.csv"))
    if csv_files:
        print(f"✅ Found {len(csv_files)} data files in data directory")
        for csv_file in csv_files[:3]:  # Show first 3 files
            print(f"   - {csv_file.name}")
        if len(csv_files) > 3:
            print(f"   ... and {len(csv_files) - 3} more files")
    else:
        print("⚠️  No data files found in data directory")
        print("   Please run 'python export_mt5_data.py' to generate data files")
    
    return True

def main():
    """Main validation function"""
    print("=" * 60)
    print("🤖 roboquant System Setup Validation")
    print("=" * 60)
    
    checks = [
        check_python_version,
        check_required_packages,
        check_environment_variables,
        check_directories,
        check_mt5_connection,
        check_data_files,
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"❌ Error during check: {e}")
            results.append(False)
    
    print("\n" + "=" * 60)
    print("📋 Validation Summary")
    print("=" * 60)
    
    if all(results):
        print("✅ All checks passed! Your environment is ready for roboquant.")
        return 0
    else:
        failed_count = len([r for r in results if not r])
        print(f"❌ {failed_count} check(s) failed. Please review the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())