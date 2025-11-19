"""Fix imports after project reorganization"""
import os
import re

# Mapping of old imports to new imports
IMPORT_MAPPINGS = {
    'from mt5_utils import': 'from brokers.mt5_utils import',
    'from mt5_core import': 'from brokers.mt5_core import',
    'from mt5_connection_manager import': 'from brokers.mt5_connection_manager import',
    'from ftmo_manager import': 'from risk.ftmo_manager import',
    'from safety import': 'from risk.safety import',
    'from adaptive_risk import': 'from risk.adaptive_risk import',
    'from risk_orders import': 'from risk.risk_orders import',
    'from trade_scorer import': 'from analysis.trade_scorer import',
    'from post_mortem import': 'from analysis.post_mortem import',
    'from performance_dashboard import': 'from analysis.performance_dashboard import',
    'from alerts import': 'from services.alerts import',
    'from news_filter import': 'from services.news_filter import',
    'from ml_engine import': 'from services.ml_engine import',
    'from api_cache import': 'from services.api_cache import',
    'from database_service import': 'from services.database_service import',
    'from error_handler import': 'from services.error_handler import',
    'from security_manager import': 'from services.security_manager import',
    'from webhook_receiver import': 'from services.webhook_receiver import',
    'from config_manager import': 'from config.config_manager import',
    'from set_file_manager import': 'from config.set_file_manager import',
    'from logging_config import': 'from config.logging_config import',
    'from donchian_strategy import': 'from core.donchian_strategy import',
    'from session_filter import': 'from core.session_filter import',
    'from market_regime import': 'from core.market_regime import',
}

def fix_file_imports(filepath):
    """Fix imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for old, new in IMPORT_MAPPINGS.items():
            content = content.replace(old, new)
        
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✓ Fixed: {filepath}")
            return True
        return False
    except Exception as e:
        print(f"✗ Error in {filepath}: {e}")
        return False

def main():
    """Fix imports in all Python files"""
    dirs_to_scan = ['core', 'brokers', 'risk', 'analysis', 'services', 'scripts', 'tests_integration', 'config']
    
    fixed_count = 0
    for dir_name in dirs_to_scan:
        if not os.path.exists(dir_name):
            continue
        
        for filename in os.listdir(dir_name):
            if filename.endswith('.py') and filename != '__init__.py':
                filepath = os.path.join(dir_name, filename)
                if fix_file_imports(filepath):
                    fixed_count += 1
    
    print(f"\n✓ Fixed {fixed_count} files")

if __name__ == '__main__':
    main()
