import logging
import json
import os
from datetime import datetime, time, timezone, timedelta
from typing import Dict, Optional, Tuple
import pytz

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

class FTMOManager:
    """FTMO Challenge Compliance Manager"""
    
    def __init__(self, config_file: str = "ftmo_config.json", ftmo_starting_balance: float = 10000.0):
        self.config_file = config_file
        self.midnight_balance = 0.0
        self.initial_balance = 0.0
        self.ftmo_starting_balance = ftmo_starting_balance  # The actual FTMO account starting balance
        self.trading_days = 0
        self.last_reset_date = None
        self.daily_losses = {}  # date -> loss
        self.trading_blocked_until = None
        self.load_config()
        
        # Initialize balances on first run
        if self.initial_balance == 0.0:
            account_info = mt5.account_info()  # type: ignore
            if account_info:
                self.initial_balance = account_info.balance
                self.midnight_balance = account_info.balance
                self.last_reset_date = datetime.now().date()
                self.save_config()
    
    def load_config(self):
        """Load FTMO configuration from file"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.midnight_balance = config.get('midnight_balance', 0.0)
                    self.initial_balance = config.get('initial_balance', 0.0)
                    self.ftmo_starting_balance = config.get('ftmo_starting_balance', 10000.0)
                    self.trading_days = config.get('trading_days', 0)
                    self.last_reset_date = datetime.fromisoformat(config['last_reset_date']) if config.get('last_reset_date') else None
                    self.daily_losses = config.get('daily_losses', {})
                    blocked_until = config.get('trading_blocked_until')
                    self.trading_blocked_until = datetime.fromisoformat(blocked_until) if blocked_until else None
            except Exception as e:
                logging.warning(f"Failed to load FTMO config: {e}")
    
    def save_config(self):
        """Save FTMO configuration to file"""
        try:
            config = {
                'midnight_balance': self.midnight_balance,
                'initial_balance': self.initial_balance,
                'ftmo_starting_balance': self.ftmo_starting_balance,
                'trading_days': self.trading_days,
                'last_reset_date': self.last_reset_date.isoformat() if self.last_reset_date else None,
                'daily_losses': self.daily_losses,
                'trading_blocked_until': self.trading_blocked_until.isoformat() if self.trading_blocked_until else None
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            logging.warning(f"Failed to save FTMO config: {e}")
    
    def update_daily_balance(self):
        """Update midnight balance at 00:00 CET"""
        cet = pytz.timezone('CET')
        now_cet = datetime.now(cet)
        today = now_cet.date()
        
        # Reset at midnight CET
        if self.last_reset_date != today:
            account_info = mt5.account_info()  # type: ignore
            if account_info:
                self.midnight_balance = account_info.balance
                self.last_reset_date = today
                self.trading_days += 1
                self.save_config()
                logging.info(f"FTMO daily reset: Midnight balance updated to {self.midnight_balance}")
    
    def get_current_metrics(self) -> Dict:
        """Get current FTMO compliance metrics"""
        account_info = mt5.account_info()  # type: ignore
        if not account_info:
            return {}
        
        current_balance = account_info.balance
        equity = account_info.equity
        
        # Calculate daily loss from midnight balance
        cet = pytz.timezone('CET')
        today_str = datetime.now(cet).strftime('%Y-%m-%d')
        daily_loss = ((current_balance - self.midnight_balance) / self.midnight_balance * 100) if self.midnight_balance > 0 else 0
        
        # Calculate overall drawdown from FTMO starting balance (clamped at 0% if equity >= starting)
        # Drawdown = max(0, (Starting Balance - Equity) / Starting Balance * 100)
        floor_balance = self.ftmo_starting_balance * 0.90
        overall_drawdown = max(0.0, ((self.ftmo_starting_balance - equity) / self.ftmo_starting_balance * 100)) if self.ftmo_starting_balance > 0 else 0
        buffer_to_floor_usd = max(0.0, equity - floor_balance)
        buffer_to_floor_pct = (buffer_to_floor_usd / self.ftmo_starting_balance * 100) if self.ftmo_starting_balance > 0 else 0
        
        # Load performance limits from configuration
        try:
            from config.set_file_manager import get_set_manager
            cfg = get_set_manager()
            set_file = os.getenv('ROBOQUANT_SET_FILE')
            if set_file:
                cfg.load_set_file(set_file)
                daily_loss_limit = cfg.get('performance.daily_loss_limit_pct', -4.0)
                drawdown_limit = cfg.get('performance.overall_dd_limit_pct', 10.0)
                logging.debug(f"Loaded performance limits from {set_file}: daily={daily_loss_limit}%, drawdown={drawdown_limit}%")
            else:
                # Fallback to defaults if no set file
                daily_loss_limit = -4.0
                drawdown_limit = 10.0
        except Exception as e:
            logging.warning(f"Failed to load performance limits from set file: {e}. Using defaults.")
            daily_loss_limit = -4.0
            drawdown_limit = 10.0
        
        return {
            'current_balance': current_balance,
            'equity': equity,
            'midnight_balance': self.midnight_balance,
            'initial_balance': self.initial_balance,
            'ftmo_starting_balance': self.ftmo_starting_balance,
            'daily_loss_percent': daily_loss,
            'overall_drawdown_percent': overall_drawdown,
            'buffer_to_floor_usd': buffer_to_floor_usd,
            'buffer_to_floor_pct': buffer_to_floor_pct,
            'loss_floor_balance': floor_balance,
            'trading_days': self.trading_days,
            'daily_loss_limit': daily_loss_limit,
            'drawdown_limit': drawdown_limit,
            'min_trading_days': 1       # Changed from 4 to 1 for testing
        }
    
    def is_trade_allowed(self, symbol: str = "XAUUSD") -> Tuple[bool, Optional[str]]:
        """Check if trading is allowed according to FTMO rules"""
        # Update daily balance
        self.update_daily_balance()
        
        # Get CET timezone
        cet = pytz.timezone('CET')
        now_cet = datetime.now(cet)
        
        # Check if trading is temporarily blocked (news protection)
        if self.trading_blocked_until:
            if now_cet < self.trading_blocked_until:
                return False, f"Trading blocked until {self.trading_blocked_until.strftime('%H:%M:%S')} CET (news protection)"
            else:
                self.trading_blocked_until = None
                self.save_config()
        
        # Get current metrics
        metrics = self.get_current_metrics()
        if not metrics:
            return False, "Failed to get account information"
        
        # Check trading hours (from configuration)
        from config.config_manager import config_manager
        
        # Try to get trading hours from set file first, fallback to config_manager
        try:
            from config.set_file_manager import get_set_manager
            cfg = get_set_manager()
            # Load set file if specified
            set_file = os.getenv('ROBOQUANT_SET_FILE')
            if set_file:
                try:
                    cfg.load_set_file(set_file)
                    trading_start_hour = cfg.get('trading_hours.start', config_manager.get('TRADING_HOUR_START', 0))
                    trading_end_hour = cfg.get('trading_hours.end', config_manager.get('TRADING_HOUR_END', 23))
                    logging.debug(f"Loaded trading hours from set file {set_file}: {trading_start_hour}-{trading_end_hour}")
                except Exception as e:
                    logging.warning(f"Failed to load set file {set_file}: {e}")
                    trading_start_hour = config_manager.get('TRADING_HOUR_START', 0)
                    trading_end_hour = config_manager.get('TRADING_HOUR_END', 23)
            else:
                trading_start_hour = config_manager.get('TRADING_HOUR_START', 0)
                trading_end_hour = config_manager.get('TRADING_HOUR_END', 23)
        except Exception as e:
            logging.warning(f"Failed to load set file configuration: {e}")
            # Fallback to config_manager if set file manager is not available
            trading_start_hour = config_manager.get('TRADING_HOUR_START', 0)
            trading_end_hour = config_manager.get('TRADING_HOUR_END', 23)
        
        trading_start = time(trading_start_hour, 0)
        # Fix: When end_hour is 23, we want to include the entire 23rd hour (until 23:59:59)
        if trading_end_hour == 23:
            trading_end = time(23, 59, 59)
        else:
            trading_end = time(trading_end_hour, 0)
        
        if not (trading_start <= now_cet.time() <= trading_end):
            return False, f"Outside trading hours ({trading_start.strftime('%H:%M')}-{trading_end.strftime('%H:%M')} CET)"
        
        # Check daily loss limit (-4%)
        if metrics['daily_loss_percent'] < metrics['daily_loss_limit']:
            return False, f"Daily loss limit exceeded: {metrics['daily_loss_percent']:.2f}% < {metrics['daily_loss_limit']}%"
        
        # Check overall drawdown limit
        # Circuit breaker: block at 5% below the configured limit to prevent breach
        circuit_breaker_threshold = max(0, metrics['drawdown_limit'] - 0.5)
        if metrics['overall_drawdown_percent'] >= circuit_breaker_threshold:
            return False, f"Circuit breaker triggered: Overall drawdown {metrics['overall_drawdown_percent']:.2f}% >= {circuit_breaker_threshold:.2f}% (limit: {metrics['drawdown_limit']}%)"
        if metrics['overall_drawdown_percent'] >= metrics['drawdown_limit']:
            return False, f"Overall drawdown limit exceeded: {metrics['overall_drawdown_percent']:.2f}% >= {metrics['drawdown_limit']}%"
        
        # Check minimum trading days
        if metrics['trading_days'] < metrics['min_trading_days']:
            return False, f"Minimum trading days not met: {metrics['trading_days']} < {metrics['min_trading_days']}"
        
        # Check spread - REMOVED as per user request
        # tick = mt5.symbol_info_tick(symbol)  # type: ignore
        # if tick:
        #     symbol_info = mt5.symbol_info(symbol)  # type: ignore
        #     if symbol_info:
        #         point = symbol_info.point
        #         spread_points = (tick.ask - tick.bid) / point if point > 0 else 0
        #         if spread_points > 50:  # 50 points max spread
        #             return False, f"Spread too high: {spread_points:.1f} points > 50 points"
        
        return True, None
    
    def block_trading_during_news(self, event_time: datetime):
        """Block trading 2 minutes before and after high-impact news"""
        cet = pytz.timezone('CET')
        event_time_cet = event_time.astimezone(cet)
        
        # Block 2 minutes before and after
        start_block = event_time_cet - timedelta(minutes=2)
        end_block = event_time_cet + timedelta(minutes=2)
        
        # Update blocking period if it's later than current
        if not self.trading_blocked_until or end_block > self.trading_blocked_until:
            self.trading_blocked_until = end_block
            self.save_config()
            logging.info(f"Trading blocked until {end_block.strftime('%H:%M:%S')} CET due to high-impact news")
    
    def get_ftmo_dashboard(self) -> str:
        """Get FTMO compliance dashboard"""
        metrics = self.get_current_metrics()
        if not metrics:
            return "Failed to get metrics"
        
        cet = pytz.timezone('CET')
        now_cet = datetime.now(cet)
        
        dashboard = f"""
