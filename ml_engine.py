# ml_engine.py
"""
Machine Learning engine for RoboQuant trading system with feature engineering
and XGBoost-based trading model.
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

# Try to import XGBoost
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    xgb = None
    XGBOOST_AVAILABLE = False
    logging.warning("XGBoost not available. ML features will be disabled.")

# Configure logging for ML engine
ml_logger = logging.getLogger('ml_engine')
ml_logger.setLevel(logging.INFO)
if not ml_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - ML_ENGINE - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    ml_logger.addHandler(handler)


class FeatureEngineer:
    """Feature engineering for trading signals."""
    
    def __init__(self):
        """Initialize the feature engineer."""
        pass
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index (RSI).
        
        Args:
            prices: Price series
            period: RSI period
            
        Returns:
            RSI series
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, prices: pd.Series, 
                      fast_period: int = 12, 
                      slow_period: int = 26, 
                      signal_period: int = 9) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate MACD indicator.
        
        Args:
            prices: Price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period
            
        Returns:
            Tuple of (MACD line, Signal line)
        """
        ema_fast = prices.ewm(span=fast_period).mean()
        ema_slow = prices.ewm(span=slow_period).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period).mean()
        return macd_line, signal_line
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range (ATR).
        
        Args:
            df: DataFrame with 'high', 'low', 'close' columns
            period: ATR period
            
        Returns:
            ATR series
        """
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        atr = pd.Series(true_range).rolling(period).mean()
        return atr
    
    def calculate_donchian(self, df: pd.DataFrame, period: int = 50) -> Tuple[pd.Series, pd.Series]:
        """
        Calculate Donchian channels.
        
        Args:
            df: DataFrame with 'high', 'low' columns
            period: Donchian period
            
        Returns:
            Tuple of (upper channel, lower channel)
        """
        upper_channel = df['high'].rolling(period).max()
        lower_channel = df['low'].rolling(period).min()
        return upper_channel, lower_channel
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Engineer features for ML model.
        
        Args:
            df: Input DataFrame with price data
            
        Returns:
            DataFrame with engineered features
        """
        if df.empty:
            return df
            
        # Make a copy to avoid modifying the original
        features_df = df.copy()
        
        # Price-based features
        features_df['returns'] = features_df['close'].pct_change()
        features_df['log_returns'] = np.log(features_df['close'] / features_df['close'].shift(1))
        
        # Technical indicators
        features_df['rsi'] = self.calculate_rsi(features_df['close'])
        macd_line, signal_line = self.calculate_macd(features_df['close'])
        features_df['macd'] = macd_line
        features_df['macd_signal'] = signal_line
        features_df['macd_histogram'] = macd_line - signal_line
        
        # ATR
        features_df['atr'] = self.calculate_atr(features_df)
        
        # Donchian channels
        upper_dc, lower_dc = self.calculate_donchian(features_df)
        features_df['donchian_upper'] = upper_dc
        features_df['donchian_lower'] = lower_dc
        features_df['donchian_position'] = (features_df['close'] - lower_dc) / (upper_dc - lower_dc)
        
        # Moving averages
        features_df['sma_20'] = features_df['close'].rolling(20).mean()
        features_df['sma_50'] = features_df['close'].rolling(50).mean()
        features_df['ema_20'] = features_df['close'].ewm(span=20).mean()
        
        # Bollinger Bands
        features_df['bb_middle'] = features_df['close'].rolling(20).mean()
        bb_std = features_df['close'].rolling(20).std()
        features_df['bb_upper'] = features_df['bb_middle'] + (bb_std * 2)
        features_df['bb_lower'] = features_df['bb_middle'] - (bb_std * 2)
        features_df['bb_position'] = (features_df['close'] - features_df['bb_lower']) / (features_df['bb_upper'] - features_df['bb_lower'])
        
        # Volatility features
        features_df['volatility_20'] = features_df['returns'].rolling(20).std()
        features_df['volatility_50'] = features_df['returns'].rolling(50).std()
        
        # Volume features (if available)
        if 'volume' in features_df.columns:
            features_df['volume_sma'] = features_df['volume'].rolling(20).mean()
            features_df['volume_ratio'] = features_df['volume'] / features_df['volume_sma']
        
        # Lag features
        for lag in [1, 2, 3, 5]:
            features_df[f'returns_lag_{lag}'] = features_df['returns'].shift(lag)
            features_df[f'rsi_lag_{lag}'] = features_df['rsi'].shift(lag)
        
        # Difference features
        features_df['price_change'] = features_df['close'] - features_df['close'].shift(1)
        features_df['price_change_pct'] = features_df['price_change'] / features_df['close'].shift(1)
        
        # Clean up any NaN values
        features_df = features_df.dropna()
        
        ml_logger.info(f"Engineered {len(features_df.columns)} features from {len(df.columns)} input columns")
        return features_df


