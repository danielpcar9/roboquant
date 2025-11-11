# safety.py
import os
import json
import logging
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5  # type: ignore

KILL_SWITCH_FILE = os.path.join(os.path.dirname(__file__), 'config', 'kill_switch.flag')

class Safety:
    
    def __init__(self, mt5_module=None, hwm_file='hwm.json', daily_file='daily_eq.json',
                 max_dd_pct=10.0, max_daily_loss_pct=3.0, max_concurrent=3, corr_threshold=0.75):
        self.mt5 = mt5_module if mt5_module else mt5
        self.hwm_file = os.path.join(os.path.dirname(__file__), hwm_file)
        self.daily_file = os.path.join(os.path.dirname(__file__), daily_file)
        self.max_dd_pct = max_dd_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_concurrent = max_concurrent
        self.corr_threshold = corr_threshold
    
    def check_kill_switch(self):
        if os.path.exists(KILL_SWITCH_FILE):
            logging.critical('KILL SWITCH ACTIVADO')
            return False, 'kill_switch'
        return True, None
    
    def _load_hwm(self):
        if os.path.exists(self.hwm_file):
            try:
                with open(self.hwm_file, 'r') as f:
                    data = json.load(f)
                    return float(data.get('hwm', 0.0))
            except Exception as e:
                logging.debug("Error cargando HWM: %s", e)
                return 0.0
        return 0.0
    
    def _save_hwm(self, value):
        data = {
            'hwm': float(value),
            'timestamp': datetime.utcnow().isoformat()
        }
        os.makedirs(os.path.dirname(self.hwm_file), exist_ok=True)
        with open(self.hwm_file, 'w') as f:
            json.dump(data, f)
    
    def check_global_drawdown(self):
        info = self.mt5.account_info()  # type: ignore
        if info is None:
            logging.warning("No se pudo obtener account_info")
            return False, 'no_account_info'
        
        equity = float(info.equity)
        hwm = self._load_hwm() or equity
        
        if equity > hwm:
            self._save_hwm(equity)
            hwm = equity
        
        dd_pct = ((hwm - equity) / hwm * 100) if hwm > 0 else 0.0
        
        if dd_pct >= self.max_dd_pct:
            logging.error("Drawdown global %.2f%% excede limite %.2f%%", dd_pct, self.max_dd_pct)
            return False, 'global_dd_' + str(round(dd_pct, 2))
        
        return True, None
    
    def check_daily_loss(self):
        info = self.mt5.account_info()  # type: ignore
        if info is None:
            return False, 'no_account_info'
        
        balance = float(info.balance)
        today = datetime.utcnow().date().isoformat()
        
        if os.path.exists(self.daily_file):
            try:
                with open(self.daily_file, 'r') as f:
                    data = json.load(f)
                    start_balance = float(data.get('balance', balance))
                    start_date = data.get('date')
            except Exception:
                start_balance, start_date = balance, None
        else:
            start_balance, start_date = balance, None
        
        if start_date != today:
            os.makedirs(os.path.dirname(self.daily_file), exist_ok=True)
            with open(self.daily_file, 'w') as f:
                json.dump({'balance': balance, 'date': today}, f)
            return True, None
        
        loss_pct = ((start_balance - balance) / start_balance * 100) if start_balance > 0 else 0.0
        
        if loss_pct >= self.max_daily_loss_pct:
            logging.error("Perdida diaria %.2f%% excede limite %.2f%%", loss_pct, self.max_daily_loss_pct)
            return False, 'daily_loss_' + str(round(loss_pct, 2))
        
        return True, None
    
    def check_concurrent_positions(self):
        positions = self.mt5.positions_get()  # type: ignore  # type: ignore
        count = len(positions) if positions else 0
        
        if count >= self.max_concurrent:
            logging.warning("Posiciones concurrentes (%d) alcanzan limite (%d)", count, self.max_concurrent)
            return False, 'concurrent_' + str(count)
        
        return True, None
    
    def get_returns(self, symbol, days=90):
        end = datetime.utcnow()
        start = end - timedelta(days=days)
        
        rates = self.mt5.copy_rates_range(symbol, self.mt5.TIMEFRAME_D1, start, end)  # type: ignore  # type: ignore
        
        if rates is None or len(rates) == 0:
            logging.debug("No se obtuvieron rates para %s", symbol)
            return np.array([])
        
        df = pd.DataFrame(rates)
        returns = df['close'].pct_change().dropna().values
        
        return returns
    
    def correlation_ok(self, new_symbol, threshold=None):
        threshold = threshold or self.corr_threshold
        
        open_positions = self.mt5.positions_get()  # type: ignore  # type: ignore
        if not open_positions:
            return True, None, None
        
        new_returns = self.get_returns(new_symbol)
        if new_returns.size == 0:
            logging.warning("No hay datos historicos para %s", new_symbol)
            return True, None, None
        
        for pos in open_positions:
            try:
                # Skip correlation check for the same symbol
                if pos.symbol == new_symbol:
                    continue
                    
                existing_returns = self.get_returns(pos.symbol)
                
                if existing_returns.size == 0:
                    continue
                
                common_len = min(len(new_returns), len(existing_returns))
                if common_len < 30:
                    continue
                
                # Convert to numpy arrays to ensure compatibility
                new_returns_array = np.array(new_returns[-common_len:])
                existing_returns_array = np.array(existing_returns[-common_len:])
                
                corr_matrix = np.corrcoef(new_returns_array, existing_returns_array)
                corr = corr_matrix[0, 1] if corr_matrix.size > 1 else 0.0
                
                if abs(corr) > threshold:
                    logging.warning("Alta correlacion (%.2f) entre %s y %s", corr, new_symbol, pos.symbol)
                    return False, float(corr), pos.symbol
                
            except Exception as e:
                logging.debug("Error verificando correlacion con %s: %s", pos.symbol, e)
                continue
        
        return True, None, None
    
    def check_all(self, new_symbol=None):
        ok, reason = self.check_kill_switch()
        if not ok:
            return False, reason
        
        ok, reason = self.check_global_drawdown()
        if not ok:
            return False, reason
        
        ok, reason = self.check_daily_loss()
        if not ok:
            return False, reason
        
        ok, reason = self.check_concurrent_positions()
        if not ok:
            return False, reason
        
        if new_symbol:
            ok, corr, other_symbol = self.correlation_ok(new_symbol)
            if not ok:
                corr_str = str(round(corr, 2)) if corr is not None else "unknown"
                other_symbol_str = other_symbol if other_symbol is not None else "unknown"
                return False, 'corr_' + corr_str + '_with_' + other_symbol_str
        
        return True, None


