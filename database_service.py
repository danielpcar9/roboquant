"""
Database Service Layer - Supabase integration for trades and metrics persistence
Provides all data persistence operations with proper error handling and logging
"""

import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

try:
    from supabase import create_client, Client
except ImportError:
    Client = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Trade data model"""
    timestamp_open: datetime
    symbol: str
    side: str  # 'BUY' or 'SELL'
    volume: float
    entry_price: float
    sl: float
    tp: float
    ticket: Optional[int] = None
    timestamp_close: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    duration_minutes: Optional[int] = None
    reason_closed: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Performance metrics data model"""
    period: str
    total_trades: int
    win_rate: float
    profit_factor: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float


class DatabaseService:
    """Service for managing all database operations"""

    _instance: Optional['DatabaseService'] = None
    _initialized: bool = False

    def __new__(cls) -> 'DatabaseService':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.client: Optional[Client] = None
            self._initialize_client()
            DatabaseService._initialized = True

    def _initialize_client(self) -> bool:
        """Initialize Supabase client"""
        try:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_ANON_KEY')

            if not url or not key:
                logger.warning("Supabase credentials not configured, database service disabled")
                return False

            self.client = create_client(url, key)
            logger.info("Supabase client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {str(e)}")
            return False

    def _is_ready(self) -> bool:
        """Check if database service is ready"""
        if not self.client:
            logger.warning("Database service not initialized")
            return False
        return True

    def save_trade(self, trade: Trade) -> bool:
        """
        Save a trade to the database

        Args:
            trade: Trade object to save

        Returns:
            bool: True if successful
        """
        if not self._is_ready():
            return False

        try:
            trade_data = {
                'timestamp_open': trade.timestamp_open.isoformat(),
                'timestamp_close': trade.timestamp_close.isoformat() if trade.timestamp_close else None,
                'ticket': trade.ticket,
                'symbol': trade.symbol,
                'side': trade.side,
                'volume': trade.volume,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'sl': trade.sl,
                'tp': trade.tp,
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'duration_minutes': trade.duration_minutes,
                'reason_closed': trade.reason_closed,
            }

            result = self.client.table('trades').insert(trade_data).execute()  # type: ignore
            logger.info(f"Trade saved successfully: {trade.symbol} {trade.side} @ {trade.entry_price}")
            return True

        except Exception as e:
            logger.error(f"Failed to save trade: {str(e)}")
            return False

    def get_trades(
        self,
        symbol: Optional[str] = None,
        days: int = 30,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve trades from the database

        Args:
            symbol: Optional symbol filter
            days: Number of days to retrieve
            limit: Maximum number of trades to return

        Returns:
            List of trade records
        """
        if not self._is_ready():
            return []

        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()

            query = self.client.table('trades').select('*').gte('timestamp_open', cutoff_date).limit(limit)  # type: ignore

            if symbol:
                query = query.eq('symbol', symbol)  # type: ignore

            result = query.execute()  # type: ignore
            logger.debug(f"Retrieved {len(result.data)} trades from database")
            return result.data

        except Exception as e:
            logger.error(f"Failed to retrieve trades: {str(e)}")
            return []

    def update_trade_close(
        self,
        ticket: int,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason_closed: str
    ) -> bool:
        """
        Update a trade with close information

        Args:
            ticket: Order ticket/ID
            exit_price: Price at which trade closed
            pnl: Profit/Loss in account currency
            pnl_pct: Profit/Loss percentage
            reason_closed: Reason for trade closure

        Returns:
            bool: True if successful
        """
        if not self._is_ready():
            return False

        try:
            update_data = {
                'timestamp_close': datetime.now().isoformat(),
                'exit_price': exit_price,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'reason_closed': reason_closed,
                'duration_minutes': None,  # Will be calculated by DB trigger if needed
            }

            self.client.table('trades').update(update_data).eq('ticket', ticket).execute()  # type: ignore
            logger.info(f"Trade {ticket} closed: P&L={pnl:.2f} ({pnl_pct:.2f}%)")
            return True

        except Exception as e:
            logger.error(f"Failed to update trade close: {str(e)}")
            return False

    def save_performance_metrics(self, metrics: PerformanceMetrics) -> bool:
        """
        Save performance metrics to the database

        Args:
            metrics: PerformanceMetrics object

        Returns:
            bool: True if successful
        """
        if not self._is_ready():
            return False

        try:
            metrics_data = {
                'calculated_at': datetime.now().isoformat(),
                'period': metrics.period,
                'total_trades': metrics.total_trades,
                'win_rate': metrics.win_rate,
                'profit_factor': metrics.profit_factor,
                'sharpe_ratio': metrics.sharpe_ratio,
                'max_drawdown': metrics.max_drawdown,
                'total_pnl': metrics.total_pnl,
            }

            self.client.table('performance_metrics').insert(metrics_data).execute()  # type: ignore
            logger.info(f"Performance metrics saved for period: {metrics.period}")
            return True

        except Exception as e:
            logger.error(f"Failed to save performance metrics: {str(e)}")
            return False

    def get_performance_metrics(self, period: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve performance metrics

        Args:
            period: Period label (e.g., 'daily', 'weekly', 'monthly')
            limit: Maximum number of records to return

        Returns:
            List of metrics records
        """
        if not self._is_ready():
            return []

        try:
            result = (
                self.client.table('performance_metrics')
                .select('*')
                .eq('period', period)
                .order('calculated_at', desc=True)
                .limit(limit)
                .execute()
            )  # type: ignore
            logger.debug(f"Retrieved {len(result.data)} performance metrics for period: {period}")
            return result.data

        except Exception as e:
            logger.error(f"Failed to retrieve performance metrics: {str(e)}")
            return []

    def save_strategy_config(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Save or update strategy configuration

        Args:
            name: Configuration name
            config: Configuration parameters as dictionary

        Returns:
            bool: True if successful
        """
        if not self._is_ready():
            return False

        try:
            config_data = {
                'name': name,
                'parameters': config,
                'updated_at': datetime.now().isoformat(),
            }

            result = self.client.table('strategy_configs').select('*').eq('name', name).execute()  # type: ignore

            if result.data:
                self.client.table('strategy_configs').update(config_data).eq('name', name).execute()  # type: ignore
            else:
                self.client.table('strategy_configs').insert(config_data).execute()  # type: ignore

            logger.info(f"Strategy config saved: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save strategy config: {str(e)}")
            return False

    def get_strategy_config(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve strategy configuration

        Args:
            name: Configuration name

        Returns:
            Configuration parameters or None
        """
        if not self._is_ready():
            return None

        try:
            result = self.client.table('strategy_configs').select('*').eq('name', name).maybeSingle().execute()  # type: ignore

            if result.data:
                logger.debug(f"Strategy config retrieved: {name}")
                return result.data.get('parameters')

            logger.warning(f"Strategy config not found: {name}")
            return None

        except Exception as e:
            logger.error(f"Failed to retrieve strategy config: {str(e)}")
            return None


def get_database_service() -> DatabaseService:
    """Get the singleton DatabaseService instance"""
    return DatabaseService()