class TradingMLModel:
    """XGBoost-based trading model."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the trading ML model.
        
        Args:
            model_path: Path to load pre-trained model (optional)
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost is not available. Please install xgboost package.")
            
        self.model = None
        self.feature_engineer = FeatureEngineer()
        self.is_trained = False
        
        if model_path:
            self.load_model(model_path)
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare features for model training/prediction.
        
        Args:
            df: Input DataFrame with price data
            
        Returns:
            DataFrame with prepared features
        """
        # Engineer features
        features_df = self.feature_engineer.engineer_features(df)
        
        # Select only numeric columns
        numeric_columns = features_df.select_dtypes(include=[np.number]).columns
        features_df = features_df[numeric_columns]
        
        # Remove any remaining non-feature columns that shouldn't be used for prediction
        exclude_columns = ['open', 'high', 'low', 'close', 'tick_volume', 'volume']
        feature_columns = [col for col in features_df.columns if col not in exclude_columns]
        
        return features_df[feature_columns]
    
    def prepare_targets(self, df: pd.DataFrame, lookahead: int = 1) -> pd.Series:
        """
        Prepare target variables for model training.
        
        Args:
            df: Input DataFrame with price data
            lookahead: Number of periods to look ahead for target calculation
            
        Returns:
            Series with target values (1 for buy signal, -1 for sell signal, 0 for hold)
        """
        # Calculate future returns
        future_returns = df['close'].shift(-lookahead) / df['close'] - 1
        
        # Create signals based on future returns
        # Buy signal: future return > 0.1%
        # Sell signal: future return < -0.1%
        # Hold signal: otherwise
        signals = pd.Series(0, index=df.index)
        signals[future_returns > 0.001] = 1   # Buy
        signals[future_returns < -0.001] = -1 # Sell
        
        return signals
    
    def train(self, df: pd.DataFrame, 
              test_size: float = 0.2,
              random_state: int = 42) -> Dict[str, Any]:
        """
        Train the ML model.
        
        Args:
            df: Training data DataFrame
            test_size: Proportion of data to use for testing
            random_state: Random state for reproducibility
            
        Returns:
            Dictionary with training results
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost is not available. Please install xgboost package.")
            
        # Prepare features and targets
        features_df = self.prepare_features(df)
        targets = self.prepare_targets(df)
        
        # Align indices
        common_index = features_df.index.intersection(targets.index)
        features_df = features_df.loc[common_index]
        targets = targets.loc[common_index]
        
        # Split data
        split_idx = int(len(features_df) * (1 - test_size))
        X_train = features_df.iloc[:split_idx]
        X_test = features_df.iloc[split_idx:]
        y_train = targets.iloc[:split_idx]
        y_test = targets.iloc[split_idx:]
        
        # Handle class imbalance
        scale_pos_weight = float(len(y_train[y_train == -1])) / len(y_train[y_train == 1]) if len(y_train[y_train == 1]) > 0 else 1
        
        # Create XGBoost classifier
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=random_state,
            objective='multi:softprob',
            num_class=3  # Buy, Sell, Hold
        )
        
        # Train model
        ml_logger.info(f"Training model with {len(X_train)} samples and {len(X_train.columns)} features")
        self.model.fit(X_train, y_train)
        
        # Evaluate model
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)
        
        # Get feature importance
        feature_importance = pd.DataFrame({
            'feature': X_train.columns,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        self.is_trained = True
        
        results = {
            'train_score': train_score,
            'test_score': test_score,
            'feature_importance': feature_importance,
            'n_features': len(X_train.columns),
            'n_samples_train': len(X_train),
            'n_samples_test': len(X_test)
        }
        
        ml_logger.info(f"Model training completed. Train accuracy: {train_score:.4f}, Test accuracy: {test_score:.4f}")
        return results
    
    def predict(self, df: pd.DataFrame) -> pd.Series:
        """
        Make predictions using the trained model.
        
        Args:
            df: Input DataFrame with price data
            
        Returns:
            Series with predictions (-1 for sell, 0 for hold, 1 for buy)
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Please train the model first.")
            
        # Prepare features
        features_df = self.prepare_features(df)
        
        # Make predictions
        predictions = self.model.predict(features_df)
        
        # Return as pandas Series with same index
        return pd.Series(predictions, index=features_df.index)
    
    def predict_proba(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Get prediction probabilities.
        
        Args:
            df: Input DataFrame with price data
            
        Returns:
            DataFrame with prediction probabilities for each class
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Please train the model first.")
            
        # Prepare features
        features_df = self.prepare_features(df)
        
        # Get probabilities
        probabilities = self.model.predict_proba(features_df)
        
        # Return as DataFrame with class labels
        return pd.DataFrame(probabilities, 
                          index=features_df.index,
                          columns=['sell_prob', 'hold_prob', 'buy_prob'])
    
    def save_model(self, path: str) -> None:
        """
        Save the trained model to disk.
        
        Args:
            path: Path to save the model
        """
        if not self.is_trained or self.model is None:
            raise RuntimeError("Model is not trained. Please train the model first.")
            
        self.model.save_model(path)
        ml_logger.info(f"Model saved to {path}")
    
    def load_model(self, path: str) -> None:
        """
        Load a pre-trained model from disk.
        
        Args:
            path: Path to load the model from
        """
        if not XGBOOST_AVAILABLE:
            raise RuntimeError("XGBoost is not available. Please install xgboost package.")
            
        self.model = xgb.XGBClassifier()
        self.model.load_model(path)
        self.is_trained = True
        ml_logger.info(f"Model loaded from {path}")


class MLTradingSystem:
    """Integration of ML model with technical trading signals."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize the ML trading system.
        
        Args:
            model_path: Path to load pre-trained model (optional)
        """
        self.ml_model = TradingMLModel(model_path) if XGBOOST_AVAILABLE else None
        self.feature_engineer = FeatureEngineer()
        self.paper_trading_mode = True  # Start in paper trading mode
        
    def generate_hybrid_signals(self, df: pd.DataFrame, 
                              technical_weight: float = 0.7,
                              ml_weight: float = 0.3) -> pd.DataFrame:
        """
        Generate hybrid trading signals combining technical and ML signals.
        
        Args:
            df: Input DataFrame with price data
            technical_weight: Weight for technical signals (0-1)
            ml_weight: Weight for ML signals (0-1)
            
        Returns:
            DataFrame with hybrid signals
        """
        if not XGBOOST_AVAILABLE or self.ml_model is None:
            ml_logger.warning("ML model not available, using only technical signals")
            return self._generate_technical_signals(df)
            
        # Generate technical signals
        tech_signals = self._generate_technical_signals(df)
        
        # Generate ML signals if model is trained
        if self.ml_model.is_trained:
            try:
                ml_predictions = self.ml_model.predict(df)
                ml_signals = pd.Series(ml_predictions, index=df.index)
            except Exception as e:
                ml_logger.warning(f"Failed to generate ML signals: {e}")
                ml_signals = pd.Series(0, index=df.index)
        else:
            ml_logger.warning("ML model not trained, using only technical signals")
            ml_signals = pd.Series(0, index=df.index)
        
        # Combine signals (70% technical, 30% ML as default)
        hybrid_signals = (tech_signals * technical_weight) + (ml_signals * ml_weight)
        
        # Convert to discrete signals
        final_signals = pd.Series(0, index=df.index)
        final_signals[hybrid_signals > 0.1] = 1   # Buy
        final_signals[hybrid_signals < -0.1] = -1 # Sell
        
        # Create result DataFrame
        result_df = df.copy()
        result_df['tech_signal'] = tech_signals
        result_df['ml_signal'] = ml_signals
        result_df['hybrid_signal'] = hybrid_signals
        result_df['final_signal'] = final_signals
        
        return result_df
    
    def _generate_technical_signals(self, df: pd.DataFrame) -> pd.Series:
        """
        Generate technical trading signals.
        
        Args:
            df: Input DataFrame with price data
            
        Returns:
            Series with technical signals
        """
        signals = pd.Series(0, index=df.index)
        
        # Donchian breakout signals
        upper_dc, lower_dc = self.feature_engineer.calculate_donchian(df)
        signals[(df['close'] > upper_dc) & (df['close'].shift(1) <= upper_dc.shift(1))] = 1   # Buy breakout
        signals[(df['close'] < lower_dc) & (df['close'].shift(1) >= lower_dc.shift(1))] = -1  # Sell breakout
        
        # RSI signals
        rsi = self.feature_engineer.calculate_rsi(df['close'])
        signals[(rsi < 30) & (rsi.shift(1) >= 30)] = 1   # RSI oversold buy
        signals[(rsi > 70) & (rsi.shift(1) <= 70)] = -1  # RSI overbought sell
        
        # MACD signals
        macd_line, signal_line = self.feature_engineer.calculate_macd(df['close'])
        macd_histogram = macd_line - signal_line
        signals[(macd_histogram > 0) & (macd_histogram.shift(1) <= 0)] = 1   # MACD bullish crossover
        signals[(macd_histogram < 0) & (macd_histogram.shift(1) >= 0)] = -1  # MACD bearish crossover
        
        return signals
    
    def log_predictions(self, df: pd.DataFrame) -> None:
        """
        Log ML predictions for monitoring.
        
        Args:
            df: Input DataFrame with price data
        """
        if not XGBOOST_AVAILABLE or self.ml_model is None:
            return
            
        try:
            if self.ml_model.is_trained:
                predictions = self.ml_model.predict(df)
                probabilities = self.ml_model.predict_proba(df)
                
                # Log recent predictions
                recent_idx = df.index[-5:] if len(df) >= 5 else df.index
                for idx in recent_idx:
                    if idx in predictions.index:
                        pred = predictions.loc[idx]
                        prob = probabilities.loc[idx] if idx in probabilities.index else None
                        signal_text = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(pred, "UNKNOWN")
                        ml_logger.info(f"ML Prediction for {idx}: {signal_text}")
                        if prob is not None:
                            ml_logger.info(f"  Probabilities - Sell: {prob['sell_prob']:.3f}, "
                                         f"Hold: {prob['hold_prob']:.3f}, Buy: {prob['buy_prob']:.3f}")
            else:
                ml_logger.info("ML model not trained yet")
        except Exception as e:
            ml_logger.error(f"Error logging predictions: {e}")
    
    def enable_live_trading(self) -> None:
        """Enable live trading mode (after paper trading validation)."""
        self.paper_trading_mode = False
        ml_logger.info("Live trading mode enabled")
    
    def is_ready_for_live_trading(self) -> bool:
        """
        Check if the system is ready for live trading.
        
        Returns:
            True if ready for live trading, False otherwise
        """
        if not XGBOOST_AVAILABLE or self.ml_model is None:
            return False
            
        return self.ml_model.is_trained and not self.paper_trading_mode


# Example usage
if __name__ == "__main__":
    # This is just for demonstration purposes
    ml_logger.info("ML Engine initialized")
    ml_logger.info("XGBoost available: %s", XGBOOST_AVAILABLE)