=== FTMO CHALLENGE DASHBOARD ===
Time (CET): {now_cet.strftime('%Y-%m-%d %H:%M:%S')}
Trading Days: {metrics['trading_days']}/4

BALANCES:
  FTMO Starting: ${metrics['ftmo_starting_balance']:.2f}
  Initial Balance: ${metrics['initial_balance']:.2f}
  Midnight: ${metrics['midnight_balance']:.2f}
  Current: ${metrics['current_balance']:.2f}
  Equity: ${metrics['equity']:.2f}
  Profit vs Start: ${metrics['equity'] - metrics['ftmo_starting_balance']:.2f}

METRICS:
  Daily Loss: {metrics['daily_loss_percent']:.2f}% (Limit: {metrics['daily_loss_limit']:.1f}%)
  Overall Drawdown: {metrics['overall_drawdown_percent']:.2f}% (Limit: {metrics['drawdown_limit']}%)
  Buffer to $9,000 floor: ${metrics['buffer_to_floor_usd']:.2f} ({metrics['buffer_to_floor_pct']:.2f}%)
  
STATUS: {"TRADE ALLOWED" if self.is_trade_allowed()[0] else "TRADING BLOCKED"}
"""
        return dashboard

    def get_risk_scale_factor(self) -> float:
        """
        Get risk scaling factor based on current drawdown.
        Reduces risk as drawdown increases to protect capital.
        
        Returns:
            float: Risk multiplier (0.25 to 1.0)
        """
        metrics = self.get_current_metrics()
        if not metrics:
            return 1.0
        
        dd = metrics['overall_drawdown_percent']
        
        # Risk scaling tiers:
        # DD < 3%: 100% risk
        # 3-5%: 70% risk
        # 5-7%: 50% risk
        # 7-8%: 35% risk
        # >8%: 25% risk (emergency)
        if dd < 3.0:
            return 1.0
        elif dd < 5.0:
            return 0.7
        elif dd < 7.0:
            return 0.5
        elif dd < 8.0:
            return 0.35
        else:
            return 0.25

# Global FTMO manager instance
ftmo_manager = FTMOManager()