def activate_kill_switch(reason="manual"):
    os.makedirs(os.path.dirname(KILL_SWITCH_FILE), exist_ok=True)
    
    with open(KILL_SWITCH_FILE, 'w') as f:
        f.write("Activated at: " + datetime.utcnow().isoformat() + "\n")
        f.write("Reason: " + reason + "\n")
    
    logging.critical("KILL SWITCH ACTIVADO: %s", reason)


def deactivate_kill_switch():
    if os.path.exists(KILL_SWITCH_FILE):
        os.remove(KILL_SWITCH_FILE)
        logging.info("Kill switch desactivado")
        return True
    return False


class FTMOSafety(Safety):
    """FTMO Challenge Safety Implementation"""
    
    def __init__(self, mt5_module=None):
        # Initialize with FTMO-specific parameters
        super().__init__(mt5_module, max_dd_pct=9.0, max_daily_loss_pct=4.0, max_concurrent=3, corr_threshold=0.75)
        
        # Import FTMO manager
        try:
            from ftmo_manager import ftmo_manager
            self.ftmo_manager = ftmo_manager
        except ImportError:
            logging.error("Failed to import FTMO manager")
            self.ftmo_manager = None
    
    def check_ftmo_rules(self, symbol: str = "XAUUSD"):
        """Check all FTMO challenge rules"""
        if not self.ftmo_manager:
            return True, None
        
        return self.ftmo_manager.is_trade_allowed(symbol)
    
    def check_all(self, new_symbol=None):
        """Override check_all to include FTMO rules"""
        # Check standard safety rules first
        ok, reason = super().check_all(new_symbol)
        if not ok:
            return False, reason
        
        # Check FTMO specific rules
        if new_symbol is not None:
            ok, reason = self.check_ftmo_rules(new_symbol)
            if not ok:
                return False, reason
        
        return True, None
        
    
    def update_after_trade(self):
        """Update metrics after executing a trade"""
        if self.ftmo_manager:
            self.ftmo_manager.save_config()