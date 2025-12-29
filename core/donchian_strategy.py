#!/usr/bin/env python3
"""
Refactorized Donchian Strategy following SOLID principles and OOP best practices.
This implementation separates concerns into distinct classes with single responsibilities.
"""

import time
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass

# Import MetaTrader5 (official package name)
import MetaTrader5 as mt5

from brokers.mt5_utils import build_and_send_order, normalize_volume, monitor_and_update_stops, place_pending_order, cancel_expired_pending_orders, update_trailing_stops, MT5Gateway
from risk.safety import Safety
# Import security manager
from services.security_manager import SecureCredentialManager, InputValidator, sanitize_error_message, RateLimiter
# Import config manager
from config.config_manager import config_manager
# Import set file manager
from config.set_file_manager import get_set_manager
# Import error handler
from services.error_handler import handle_exception, retry_with_exponential_backoff, MT5ConnectionError, OrderExecutionError
# Import news filter
from services.news_filter import news_filter
# Import market regime detector
from core.market_regime import market_regime_detector

# Import consolidated performance monitoring
from brokers.mt5_core import strategy_performance_monitor as performance_monitor

# Import quantitative engine
from core.quant_engine import QuantitativeEngine

# Set up logging with more detailed level
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')

# Load environment variables and initialize security manager
credential_manager = SecureCredentialManager()

# Global variable for quantitative optimal lot size
QUANT_OPTIMAL_LOTS = None

# Global dict to store entry scores for trades
TRADE_ENTRY_SCORES = {}

# Global variable to store current entry score for ticket association
CURRENT_ENTRY_SCORE = None


@dataclass
class StrategyConfig:
    """Configuration data class for strategy parameters"""
    donchian_period: int = config_manager.get('DONCHIAN_PERIOD')
    momentum_period: int = config_manager.get('MOMENTUM_PERIOD')
    sample_period: int = config_manager.get('SAMPLE_PERIOD')
    risk_percent: float = config_manager.get('RISK_PERCENT')
    use_risk_management: bool = config_manager.get('USE_RISK_MANAGEMENT')
    lots: float = config_manager.get('LOTS')
    stop_loss_points: int = config_manager.get('STOP_LOSS_POINTS')
    take_profit_points: int = config_manager.get('TAKE_PROFIT_POINTS')
    timeframe_name: str = config_manager.get('TIMEFRAME')
    breakout_threshold: float = config_manager.get('BREAKOUT_THRESHOLD')
    trading_hour_start: int = config_manager.get('TRADING_HOUR_START')
    trading_hour_end: int = config_manager.get('TRADING_HOUR_END')
    magic_number: int = config_manager.get('MAGIC_NUMBER')
    event_size_factor: float = config_manager.get('EVENT_SIZE_FACTOR')
    event_sl_atr_multiplier: float = config_manager.get('EVENT_SL_ATR_MULTIPLIER')
    event_breakout_atr_threshold: float = config_manager.get('EVENT_BREAKOUT_ATR_THRESHOLD')
    event_volume_spike_factor: float = config_manager.get('EVENT_VOLUME_SPIKE_FACTOR')
    max_spread_points: float = config_manager.get('MAX_SPREAD_POINTS')


