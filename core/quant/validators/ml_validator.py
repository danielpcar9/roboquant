"""ML Strategy Validator for Enhanced Trade Decision Making
Uses machine learning to validate and enhance quantitative trading signals
"""

import contextlib
import logging
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split

from core.mt5_compat import mt5

from ...donchian_components.calculators.technical_indicators import (
    TechnicalIndicatorsCalculator,
)
from ..analyzers.statistical_analyzer import QuantitativeAnalyzer


class MLStrategyValidator:
    """Machine Learning validator for trading signals using Random Forest classification"""

    def __init__(self) -> None:
        """Initialize ML validator and load model if available."""
        # Initialize MT5 only when available
        if MT5_AVAILABLE:
            if not mt5.initialize():
                raise RuntimeError("Failed to initialize MT5")

        self.model = None
        self.feature_names = [
            'momentum_score', 'volatility_score', 'trend_strength',
            'adx', 'di_plus', 'di_minus',
            'channel_position', 'atr_normalized', 'volume_ratio'
        ]
        self.models_dir = Path("models")
        self.models_dir.mkdir(exist_ok=True)
        self.model_path = self.models_dir / "ml_validator.pkl"

        # Initialize components
        self.analyzer = QuantitativeAnalyzer()
        self.indicator_calculator = TechnicalIndicatorsCalculator()

        # Load existing model if available
        self._load_model()

        logging.info("MLStrategyValidator initialized")

    def __del__(self):
        if MT5_AVAILABLE:
            with contextlib.suppress(Exception):
                mt5.shutdown()

    def _load_model(self) -> None:
        """Load trained model from disk if exists"""
        try:
            if self.model_path.exists():
                self.model = joblib.load(self.model_path)
                logging.info(f"ML model loaded from {self.model_path}")
            else:
                logging.info("No existing ML model found, will train when data is available")
        except Exception as e:
            logging.warning(f"Failed to load ML model: {e}")
            self.model = None

    def _save_model(self) -> None:
        """Save trained model to disk"""
        try:
            joblib.dump(self.model, self.model_path)
            logging.info(f"ML model saved to {self.model_path}")
        except Exception as e:
            logging.error(f"Failed to save ML model: {e}")

    def extract_features(self, symbol: str) -> dict[str, float]:
        """Extract all required features for ML prediction"""
        try:
            if not MT5_AVAILABLE:
                logging.warning("MT5 not available; skipping feature extraction")
                return {}

            # Get price data
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 100)  # type: ignore
            if rates is None or len(rates) < 50:
                logging.warning("Insufficient price data for feature extraction")
                return {}

            prices = np.array([rate[4] for rate in rates])  # close prices
            volumes = np.array([rate[5] for rate in rates])  # volumes

            # Calculate quantitative features
            momentum_score = self.analyzer.calculate_momentum_score(prices)
            volatility_score = self.analyzer.calculate_volatility_score(prices)
            trend_strength = self.analyzer.calculate_trend_strength(prices)

            if adx_data := self.indicator_calculator.calculate_adx(symbol, 14):
                adx = adx_data.get('adx', 25.0)
                di_plus = adx_data.get('di_plus', 25.0)
                di_minus = adx_data.get('di_minus', 25.0)
            else:
                adx, di_plus, di_minus = 25.0, 25.0, 25.0

            # Calculate Donchian channels and position
            upper_channel, lower_channel = self.indicator_calculator.get_donchian_channels(symbol, 50)
            current_price = self.indicator_calculator.get_current_price(symbol, "BUY")

            if upper_channel and lower_channel and current_price:
                channel_width = upper_channel - lower_channel
                channel_position = (current_price - lower_channel) / channel_width if channel_width > 0 else 0.5
            else:
                channel_position = 0.5

            # Calculate ATR and volume ratio
            atr = self.indicator_calculator.calculate_atr(symbol, 14)
            atr_normalized = atr / current_price if atr and current_price else 0.001

            current_volume = volumes[-1] if len(volumes) > 0 else 1
            avg_volume = np.mean(volumes[-20:]) if len(volumes) >= 20 else current_volume
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0

            features = {
                'momentum_score': momentum_score,
                'volatility_score': volatility_score,
                'trend_strength': trend_strength,
                'adx': adx,
                'di_plus': di_plus,
                'di_minus': di_minus,
                'channel_position': channel_position,
                'atr_normalized': atr_normalized,
                'volume_ratio': volume_ratio
            }

            logging.debug(f"Features extracted for {symbol}: {features}")
            return features

        except Exception as e:
            logging.error(f"Error extracting features: {e}")
            return {}

    def validate_signal(self, features_dict: dict[str, float]) -> tuple[bool, float, str]:
        """Validate trading signal using ML model.

        Args:
            features_dict: Dictionary with all required features.

        Returns:
            Tuple of (should_trade, confidence, predicted_action).
        """
        if not self.model:
            logging.warning("No ML model available, returning neutral validation")
            return False, 0.0, "HOLD"

        try:
            return self._run_model_inference(features_dict)
        except Exception as e:
            logging.error(f"Error in ML validation: {e}")
            return False, 0.0, "HOLD"

    def _run_model_inference(self, features_dict: dict[str, float]) -> tuple[bool, float, str]:
        # Prepare feature vector
        feature_vector = np.array([[features_dict.get(name, 0.0) for name in self.feature_names]])

        # Get prediction and probabilities
        prediction = self.model.predict(feature_vector)[0]
        probabilities = self.model.predict_proba(feature_vector)[0]

        # Map prediction to action
        action_map = {1: "BUY", -1: "SELL", 0: "HOLD"}
        predicted_action = action_map.get(prediction, "HOLD")

        # Get confidence (max probability)
        confidence = float(np.max(probabilities))

        # Decision logic
        should_trade = (
            (prediction != 0 and confidence > 0.30) or  # Trade si BUY/SELL confianza >30%
            (prediction == 0 and confidence < 0.60)     # Permitir HOLD con baja confianza
        )

        logging.info(f"ML Validation - Action: {predicted_action}, Confidence: {confidence:.3f}, Trade: {should_trade}")

        return should_trade, confidence, predicted_action

    def create_labels(self, prices: np.ndarray, window: int = 5, threshold: float = 0.005) -> np.ndarray:
        """Create training labels based on future price movement

        Args:
            prices: Array of historical prices
            window: Number of periods to look forward
            threshold: Minimum price change to consider (0.5% default)

        Returns:
            Array of labels: 1 (BUY), -1 (SELL), 0 (HOLD)
        """
        labels = []

        # Ensure prices are float64 scalars
        prices = prices.astype(np.float64)

        for i in range(len(prices) - window):
            current_price = float(prices[i])  # Convert to scalar
            future_price = float(prices[i + window])  # Convert to scalar

            price_change = (future_price - current_price) / current_price

            if price_change > threshold:
                labels.append(1)  # BUY signal
            elif price_change < -threshold:
                labels.append(-1)  # SELL signal
            else:
                labels.append(0)  # HOLD signal

        return np.array(labels)

    def train_from_history(self, symbol: str = "XAUUSD", n_days: int = 90) -> dict[str, Any]:
        """Train ML model using historical data.

        Args:
            symbol: Trading symbol.
            n_days: Number of days of historical data to use.

        Returns:
            Dictionary with training results and metrics.
        """
        try:
            return self._train_model_from_history(symbol, n_days)
        except Exception as e:
            logging.error(f"Error training ML model: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return {"error": str(e)}

    def _train_model_from_history(self, symbol: str, n_days: int) -> dict[str, Any]:
        logging.info(f"Training ML validator for {symbol} using {n_days} days of data")

        if not MT5_AVAILABLE:
            raise RuntimeError("MT5 not available; cannot train from live history on this platform")

        # Get historical data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, n_days * 24)  # type: ignore
        logging.info(f"Requested {n_days * 24} bars, got {len(rates) if rates is not None else 0} bars")
        if rates is None or len(rates) < 50:
            raise ValueError(f"Insufficient historical data for training: got {len(rates) if rates is not None else 0} bars, need at least 50")

        prices = np.array([rate[4] for rate in rates]).astype(np.float64)
        logging.info(f"Retrieved {len(prices)} price points for training")

        # Create labels
        labels = self.create_labels(prices, window=5, threshold=0.005)
        logging.info(f"Created {len(labels)} labels: BUY={int(np.sum(labels==1))}, SELL={int(np.sum(labels==-1))}, HOLD={int(np.sum(labels==0))}")

        # Extract features for training data
        feature_data = []
        valid_labels = []

        # We need to align features with labels (labels are shorter due to window)
        for i in range(len(labels)):
            # Get features using data up to point i only (avoid look-ahead)
            temp_rates = rates[: i + 1]
            if len(temp_rates) < 50:
                continue

            temp_prices = np.array([rate[4] for rate in temp_rates]).astype(np.float64)

            # Calculate features using temporary data
            momentum_score = float(self.analyzer.calculate_momentum_score(temp_prices))
            volatility_score = float(self.analyzer.calculate_volatility_score(temp_prices))
            trend_strength = float(self.analyzer.calculate_trend_strength(temp_prices))

            # Compute indicators from historical window (no MT5 dependency)
            temp_df = self._rates_to_df(temp_rates)
            adx, di_plus, di_minus, atr = self._calculate_adx_di_atr(temp_df)

            upper_channel = temp_df["high"].rolling(50).max().iloc[-1]
            lower_channel = temp_df["low"].rolling(50).min().iloc[-1]
            current_price = temp_df["close"].iloc[-1]

            channel_width = upper_channel - lower_channel
            channel_position = (
                (current_price - lower_channel) / channel_width if channel_width > 0 else 0.5
            )

            atr_normalized = (atr / current_price) if atr and current_price else 0.001
            if "tick_volume" in temp_df.columns:
                current_volume = float(temp_df["tick_volume"].iloc[-1])
                avg_volume = float(temp_df["tick_volume"].iloc[-20:].mean())
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            else:
                volume_ratio = 1.0

            features = [
                momentum_score, volatility_score, trend_strength,
                adx, di_plus, di_minus,
                channel_position, atr_normalized, volume_ratio
            ]

            feature_data.append(features)
            valid_labels.append(int(labels[i]))

        if len(feature_data) < 30:  # Reduced from 50 to 30
            raise ValueError("Insufficient aligned data for training")

        # Convert to arrays
        X = np.array(feature_data, dtype=np.float64)
        y = np.array(valid_labels, dtype=np.int32)

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Train model
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42
        )

        self.model.fit(X_train, y_train)

        # Evaluate model
        train_score = self.model.score(X_train, y_train)
        test_score = self.model.score(X_test, y_test)

        # Predictions for metrics
        y_pred = self.model.predict(X_test)

        # Calculate metrics
        report = classification_report(y_test, y_pred, output_dict=True)
        confusion = confusion_matrix(y_test, y_pred)
        feature_importance = dict(zip(self.feature_names, self.model.feature_importances_, strict=True))

        # Save model
        self._save_model()

        results = {
            'training_samples': len(X_train),
            'test_samples': len(X_test),
            'train_accuracy': float(train_score),
            'test_accuracy': float(test_score),
            'classification_report': report,
            'confusion_matrix': confusion.tolist(),
            'feature_importances': feature_importance,
            'model_parameters': self.model.get_params()
        }

        logging.info(f"ML Model Training Complete - Accuracy: {test_score:.3f}")
        logging.info(f"Feature Importances: {feature_importance}")

        return results

    @staticmethod
    def _rates_to_df(rates) -> pd.DataFrame:
        return pd.DataFrame(rates)

    @staticmethod
    def _calculate_adx_di_atr(df: pd.DataFrame, period: int = 14) -> tuple[float, float, float, float]:
        """Calculate ADX, +DI, -DI, ATR from historical data."""
        high_low = df["high"] - df["low"]
        high_close = np.abs(df["high"] - df["close"].shift())
        low_close = np.abs(df["low"] - df["close"].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / period, adjust=False).mean()

        up_move = df["high"] - df["high"].shift()
        down_move = df["low"].shift() - df["low"]

        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()
        minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()

        plus_di = 100 * (plus_dm_smooth / atr.replace(0, np.nan))
        minus_di = 100 * (minus_dm_smooth / atr.replace(0, np.nan))

        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)
        adx = dx.ewm(alpha=1 / period, adjust=False).mean()

        adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 25.0
        plus_val = float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 25.0
        minus_val = float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 25.0
        atr_val = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0

        return adx_val, plus_val, minus_val, atr_val

# Backward compatibility
MLValidator = MLStrategyValidator