class MarketDataService:
    """Responsible for fetching and calculating market indicators. Single Responsibility Principle."""
    
    def __init__(self, mt5_module=mt5):
        self.mt5 = mt5_module
        self.timeframe = self._get_timeframe_from_config()
    
    def _get_timeframe_from_config(self):
        """Convert timeframe name to MT5 constant"""
        timeframe_name = config_manager.get('TIMEFRAME')
        timeframe_map = {
            'M1': self.mt5.TIMEFRAME_M1,
            'M5': self.mt5.TIMEFRAME_M5,
            'M15': self.mt5.TIMEFRAME_M15,
            'M30': self.mt5.TIMEFRAME_M30,
            'H1': self.mt5.TIMEFRAME_H1,
            'H4': self.mt5.TIMEFRAME_H4,
            'D1': self.mt5.TIMEFRAME_D1,
            'W1': self.mt5.TIMEFRAME_W1,
            'MN1': self.mt5.TIMEFRAME_MN1
        }
        return timeframe_map.get(timeframe_name.upper(), self.mt5.TIMEFRAME_M5)
    
    @handle_exception
    @performance_monitor
    def get_donchian_channels(self, symbol: str, period: int) -> Tuple[Optional[float], Optional[float]]:
        """Calculate Donchian channels"""
        logging.debug(f"Calculating Donchian channels for {symbol} with period {period}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period)
        if rates is None or len(rates) < period:
            logging.error(f"Failed to get rate data for Donchian calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
            return None, None
        
        highs = [rate['high'] for rate in rates]
        lows = [rate['low'] for rate in rates]
        
        upper_channel = max(highs)
        lower_channel = min(lows)
        
        logging.debug(f"Calculated channels - Upper: {upper_channel}, Lower: {lower_channel}")
        return upper_channel, lower_channel
    
    @handle_exception
    @performance_monitor
    def calculate_momentum(self, symbol: str, lookback: int) -> float:
        """Calculate average momentum over a lookback period"""
        logging.debug(f"Calculating momentum for {symbol} with lookback {lookback}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, lookback)
        if rates is None or len(rates) < lookback:
            logging.error(f"Failed to get rate data for momentum calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
            return 0
        
        sum_momentum = 0
        for rate in rates:
            body = abs(rate['close'] - rate['open'])
            sum_momentum += body
        
        momentum = sum_momentum / lookback if lookback > 0 else 0
        logging.debug(f"Calculated momentum: {momentum}")
        return momentum
    
    @handle_exception
    @performance_monitor
    def calculate_atr(self, symbol: str, period: int = 14) -> Optional[float]:
        """Calculate Average True Range"""
        logging.debug(f"Calculating ATR for {symbol} with period {period}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, period + 1)
        if rates is None or len(rates) < period + 1:
            logging.error(f"Failed to get rate data for ATR calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
            return None
        
        atr_values = []
        for i in range(1, len(rates)):
            tr1 = rates[i]['high'] - rates[i]['low']
            tr2 = abs(rates[i]['high'] - rates[i-1]['close'])
            tr3 = abs(rates[i]['low'] - rates[i-1]['close'])
            tr = max(tr1, tr2, tr3)
            atr_values.append(tr)
        
        atr = sum(atr_values) / len(atr_values) if atr_values else 0
        logging.debug(f"ATR for {symbol}: {atr:.5f}")
        return atr
    
    @handle_exception
    @performance_monitor
    def get_current_price(self, symbol: str, order_type: str) -> Optional[float]:
        """Get current price based on order type"""
        logging.debug(f"Getting current price for {symbol}, order type: {order_type}")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return None
        
        price = tick.ask if order_type == "BUY" else tick.bid
        logging.debug(f"Current price for {symbol}: {price}")
        return price
    
    @handle_exception
    @performance_monitor
    def get_spread(self, symbol: str) -> Optional[float]:
        """Get current spread"""
        logging.debug(f"Calculating spread for {symbol}")
        tick = self.mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error(f"Failed to get tick data for {symbol}")
            return None
        
        symbol_info = self.mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return None
        
        point = symbol_info.point
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        spread_points = (tick.ask - tick.bid) / point if point > 0 else 0
        logging.debug(f"Spread for {symbol}: {spread_points:.2f} points")
        return spread_points
    
    @handle_exception
    @performance_monitor
    def get_volume_stats(self, symbol: str, lookback: int = 20) -> Tuple[Optional[float], Optional[float]]:
        """Get volume statistics"""
        logging.debug(f"Calculating volume stats for {symbol} with lookback {lookback}")
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, lookback)
        if rates is None or len(rates) < lookback:
            logging.error(f"Failed to get rate data for volume calculation. Rates: {rates}, Length: {len(rates) if rates else 0}")
            return None, None
        
        volumes = [rate['tick_volume'] for rate in rates]
        current_volume = volumes[-1] if volumes else 0
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        
        logging.debug(f"Volume stats for {symbol} - Current: {current_volume}, Average: {avg_volume:.2f}")
        return current_volume, avg_volume
    
    @handle_exception
    @performance_monitor
    def detect_engulfing(self, symbol: str) -> Tuple[bool, bool]:
        """Detect bullish and bearish engulfing patterns"""
        rates = self.mt5.copy_rates_from_pos(symbol, self.timeframe, 1, 3)
        if rates is None or len(rates) < 2:
            logging.error(f"Failed to get rate data for engulfing pattern detection. Rates: {rates}, Length: {len(rates) if rates else 0}")
            return False, False
        
        prev, current = rates[-2], rates[-1]
        
        # Envolvente alcista (bullish)
        bullish = (prev['close'] < prev['open'] and 
                   current['close'] > current['open'] and
                   current['open'] < prev['close'] and
                   current['close'] > prev['open'])
        
        # Envolvente bajista (bearish)
        bearish = (prev['close'] > prev['open'] and
                   current['close'] < current['open'] and
                   current['open'] > prev['close'] and
                   current['close'] < prev['open'])
        
        return bullish, bearish


class RiskCalculator:
    """Responsible for all risk-related calculations. Single Responsibility Principle."""
    
    def __init__(self, market_data_service: MarketDataService):
        self.market_data = market_data_service
    
    @handle_exception
    def calculate_dynamic_stops(self, symbol: str, entry_price: float, order_type: str, atr: float) -> Tuple[float, float]:
        """
        Calculate dynamic SL/TP based on ATR and risk profile.
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            order_type: "BUY" or "SELL"
            atr: Average True Range value
        
        Returns:
            tuple: (sl_price, tp_price)
        """
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error(f"Failed to get symbol info for {symbol}")
            # Fallback to ATR-based values with default multipliers
            point = 0.01 if 'JPY' not in symbol else 0.001
            # For NASDAQ, adjust point value
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            # Use default ATR multipliers for fallback
            sl_multiplier = 3.0  # LOW RISK profile default
            tp_multiplier = 6.0  # LOW RISK profile default
            # Estimate ATR if we can't get it
            estimated_atr = 5.0  # Default ATR estimate
            sl_distance = sl_multiplier * estimated_atr
            tp_distance = tp_multiplier * estimated_atr
            
            if order_type == "BUY":
                sl_price = entry_price - (sl_distance * point)
                tp_price = entry_price + (tp_distance * point)
            else:
                sl_price = entry_price + (sl_distance * point)
                tp_price = entry_price - (tp_distance * point)
            return sl_price, tp_price
        
        point = symbol_info.point
        
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        
        # Determine if we're using LOW RISK (default) or HIGH RISK (aggressive) profile
        # Based on the risk_per_trade_pct in the current configuration
        risk_percent = config_manager.get('RISK_PERCENT')
        risk_profile = "HIGH" if risk_percent > 1.0 else "LOW"
        
        # Get ATR multipliers from configuration
        cfg = get_set_manager()
        set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
        
        try:
            if set_file:
                cfg.load_set_file(set_file)
                
            if risk_profile == "LOW":  # Default profile
                sl_multiplier = cfg.get('strategy.sl_atr_multiplier', 3.0)
                tp_multiplier = cfg.get('strategy.tp_atr_multiplier', 6.0)
            else:  # HIGH RISK (aggressive)
                sl_multiplier = cfg.get('strategy.sl_atr_multiplier', 2.0)
                tp_multiplier = cfg.get('strategy.tp_atr_multiplier', 1.5)
        except Exception as e:
            logging.warning(f"Failed to load ATR multipliers from config, using defaults: {e}")
            # Fallback to configuration-based defaults
            if risk_profile == "LOW":
                sl_multiplier = config_manager.get('SL_ATR_MULTIPLIER', 3.0)
                tp_multiplier = config_manager.get('TP_ATR_MULTIPLIER', 6.0)
            else:
                sl_multiplier = config_manager.get('SL_ATR_MULTIPLIER', 2.0)
                tp_multiplier = config_manager.get('TP_ATR_MULTIPLIER', 1.5)
        
        # Calculate SL/TP distances based on ATR multipliers
        sl_distance = sl_multiplier * atr
        tp_distance = tp_multiplier * atr
        
        sl_price = entry_price - sl_distance if order_type == "BUY" else entry_price + sl_distance
        tp_price = entry_price + tp_distance if order_type == "BUY" else entry_price - tp_distance
        
        logging.info(f"Dynamic stops calculated - Profile: {risk_profile}, SL: {sl_price:.5f}, TP: {tp_price:.5f}")
        return sl_price, tp_price
    
    @handle_exception
    def compute_lot_size(self, balance: float, risk_pct: float, sl_distance: float, symbol: str) -> float:
        """Calculate lot size based on risk percentage and stop loss distance"""
        
        # Check if quantitative optimal lot size is available
        import core.donchian_strategy as ds_module
        if hasattr(ds_module, 'QUANT_OPTIMAL_LOTS') and ds_module.QUANT_OPTIMAL_LOTS is not None:
            quant_lots = ds_module.QUANT_OPTIMAL_LOTS
            logging.info(f"Using quantitative optimal lot size: {quant_lots:.3f}")
            
            # Validate and return quantitative lot size
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                logging.error(f"Failed to get symbol info for {symbol}")
                return 0.01  # Seguridad: mínimo absoluto
            
            # Apply broker limits to quantitative lot size
            min_lot = symbol_info.volume_min
            max_lot = symbol_info.volume_max or quant_lots
            
            # Apply safety limits
            max_allowed_lots = 0.30  # Safety limit
            quant_lots = max(min_lot, min(quant_lots, max_lot, max_allowed_lots))
            
            normalized_lots = normalize_volume(symbol, quant_lots)
            normalized_lots = min(normalized_lots, max_allowed_lots)
            
            logging.info(f"Quantitative lot size after validation: {normalized_lots:.3f}")
            return normalized_lots
        
        # Traditional risk-based calculation
        risk_amount = balance * (risk_pct / 100.0)
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return 0.01  # Seguridad: mínimo absoluto
        
        # For XAU/USD, 1 lot = 100 oz troy, so point value is 100
        point_value = 100.0 if 'XAU' in symbol or 'GOLD' in symbol else 1.0
        point = symbol_info.point
        
        if point == 0 or sl_distance == 0:
            logging.warning(f"Invalid point or SL distance for {symbol}, using minimum lot size")
            return 0.01
        
        # LOG DETALLADO para debugging
        logging.info(f"=== LOT CALCULATION DEBUG ===")
        logging.info(f"Symbol: {symbol}")
        logging.info(f"Balance: ${balance:.2f}")
        logging.info(f"Risk %: {risk_pct}%")
        logging.info(f"Risk Amount: ${risk_amount:.2f}")
        logging.info(f"SL Distance (price points): {sl_distance:.5f}")
        logging.info(f"Point value: {point:.5f}")
        logging.info(f"Contract multiplier: {point_value:.2f}")
        
        # Calculate lots: risk_amount / (sl_distance * point_value)
        # For XAU/USD: sl_distance is already in price points, point_value is contract size (100 oz)
        # Risk per lot = sl_distance * point_value = points * ($ per point per lot)
        # So lots = risk_amount / (sl_distance * point_value)
        lots = risk_amount / (sl_distance * point_value)
        
        logging.info(f"Raw calculated lots: {lots:.6f}")
        
        # Ensure minimum lot size
        min_lot = symbol_info.volume_min
        lots = max(lots, min_lot)
        
        logging.info(f"After min limit ({min_lot}): {lots:.6f}")
        
        # LÍMITE DE SEGURIDAD MÁXIMO - CRÍTICO PARA PROTEGER CAPITAL
        # Límite ultra conservador: máximo 0.30 lotes para protección extrema
        max_allowed_lots = 0.30
        if lots > max_allowed_lots:
            logging.warning(f"⚠️ SEGURIDAD: Lotaje {lots:.2f} excede límite {max_allowed_lots:.2f}, FORZANDO a límite")
            lots = max_allowed_lots
        
        # Ensure we don't exceed broker maximum lot size
        max_lot = symbol_info.volume_max or lots
        lots = min(lots, max_lot)
        
        logging.info(f"After max safety limit ({max_allowed_lots}): {lots:.6f}")
        
        # Normalize to broker requirements
        normalized_lots = normalize_volume(symbol, lots)
        
        logging.info(f"After normalization: {normalized_lots:.6f}")
        
        # VALIDACIÓN FINAL CRÍTICA
        if normalized_lots > max_allowed_lots:
            logging.error(f"🚨 CRÍTICO: normalize_volume retornó {normalized_lots:.2f} que excede límite {max_allowed_lots:.2f}. FORZANDO a límite.")
            normalized_lots = max_allowed_lots
        
        logging.info(f"FINAL LOT SIZE: {normalized_lots:.6f}")
        logging.info(f"=== END LOT CALCULATION ===")
        
        return normalized_lots


class SessionManager:
    """Manages trading sessions and session-based orders"""
    
    def __init__(self, mt5_gateway: MT5Gateway, market_data_service: MarketDataService, risk_calculator: RiskCalculator):
        self.mt5_gateway = mt5_gateway
        self.market_data = market_data_service
        self.risk_calc = risk_calculator
        self.session_pending_orders = {}  # Track pending orders by session
        self.last_session = None  # Track the last session
    
    @handle_exception
    @performance_monitor
    def get_current_session(self) -> Optional[str]:
        """
        Get current trading session based on UTC time
        
        Sessions:
        - Asia: 00:00-09:00 UTC
        - London: 08:00-17:00 UTC
        - New York: 13:00-22:00 UTC
        
        Returns:
            str: Current session name or None if no session
        """
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        current_minute = now.minute
        
        # Convert to total minutes for easier comparison
        total_minutes = current_hour * 60 + current_minute
        
        # Define session time ranges in minutes (UTC)
        asia_start = 0 * 60      # 00:00 UTC
        asia_end = 9 * 60        # 09:00 UTC
        london_start = 8 * 60    # 08:00 UTC
        london_end = 17 * 60     # 17:00 UTC
        ny_start = 13 * 60       # 13:00 UTC
        ny_end = 22 * 60         # 22:00 UTC
        
        # Check which session we're in
        if asia_start <= total_minutes < asia_end:
            return "Asia"
        elif london_start <= total_minutes < london_end:
            return "London"
        elif ny_start <= total_minutes < ny_end:
            return "NewYork"
        else:
            return None  # Outside all sessions
    
    @handle_exception
    @performance_monitor
    def get_session_high_low(self, symbol: str, session_name: str, days_back: int = 1) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the high/low of the previous session with fallback mechanism
        
        Args:
            symbol: Trading symbol
            session_name: Session name ("Asia", "London", "NewYork")
            days_back: How many days back to look for session (default 1)
            
        Returns:
            tuple: (session_high, session_low) or (None, None) if failed
        """
        # Define session time ranges in UTC
        session_times = {
            "Asia": {"start_hour": 0, "end_hour": 9},
            "London": {"start_hour": 8, "end_hour": 17},
            "NewYork": {"start_hour": 13, "end_hour": 22}
        }
        
        if session_name not in session_times:
            logging.error(f"Unknown session: {session_name}")
            return None, None
        
        session_info = session_times[session_name]
        
        # Try up to 3 days back if initial lookup fails
        max_days_back = min(3, days_back + 2)  # Up to 3 days back total
        
        for days in range(days_back, max_days_back + 1):
            # Calculate the date for the session we want to analyze
            now = datetime.now(timezone.utc)
            target_date = now - timedelta(days=days)
            
            # Create datetime objects for session start and end
            session_start = target_date.replace(
                hour=session_info["start_hour"], 
                minute=0, 
                second=0, 
                microsecond=0
            )
            session_end = target_date.replace(
                hour=session_info["end_hour"], 
                minute=0, 
                second=0, 
                microsecond=0
            )
            
            # Convert to timestamps for MT5
            from_ts = int(session_start.timestamp())
            to_ts = int(session_end.timestamp())
            
            # Get rates for the session
            rates = mt5.copy_rates_range(symbol, self.market_data.timeframe, from_ts, to_ts)
            if rates is not None and len(rates) > 0:
                # Calculate high and low
                session_high = max([rate['high'] for rate in rates])
                session_low = min([rate['low'] for rate in rates])
                
                logging.debug(f"{session_name} session {target_date.date()}: High={session_high:.5f}, Low={session_low:.5f}")
                return session_high, session_low
            else:
                logging.warning(f"Failed to get rate data for {session_name} session on {target_date.date()}, trying {days+1} days back")
        
        logging.error(f"Failed to get rate data for {session_name} session after trying up to {max_days_back} days back")
        return None, None
    
    @handle_exception
    @performance_monitor
    def place_session_breakout_orders(self, symbol: str, session_name: str) -> bool:
        """
        Place breakout orders based on previous session high/low
        
        Args:
            symbol: Trading symbol
            session_name: Session name ("Asia", "London", "NewYork")
        """
        # Get session high/low from previous day with fallback
        session_high, session_low = self.get_session_high_low(symbol, session_name, days_back=1)
        
        if session_high is None or session_low is None:
            logging.warning(f"Failed to get {session_name} session high/low, skipping breakout orders")
            return False
        
        # Check existing positions to avoid placing opposite orders
        positions = mt5.positions_get(symbol=symbol)
        logging.info(f"Checking positions for {symbol} - Found {len(positions) if positions else 0} positions")
        if positions:
            # Count positions by direction
            buy_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_BUY)
            sell_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_SELL)
            
            logging.info(f"Existing positions - BUY: {buy_positions}, SELL: {sell_positions}")
            
            # If we have positions in both directions, don't place any new orders
            if buy_positions > 0 and sell_positions > 0:
                logging.info("Both BUY and SELL positions exist, skipping session breakout orders to avoid conflict")
                return False
            
            # If we have a BUY position, don't place a SELL order
            if buy_positions > 0:
                logging.info("BUY position exists, will only place BUY_STOP order for session breakout")
                place_sell_order = False
            else:
                place_sell_order = True
                
            # If we have a SELL position, don't place a BUY order
            if sell_positions > 0:
                logging.info("SELL position exists, will only place SELL_STOP order for session breakout")
                place_buy_order = False
            else:
                place_buy_order = True
            
            logging.info(f"Order placement flags - BUY: {place_buy_order}, SELL: {place_sell_order}")
        else:
            # No existing positions, place both orders
            place_buy_order = True
            place_sell_order = True
            logging.info("No existing positions, will place both BUY_STOP and SELL_STOP orders")
        
        # Get symbol info for point value
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logging.error(f"Failed to get symbol info for {symbol}")
            return False
        
        point = symbol_info.point
        
        # Adjust point value for NASDAQ
        if 'NASDAQ' in symbol.upper():
            point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
        
        # Calculate dynamic SL/TP using ATR
        atr = self.market_data.calculate_atr(symbol, 14)
        if atr is None:
            atr = 5.0  # Default fallback
        
        # Calculate pending order prices (closer distance based on ATR to avoid error 10015)
        # For XAU/USD, 1 pip = 0.1 points, so 10 pips = 1 point
        pip_value = point * 10  # Standard pip calculation
        # Use distance based on ATR (more conservative) to keep orders closer to market price
        breakout_distance = min(10 * pip_value, atr * 0.5)
        
        # Get current market price to ensure orders are placed at valid distances
        current_tick = mt5.symbol_info_tick(symbol)
        if current_tick is None:
            logging.error(f"Failed to get current tick data for {symbol}")
            return False
        
        current_ask = current_tick.ask
        current_bid = current_tick.bid
        
        # Calculate buy and sell prices ensuring they are at valid distances from current market
        # BUY_STOP orders must be placed above current ask price
        # SELL_STOP orders must be placed below current bid price
        min_buy_price = current_ask + (20 * pip_value)  # Minimum 20 pips above current ask
        max_buy_price = current_ask + (50 * pip_value)  # Maximum 50 pips above current ask
        
        min_sell_price = current_bid - (50 * pip_value)  # Maximum 50 pips below current bid
        max_sell_price = current_bid - (20 * pip_value)  # Minimum 20 pips below current bid
        
        # Calculate initial breakout prices
        raw_buy_price = session_high + breakout_distance
        raw_sell_price = session_low - breakout_distance
        
        # Adjust prices to be within valid ranges
        buy_price = max(min_buy_price, min(max_buy_price, raw_buy_price))
        sell_price = max(min_sell_price, min(max_sell_price, raw_sell_price))

        # Enforce a minimum gap between pending orders to avoid opposite triggers near market
        gap_points = buy_price - sell_price
        # Read min gap from config (pips), fallback to 60
        try:
            cfg = get_set_manager()
            set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
            if set_file:
                cfg.load_set_file(set_file)
            min_gap_pips = cfg.get('position_limits.min_pending_gap_pips', 60)
        except Exception:
            min_gap_pips = 60
        min_gap_points = max(0.5 * atr, float(min_gap_pips) * pip_value)
        if gap_points < min_gap_points:
            logging.info(f"Pending order gap too small ({gap_points:.5f} pts). Applying single-side placement to avoid opposite triggers.")
            # Choose the side farther from current price to reduce immediate whipsaw
            buy_dist = abs(buy_price - current_ask)
            sell_dist = abs(current_bid - sell_price)
            if buy_dist >= sell_dist:
                place_sell_order = False
                logging.info("Selecting BUY_STOP only due to gap constraint")
            else:
                place_buy_order = False
                logging.info("Selecting SELL_STOP only due to gap constraint")
        
        logging.info(f"Session breakout prices - BUY: {raw_buy_price:.5f}, SELL: {raw_sell_price:.5f}")
        logging.info(f"Adjusted prices - BUY: {buy_price:.5f}, SELL: {sell_price:.5f}")
        logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
        
        # Calculate SL/TP distances based on ATR
        sl_distance = 3.0 * atr  # Using default LOW RISK profile
        tp_distance = 6.0 * atr
        
        # Calculate SL/TP for buy order using adjusted price
        buy_sl = buy_price - sl_distance
        buy_tp = buy_price + tp_distance
        
        # Calculate SL/TP for sell order using adjusted price
        sell_sl = sell_price + sl_distance
        sell_tp = sell_price - tp_distance
        
        # Calculate lot size based on risk management
        buy_volume = config_manager.get('LOTS')  # Default to fixed lot size
        if config_manager.get('USE_RISK_MANAGEMENT'):
            try:
                # Calculate lot size based on 1% risk rule
                buy_sl_distance = abs(buy_price - buy_sl)
                account_info = mt5.account_info()
                balance = account_info.balance if account_info else 10000.0  # Default $10k account
                buy_volume = self.risk_calc.compute_lot_size(
                    balance=balance,
                    risk_pct=config_manager.get('RISK_PERCENT'),
                    sl_distance=buy_sl_distance,
                    symbol=symbol
                )
                logging.info(f"Calculated lot size for BUY order: {buy_volume:.2f}")
            except Exception as e:
                logging.warning(f"Failed to calculate dynamic lot size for BUY order, using default: {e}")
                buy_volume = config_manager.get('LOTS')
        
        # Place buy stop order only if allowed
        buy_result = None
        if place_buy_order:
            buy_result = self.mt5_gateway.place_pending_order(
                symbol=symbol,
                order_type="BUY_STOP",
                volume=buy_volume,
                price=buy_price,
                sl=buy_sl,
                tp=buy_tp,
                magic=config_manager.get('MAGIC_NUMBER'),
                expiration_hours=8  # Expire after 8 hours
            )
        else:
            logging.info("Skipping BUY_STOP order placement due to existing opposite position")
        
        # Calculate lot size for sell order
        sell_volume = config_manager.get('LOTS')  # Default to fixed lot size
        if config_manager.get('USE_RISK_MANAGEMENT'):
            try:
                # Calculate lot size based on 1% risk rule
                sell_sl_distance = abs(sell_price - sell_sl)
                account_info = mt5.account_info()
                balance = account_info.balance if account_info else 10000.0  # Default $10k account
                sell_volume = self.risk_calc.compute_lot_size(
                    balance=balance,
                    risk_pct=config_manager.get('RISK_PERCENT'),
                    sl_distance=sell_sl_distance,
                    symbol=symbol
                )
                logging.info(f"Calculated lot size for SELL order: {sell_volume:.2f}")
            except Exception as e:
                logging.warning(f"Failed to calculate dynamic lot size for SELL order, using default: {e}")
                sell_volume = config_manager.get('LOTS')
        
        # Place sell stop order only if allowed
        sell_result = None
        if place_sell_order:
            sell_result = self.mt5_gateway.place_pending_order(
                symbol=symbol,
                order_type="SELL_STOP",
                volume=sell_volume,
                price=sell_price,
                sl=sell_sl,
                tp=sell_tp,
                magic=config_manager.get('MAGIC_NUMBER'),
                expiration_hours=8  # Expire after 8 hours
            )
        else:
            logging.info("Skipping SELL_STOP order placement due to existing opposite position")
        
        # Track pending orders by session
        if buy_result or sell_result:
            self.session_pending_orders[session_name] = {
                "buy_order": buy_result.order if buy_result else None,
                "sell_order": sell_result.order if sell_result else None,
                "timestamp": datetime.now(timezone.utc)
            }
            buy_info = f"BUY @ {buy_price:.5f}" if place_buy_order else "BUY skipped"
            sell_info = f"SELL @ {sell_price:.5f}" if place_sell_order else "SELL skipped"
            logging.info(f"Placed session breakout orders for {session_name}: {buy_info}, {sell_info}")
            return True
        elif place_buy_order or place_sell_order:
            # We intended to place orders but failed
            logging.error(f"Failed to place session breakout orders for {session_name}")
            return False
        else:
            # No orders were intended to be placed
            logging.info(f"No session breakout orders placed for {session_name} due to existing positions")
            return True
    
    @handle_exception
    @performance_monitor
    def cancel_session_orders(self, session_name: str) -> bool:
        """
        Cancel pending orders for a specific session
        
        Args:
            session_name: Session name ("Asia", "London", "NewYork")
        """
        if session_name not in self.session_pending_orders:
            logging.debug(f"No pending orders found for session {session_name}")
            return True
        
        session_orders = self.session_pending_orders[session_name]
        
        # Cancel buy order if it exists
        if session_orders.get("buy_order"):
            try:
                # Prepare cancel request
                request = {
                    'action': mt5.TRADE_ACTION_REMOVE,
                    'order': int(session_orders["buy_order"]),
                    'type_time': mt5.ORDER_TIME_GTC,
                    'type_filling': mt5.ORDER_FILLING_FOK
                }
                
                result = mt5.order_send(request)
                if result and getattr(result, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
                    logging.info(f"Cancelled buy order {session_orders['buy_order']} for session {session_name}")
                else:
                    logging.warning(f"Failed to cancel buy order {session_orders['buy_order']} for session {session_name}")
            except Exception as e:
                logging.error(f"Error cancelling buy order for session {session_name}: {e}")
        
        # Cancel sell order if it exists
        if session_orders.get("sell_order"):
            try:
                # Prepare cancel request
                request = {
                    'action': mt5.TRADE_ACTION_REMOVE,
                    'order': int(session_orders["sell_order"]),
                    'type_time': mt5.ORDER_TIME_GTC,
                    'type_filling': mt5.ORDER_FILLING_FOK
                }
                
                result = mt5.order_send(request)
                if result and getattr(result, 'retcode', None) == mt5.TRADE_RETCODE_DONE:
                    logging.info(f"Cancelled sell order {session_orders['sell_order']} for session {session_name}")
                else:
                    logging.warning(f"Failed to cancel sell order {session_orders['sell_order']} for session {session_name}")
            except Exception as e:
                logging.error(f"Error cancelling sell order for session {session_name}: {e}")
        
        # Remove from tracking
        del self.session_pending_orders[session_name]
        logging.info(f"Cancelled all pending orders for session {session_name}")
        return True
    
    @handle_exception
    @performance_monitor
    def check_existing_session_orders(self, session_name: str) -> bool:
        """
        Check if there are already pending orders for a session
        
        Args:
            session_name: Session name ("Asia", "London", "NewYork")
            
        Returns:
            bool: True if orders exist, False otherwise
        """
        # Check our tracking dictionary
        if session_name in self.session_pending_orders:
            session_orders = self.session_pending_orders[session_name]
            # Check if orders are still active
            if session_orders.get("buy_order") or session_orders.get("sell_order"):
                # Verify with MT5 that orders still exist
                orders = mt5.orders_get()
                if orders:
                    for order in orders:
                        if (getattr(order, 'magic', 0) == config_manager.get('MAGIC_NUMBER') and 
                            (order.ticket == session_orders.get("buy_order") or 
                             order.ticket == session_orders.get("sell_order"))):
                            return True
                # If we get here, orders may have been filled or cancelled
                del self.session_pending_orders[session_name]
        
        return False


class QuantitativeIntegration:
    """Handles integration with quantitative engine for advanced analysis"""
    
    def __init__(self):
        self.quant_engine = QuantitativeEngine()
    
    def apply_quantitative_analysis(self, symbol: str, adx_value: float) -> Tuple[Optional[float], bool]:
        """
        Apply quantitative analysis to determine entry and position sizing
        
        Returns:
            tuple: (optimal_lots, should_trade)
        """
        try:
            # Get historical price data for quantitative analysis
            rates = mt5.copy_rates_from_pos(0, self.market_data.timeframe, 200)  # Get last 200 bars
            if rates is not None and len(rates) > 50:
                prices = rates['close']
                
                # Get DI values from market regime detector for quantitative analysis
                di_plus, di_minus = market_regime_detector.get_di_values(symbol, 14)
                
                # Calculate comprehensive entry score using quantitative formulas
                entry_result = self.quant_engine.calculate_entry_score(
                    prices=prices,
                    adx_value=adx_value,
                    di_plus=di_plus,
                    di_minus=di_minus
                )
                
                logging.info(f"Quantitative Entry Score: {entry_result['entry_score']:.3f}")
                logging.info(f"Recommendation: {entry_result['recommendation']}")
                
                # Use quantitative score instead of simple boolean conditions
                if entry_result['recommendation'] == 'HOLD' or entry_result['entry_score'] < 0.5:
                    logging.info(f"Quantitative analysis recommends HOLD (score: {entry_result['entry_score']:.3f}), skipping trade")
                    return None, False
                
                # Calculate optimal position size using quantitative formulas
                account_info = mt5.account_info()
                if account_info:
                    # Get historical returns if available for more sophisticated sizing
                    historical_returns = None  # Could be loaded from risk management system
                    
                    optimal_lots = self.quant_engine.calculate_optimal_position_size(
                        account_balance=account_info.balance,
                        entry_score=entry_result['entry_score'],
                        historical_returns=historical_returns
                    )
                    
                    logging.info(f"Quantitative position sizing: {optimal_lots:.3f} lots")
                    
                    return optimal_lots, True
            
            return None, True  # Default to traditional analysis if quantitative fails
            
        except ImportError:
            logging.warning("Quantitative engine not available, using traditional analysis")
            return None, True
        except Exception as e:
            logging.warning(f"Error in quantitative analysis: {e}, continuing with traditional analysis")
            return None, True


class DonchianStrategy:
    """
    Main strategy class following SOLID principles.
    This class orchestrates the strategy execution by delegating to specialized services.
    """
    
    def __init__(self):
        self.mt5_gateway = MT5Gateway()
        self.market_data = MarketDataService()
        self.risk_calc = RiskCalculator(self.market_data)
        self.session_manager = SessionManager(self.mt5_gateway, self.market_data, self.risk_calc)
        self.quant_integration = QuantitativeIntegration()
        
        # Load configuration
        self.config = StrategyConfig()
    
    def _in_trading_hours(self) -> bool:
        """Check if current time is within trading hours (GMT)"""
        # Obtener hora UTC correctamente
        current_hour_utc = datetime.now(timezone.utc).hour
        current_hour_local = datetime.now().hour
        
        in_hours = self.config.trading_hour_start <= current_hour_utc <= self.config.trading_hour_end
        
        logging.debug(f"México: {current_hour_local}:00 | UTC: {current_hour_utc}:00 | Trading: {self.config.trading_hour_start}-{self.config.trading_hour_end} UTC | Active: {in_hours}")
        
        return in_hours
    
    def _execute_trade(self, symbol: str, order_type: str, lots: float, sl_points: float, tp_points: float) -> bool:
        """Execute a trade with given parameters"""
        # Validate inputs
        if not InputValidator.validate_symbol(symbol):
            logging.error(f"Invalid symbol: {symbol}")
            return False
            
        if not InputValidator.validate_order_type(order_type):
            logging.error(f"Invalid order type: {order_type}")
            return False
            
        if not InputValidator.validate_volume(lots):
            logging.error(f"Invalid volume: {lots}")
            return False
            
        if sl_points <= 0 or tp_points <= 0:
            logging.error(f"Invalid SL/TP points: SL={sl_points}, TP={tp_points}")
            return False
        
        logging.info(f"Attempting to execute {order_type} trade for {symbol}")
        price = self.market_data.get_current_price(symbol, order_type)
        if price is None:
            logging.error("Failed to get current price")
            return False
        
        # Validate price
        if not InputValidator.validate_price(price):
            logging.error(f"Invalid price: {price}")
            return False
        
        # Get symbol info for point value
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            logging.error(f"Failed to get symbol info for {symbol}")
            return False
            
        point = symbol_info.point
        logging.debug(f"Symbol point value: {point}")
        
        if order_type == "BUY":
            sl = price - sl_points * point
            tp = price + tp_points * point
        else:  # SELL
            sl = price + sl_points * point
            tp = price - tp_points * point
        
        # Validate calculated prices
        if not InputValidator.validate_price(sl) or not InputValidator.validate_price(tp):
            logging.error(f"Invalid calculated SL/TP prices: SL={sl}, TP={tp}")
            return False
        
        if self.config.use_risk_management:
            account_info = mt5.account_info()
            if account_info is None:
                logging.error("Failed to get account info")
                return False
            from brokers.mt5_utils import estimate_lots_by_risk
            # Apply adaptive risk scaling based on current drawdown
            try:
                from risk.ftmo_manager import ftmo_manager
                risk_scale = ftmo_manager.get_risk_scale_factor()
                scaled_risk = self.config.risk_percent * risk_scale
                if risk_scale < 1.0:
                    logging.info(f"Risk scaled down: {self.config.risk_percent}% → {scaled_risk:.2f}% (factor: {risk_scale:.2f})")
            except Exception as e:
                logging.warning(f"Failed to get risk scale factor, using full risk: {e}")
                scaled_risk = self.config.risk_percent
            
            calculated_lots = estimate_lots_by_risk(
                symbol=symbol,
                entry_price=price,
                stop_price=sl,
                risk_pct=scaled_risk,
                mt5_module=mt5
            )
            logging.info(f"Risk: {scaled_risk:.2f}% = ${account_info.balance * scaled_risk / 100:.2f}, Lots: {calculated_lots}")
            lots = calculated_lots
        
        # Validate final volume
        if not InputValidator.validate_volume(lots):
            logging.error(f"Invalid final volume: {lots}")
            return False
        
        logging.info(f"Trade parameters - Price: {price}, SL: {sl}, TP: {tp}, Volume: {lots}")
        
        try:
            # Normalize volume to ensure it meets broker requirements
            original_lots = lots
            lots = normalize_volume(symbol, lots)
            if lots != original_lots:
                logging.info(f"Volume normalized from {original_lots} to {lots}")
            
            logging.info(f"Calling build_and_send_order with parameters: symbol={symbol}, side={order_type}, volume={lots}, sl={sl}, tp={tp}")
            result = build_and_send_order(
                symbol=symbol,
                side=order_type,
                volume=lots,
                sl=sl,
                tp=tp,
                magic=self.config.magic_number
            )
            
            if result:
                logging.info(f"{order_type} executed: Price={price:.5f} SL={sl:.5f} TP={tp:.5f}")
                logging.info(f"Order result: {result}")
                return True
            else:
                logging.error("Failed to execute trade - build_and_send_order returned None")
                return False
                
        except Exception as e:
            logging.error(f"Error executing trade: {sanitize_error_message(str(e))}", exc_info=True)
            return False
    
    def run_strategy(self, symbol="XAUUSD"):
        """Main strategy function with pending orders"""
        logging.info(f"Running strategy for symbol: {symbol}")
        
        # Check if we're in trading hours
        if not self._in_trading_hours():
            logging.info("Outside trading hours")
            return
        
        # Check for news events that might affect trading
        if news_filter.is_news_time():
            logging.info("News event detected, skipping trade execution")
            return
        
        # Check spread first
        spread = self.market_data.get_spread(symbol)
        if spread is None:
            logging.error("Failed to get current spread")
            return
        
        if spread > self.config.max_spread_points:
            logging.info(f"Spread too high: {spread:.2f} points > {self.config.max_spread_points} points, skipping")
            return
        
        # CHECK MARKET REGIME (ADX FILTER)
        # Get ADX filter settings from configuration
        try:
            cfg = get_set_manager()
            require_adx = cfg.get('strategy.require_adx_confirmation', False)
            adx_threshold = cfg.get('strategy.adx_threshold', 20)
            adx_period = cfg.get('strategy.adx_period', 14)
        except:
            require_adx = False
            adx_threshold = 20
            adx_period = 14
        
        # Apply ADX filter if enabled
        if require_adx:
            regime, adx_value, slope_value = market_regime_detector.detect_regime(
                symbol, 
                adx_period=adx_period,
                adx_threshold=adx_threshold
            )
            
            if regime == "RANGING":
                # The market_regime_detector already logs detailed ADX+DI info
                logging.info(f"Market is RANGING, skipping trade")
                logging.info("ADX filter prevents trading in ranging markets to avoid false breakouts")
                return
            elif regime == "UNKNOWN":
                logging.warning(f"Unable to determine market regime, skipping trade as precaution")
                return
            else:
                # market_regime_detector already logs detailed trending info
                logging.info(f"Market is TRENDING (ADX: {adx_value:.2f} > {adx_threshold}), proceeding with strategy")
        
        # QUANTITATIVE ANALYSIS INTEGRATION
        # Import and use quantitative engine for entry decisions
        try:
            from core.quant_engine import QuantitativeEngine
            quant_engine = QuantitativeEngine()
            
            # Get historical price data for quantitative analysis
            rates = mt5.copy_rates_from_pos(0, self.market_data.timeframe, 200)  # Get last 200 bars
            if rates is not None and len(rates) > 50:
                prices = rates['close']
                
                # Get DI values from market regime detector for quantitative analysis
                di_plus, di_minus = market_regime_detector.get_di_values(symbol, adx_period)
                
                # Calculate comprehensive entry score using quantitative formulas
                entry_result = quant_engine.calculate_entry_score(
                    prices=prices,
                    adx_value=adx_value,
                    di_plus=di_plus,
                    di_minus=di_minus
                )
                
                logging.info(f"Quantitative Entry Score: {entry_result['entry_score']:.3f}")
                logging.info(f"Recommendation: {entry_result['recommendation']}")
                
                # Use quantitative score instead of simple boolean conditions
                if entry_result['recommendation'] == 'HOLD' or entry_result['entry_score'] < 0.5:
                    logging.info(f"Quantitative analysis recommends HOLD (score: {entry_result['entry_score']:.3f}), skipping trade")
                    return
                
                # Calculate optimal position size using quantitative formulas
                account_info = mt5.account_info()
                if account_info:
                    # Get historical returns if available for more sophisticated sizing
                    historical_returns = None  # Could be loaded from risk management system
                    
                    optimal_lots = quant_engine.calculate_optimal_position_size(
                        account_balance=account_info.balance,
                        entry_score=entry_result['entry_score'],
                        historical_returns=historical_returns
                    )
                    
                    logging.info(f"Quantitative position sizing: {optimal_lots:.3f} lots")
                    
                    # Override the risk management lot calculation with quantitative size
                    # This will be used later in the strategy
                    import core.donchian_strategy as ds_module
                    ds_module.QUANT_OPTIMAL_LOTS = optimal_lots
                    
                    # Store entry score for potential future trade association
                    # The ticket will be associated when the trade is executed
                    current_entry_score = entry_result['entry_score']
                    logging.debug(f"Calculated entry score: {current_entry_score:.3f} for potential trade")
                    
                    # Store entry score globally for later association with ticket when trade executes
                    globals()['CURRENT_ENTRY_SCORE'] = current_entry_score
        
        except ImportError:
            logging.warning("Quantitative engine not available, using traditional analysis")
        except Exception as e:
            logging.warning(f"Error in quantitative analysis: {e}, continuing with traditional analysis")
            
        
        # Cancel expired pending orders
        cancel_expired_pending_orders(self.config.magic_number)
        
        # Initialize breakout variables
        bullish_breakout = False
        bearish_breakout = False
        
        # Get Donchian channels early for position management
        upper_channel, lower_channel = self.market_data.get_donchian_channels(symbol, self.config.donchian_period)
        if upper_channel is None or lower_channel is None:
            logging.error("Failed to calculate Donchian channels")
            return
        
        # Get current price early for breakout detection
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            logging.error("Failed to get current tick data")
            return
        
        # Use bid price for analysis (real market price) - FIXED FOR FTMO
        current_close = tick.bid
        
        # Calculate ATR for breakout detection
        atr = self.market_data.calculate_atr(symbol)
        if atr is None:
            logging.error("ATR failed")
            return
        
        # Check for breakout conditions early for position management
        # Enhanced breakout detection with configurable threshold
        if self.config.breakout_threshold > 0:
            # Use threshold for stronger breakout confirmation
            bullish_breakout = current_close > (upper_channel + (self.config.breakout_threshold * atr))
            bearish_breakout = current_close < (lower_channel - (self.config.breakout_threshold * atr))
        else:
            # Standard breakout detection
            bullish_breakout = current_close > upper_channel
            bearish_breakout = current_close < lower_channel
        
        # Check existing positions and limits
        positions = mt5.positions_get(symbol=symbol)
        
        # Get max positions from config, default to 2 if not specified
        try:
            max_positions = cfg.get('position_limits.max_positions', 2)
        except:
            max_positions = 2
        
        if positions:
            # Count positions by direction
            buy_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_BUY)
            sell_positions = sum(1 for p in positions if p.type == mt5.POSITION_TYPE_SELL)
            total_positions = len(positions)
            
            # Block if max total positions reached
            if total_positions >= max_positions:
                logging.info(f"Max positions reached ({total_positions}/{max_positions}), skipping")
                return
            
            # Block opposite direction trades
            if bullish_breakout and sell_positions > 0:
                logging.info(f"Opposite SELL position exists, cannot open BUY")
                return
            if bearish_breakout and buy_positions > 0:
                logging.info(f"Opposite BUY position exists, cannot open SELL")
                return
            
            # Allow same-direction trades if under max_positions
            if bullish_breakout and buy_positions >= max_positions:
                logging.info(f"Max BUY positions reached ({buy_positions}/{max_positions})")
                return
            if bearish_breakout and sell_positions >= max_positions:
                logging.info(f"Max SELL positions reached ({sell_positions}/{max_positions})")
                return
            
            logging.info(f"Positions: {buy_positions} BUY, {sell_positions} SELL. Allowing same-direction trade")
        
        # SESSION BREAKOUT LOGIC
        # Get current session
        current_session = self.session_manager.get_current_session()
        
        # Check if we're at the start of a new session
        if current_session and current_session != self.session_manager.last_session:
            logging.info(f"New session started: {current_session}")
            
            # Cancel previous session orders if they exist
            if self.session_manager.last_session and self.session_manager.last_session in self.session_manager.session_pending_orders:
                self.session_manager.cancel_session_orders(self.session_manager.last_session)
            
            # Check if we already have session orders for this session
            if not self.session_manager.check_existing_session_orders(current_session):
                # Place new session breakout orders
                self.session_manager.place_session_breakout_orders(symbol, current_session)
            
            # Update last session
            self.session_manager.last_session = current_session
            # Continue with Donchian strategy even after placing session orders
        
        # Continue with existing Donchian strategy logic if no session change
        # Check for existing pending orders
        orders = mt5.orders_get(symbol=symbol)
        pending_orders = [order for order in orders if getattr(order, 'magic', 0) == self.config.magic_number] if orders else []
        if pending_orders:
            logging.info(f"Pending order already exists for {symbol}, skipping")
            return
        
        # Calculate momentum values
        current_momentum = self.market_data.calculate_momentum(symbol, self.config.momentum_period)
        historical_momentum = self.market_data.calculate_momentum(symbol, self.config.sample_period)
        
        logging.info(f"Momentum values - Current: {current_momentum}, Historical: {historical_momentum}")
        
        # Get volume stats for event detection
        current_volume, avg_volume = self.market_data.get_volume_stats(symbol)
        volume_spike = current_volume and avg_volume and current_volume > avg_volume * self.config.event_volume_spike_factor
        
        # Use bid price for analysis (real market price) - FIXED FOR FTMO
        logging.info(f"Current close price (bid): {current_close}")
        logging.info(f"Upper channel: {upper_channel}, Lower channel: {lower_channel}")
        
        # Calculate ATR for dynamic SL/TP
        if atr is None:
            logging.error("ATR failed")
            return
        
        # Momentum filter: current > historical * 0.3 (less restrictive)
        momentum_filter = current_momentum > (historical_momentum * 0.3)
        
        # Add volume confirmation
        volume_spike, vol_ratio = self.market_data.get_volume_stats(symbol)
        
        # Detect engulfing patterns
        bullish_engulfing, bearish_engulfing = self.market_data.detect_engulfing(symbol)
        
        # Volume confirmation made optional for more signals during testing
        if bullish_breakout and momentum_filter:  # Removed engulfing confirmation for more signals
            logging.info(f"STRONG BUY signal: Volume {vol_ratio:.2f}x average")
            
            # Calculate pending order price (0.5 * ATR above upper channel)
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logging.error(f"Failed to get symbol info for {symbol}")
                return
            point = symbol_info.point
            
            # Adjust point value for NASDAQ
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            
            # Calculate breakout distance
            breakout_distance = 0.5 * atr
            raw_pending_price = upper_channel + breakout_distance
            
            # Get current market price to ensure orders are placed at valid distances
            current_tick = mt5.symbol_info_tick(symbol)
            if current_tick is None:
                logging.error(f"Failed to get current tick data for {symbol}")
                return
            
            current_ask = current_tick.ask
            current_bid = current_tick.bid
            
            # For BUY_STOP orders, they must be placed above current ask price
            # But not too far above to avoid error 10015
            pip_value = point * 10  # Standard pip calculation
            min_buy_price = current_ask + (5 * pip_value)   # Minimum 5 pips above current ask
            max_buy_price = current_ask + (50 * pip_value)  # Maximum 50 pips above current ask
            
            # Adjust price to be within valid range
            pending_price = max(min_buy_price, min(max_buy_price, raw_pending_price))
            
            logging.info(f"Raw BUY_STOP price: {raw_pending_price:.5f}, Adjusted price: {pending_price:.5f}")
            logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
            
            # Calculate dynamic SL/TP based on ATR and risk profile using adjusted price
            sl_price, tp_price = self.risk_calc.calculate_dynamic_stops(symbol, pending_price, "BUY", atr)
            
            # Calculate lot size based on risk management
            buy_volume = self.config.lots  # Default to fixed lot size
            if self.config.use_risk_management:
                try:
                    # Calculate lot size based on 1% risk rule
                    buy_sl_distance = abs(pending_price - sl_price)
                    account_info = mt5.account_info()
                    balance = account_info.balance if account_info else 10000.0  # Default $10k account
                    buy_volume = self.risk_calc.compute_lot_size(
                        balance=balance,
                        risk_pct=self.config.risk_percent,
                        sl_distance=buy_sl_distance,
                        symbol=symbol
                    )
                    logging.info(f"Calculated lot size for BUY pending order: {buy_volume:.2f}")
                except Exception as e:
                    logging.warning(f"Failed to calculate dynamic lot size for BUY pending order, using default: {e}")
                    buy_volume = self.config.lots
            
            # Place pending order
            result = place_pending_order(
                symbol=symbol,
                order_type="BUY_STOP",
                volume=buy_volume,
                price=pending_price,
                sl=sl_price,
                tp=tp_price,
                magic=self.config.magic_number
            )
            
            if result:
                logging.info(f"BUY_STOP order placed: Price={pending_price:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}")
                if hasattr(result, 'order') and 'CURRENT_ENTRY_SCORE' in globals():
                    TRADE_ENTRY_SCORES[result.order] = globals()['CURRENT_ENTRY_SCORE']
                    logging.debug(f"Entry score {globals()['CURRENT_ENTRY_SCORE']:.3f} → ticket {result.order}")
                # Store entry score for this ticket if we can get it from the result
                if hasattr(result, 'order'):
                    ticket = result.order
                    # Use the globally stored entry score
                    if 'CURRENT_ENTRY_SCORE' in globals() and globals()['CURRENT_ENTRY_SCORE'] is not None:
                        TRADE_ENTRY_SCORES[ticket] = globals()['CURRENT_ENTRY_SCORE']
                        logging.debug(f"Associated entry score {globals()['CURRENT_ENTRY_SCORE']:.3f} with ticket {ticket}")
                    else:
                        logging.warning(f"No current entry score available for ticket {ticket}")
            else:
                logging.error("Failed to place BUY_STOP order")
                
        elif bearish_breakout and momentum_filter:  # Removed engulfing confirmation for more signals
            logging.info(f"STRONG SELL signal: Volume {vol_ratio:.2f}x average")
            
            # Calculate pending order price (0.5 * ATR below lower channel)
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                logging.error(f"Failed to get symbol info for {symbol}")
                return
            point = symbol_info.point
            
            # Adjust point value for NASDAQ
            if 'NASDAQ' in symbol.upper():
                point = 1.0  # NASDAQ typically uses 1.0 point increments for indices
            
            # Calculate breakout distance
            breakout_distance = 0.5 * atr
            raw_pending_price = lower_channel - breakout_distance
            
            # Get current market price to ensure orders are placed at valid distances
            current_tick = mt5.symbol_info_tick(symbol)
            if current_tick is None:
                logging.error(f"Failed to get current tick data for {symbol}")
                return
            
            current_ask = current_tick.ask
            current_bid = current_tick.bid
            
            # For SELL_STOP orders, they must be placed below current bid price
            # But not too far below to avoid error 10015
            pip_value = point * 10  # Standard pip calculation
            min_sell_price = current_bid - (50 * pip_value)  # Maximum 50 pips below current bid
            max_sell_price = current_bid - (5 * pip_value)   # Minimum 5 pips below current bid
            
            # Adjust price to be within valid range
            pending_price = max(min_sell_price, min(max_sell_price, raw_pending_price))
            
            logging.info(f"Raw SELL_STOP price: {raw_pending_price:.5f}, Adjusted price: {pending_price:.5f}")
            logging.info(f"Current market - BID: {current_bid:.5f}, ASK: {current_ask:.5f}")
            
            # Calculate dynamic SL/TP based on ATR and risk profile using adjusted price
            sl_price, tp_price = self.risk_calc.calculate_dynamic_stops(symbol, pending_price, "SELL", atr)
            
            # Calculate lot size based on risk management
            sell_volume = self.config.lots  # Default to fixed lot size
            if self.config.use_risk_management:
                try:
                    # Calculate lot size based on 1% risk rule
                    sell_sl_distance = abs(pending_price - sl_price)
                    account_info = mt5.account_info()
                    balance = account_info.balance if account_info else 10000.0  # Default $10k account
                    sell_volume = self.risk_calc.compute_lot_size(
                        balance=balance,
                        risk_pct=self.config.risk_percent,
                        sl_distance=sell_sl_distance,
                        symbol=symbol
                    )
                    logging.info(f"Calculated lot size for SELL pending order: {sell_volume:.2f}")
                except Exception as e:
                    logging.warning(f"Failed to calculate dynamic lot size for SELL pending order, using default: {e}")
                    sell_volume = self.config.lots
            
            # Place pending order
            result = place_pending_order(
                symbol=symbol,
                order_type="SELL_STOP",
                volume=sell_volume,
                price=pending_price,
                sl=sl_price,
                tp=tp_price,
                magic=self.config.magic_number
            )
            
            if result:
                logging.info(f"SELL_STOP order placed: Price={pending_price:.5f}, SL={sl_price:.5f}, TP={tp_price:.5f}")
                if hasattr(result, 'order') and 'CURRENT_ENTRY_SCORE' in globals():
                    TRADE_ENTRY_SCORES[result.order] = globals()['CURRENT_ENTRY_SCORE']
                    logging.debug(f"Entry score {globals()['CURRENT_ENTRY_SCORE']:.3f} → ticket {result.order}")
                # Store entry score for this ticket if we can get it from the result
                if hasattr(result, 'order'):
                    ticket = result.order
                    # Use the globally stored entry score
                    if 'CURRENT_ENTRY_SCORE' in globals() and globals()['CURRENT_ENTRY_SCORE'] is not None:
                        TRADE_ENTRY_SCORES[ticket] = globals()['CURRENT_ENTRY_SCORE']
                        logging.debug(f"Associated entry score {globals()['CURRENT_ENTRY_SCORE']:.3f} with ticket {ticket}")
                    else:
                        logging.warning(f"No current entry score available for ticket {ticket}")
            else:
                logging.error("Failed to place SELL_STOP order")


@handle_exception
@performance_monitor
def initialize_mt5():
    """Initialize MT5 connection"""
    # Add more detailed initialization info
    logging.info("Attempting to initialize MT5...")
    
    # Get credentials from secure credential manager
    login = credential_manager.get_credential('MT5_LOGIN')
    password = credential_manager.get_credential('MT5_PASSWORD')
    server = credential_manager.get_credential('MT5_SERVER')
    
    # Initialize with credentials if available
    if login and password and server:
        try:
            login_int = int(login)
            logging.info(f"Initializing MT5 with credentials for account {login_int} on server {server}")
            if not mt5.initialize(login=login_int, password=password, server=server):
                logging.error("Failed to initialize MT5 with credentials")
                error = mt5.last_error()
                logging.error(f"MT5 initialization error: {error}")
                return False
        except ValueError as e:
            logging.error(f"Invalid login format: {login}. Error: {sanitize_error_message(str(e))}")
            return False
    else:
        # Initialize without credentials
        logging.info("Initializing MT5 without credentials")
        if not mt5.initialize():
            logging.error("Failed to initialize MT5")
            error = mt5.last_error()
            logging.error(f"MT5 initialization error: {error}")
            return False
    
    logging.info("MT5 initialized successfully")
    return True


@handle_exception
@performance_monitor
def main():
    """Main function to run the strategy"""
    logging.info("Starting Donchian Breakout Strategy")
    
    # Load configuration set file if specified
    set_file = os.getenv('ROBOQUANT_SET_FILE', 'default.json')
    if set_file:
        try:
            cfg = get_set_manager()
            cfg.load_set_file(set_file)
            logging.info(f"Loaded configuration set: {set_file}")
        except Exception as e:
            logging.warning(f"Failed to load configuration set {set_file}: {e}. Using default values.")
    
    # Initialize MT5
    if not initialize_mt5():
        return
    
    # Select symbol
    symbol = os.getenv('TRADING_SYMBOL', 'XAUUSD')
    logging.info(f"Selecting symbol: {symbol}")
    if not mt5.symbol_select(symbol, True):
        logging.error(f"Failed to select symbol {symbol}")
        mt5.shutdown()
        return
    
    # Initialize FTMO safety module
    from risk.safety import FTMOSafety
    safety = FTMOSafety(mt5_module=mt5)
    ds = DonchianStrategy()
    
    logging.info("Donchian Breakout Strategy started")
    logging.info(f"Parameters: Donchian Period={config_manager.get('DONCHIAN_PERIOD')}, Momentum Period={config_manager.get('MOMENTUM_PERIOD')}")
    
    try:
        # Run once immediately for testing
        logging.info("Running strategy immediately for testing...")
        
        # Check safety before running strategy
        ok, reason = safety.check_all(new_symbol=symbol)
        if not ok:
            logging.error(f"Safety check failed: {reason}")
            logging.info("Skipping strategy execution due to safety check failure")
        else:
            logging.info("Safety checks passed")
            # Show FTMO dashboard
            try:
                from risk.ftmo_manager import ftmo_manager
                logging.info(ftmo_manager.get_ftmo_dashboard())
            except Exception as e:
                logging.debug(f"Failed to show FTMO dashboard: {e}")
            ds.run_strategy(symbol)
        
        # Import the monitoring function
        from brokers.mt5_utils import monitor_and_update_stops
        
        # Then continue with the loop
        while True:
            # Run strategy
            # Check safety before running strategy
            ok, reason = safety.check_all(new_symbol=symbol)
            if not ok:
                logging.error(f"Safety check failed: {reason}")
                logging.info("Skipping strategy execution due to safety check failure")
            else:
                logging.info("Safety checks passed")
                # Show FTMO dashboard every 10 iterations
                import random
                if random.randint(1, 10) == 1:  # Roughly every 50 minutes
                    try:
                        from risk.ftmo_manager import ftmo_manager
                        logging.info(ftmo_manager.get_ftmo_dashboard())
                    except Exception as e:
                        logging.debug(f"Failed to show FTMO dashboard: {e}")
                ds.run_strategy(symbol)
            
            # Monitor positions and add SL/TP if missing
            try:
                monitor_and_update_stops()
            except Exception as e:
                logging.error(f"Error monitoring positions: {e}", exc_info=True)
            
            # Update trailing stops
            try:
                update_trailing_stops()
            except Exception as e:
                logging.error(f"Error updating trailing stops: {e}", exc_info=True)
            
            # UPDATED: Sleep interval adjusted for M5 timeframe (300 seconds = 5 minutes)
            logging.debug("Waiting 300 seconds (5 minutes) before next check...")
            time.sleep(300)
            
    except KeyboardInterrupt:
        logging.info("Strategy stopped by user")
    except Exception as e:
        logging.error(f"Error in main loop: {e}", exc_info=True)
    finally:
        mt5.shutdown()
        logging.info("MT5 connection closed")


if __name__ == "__main__":
    main()