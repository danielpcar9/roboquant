#!/usr/bin/env python3
"""Minimal training script to isolate the error"""

import numpy as np
import MetaTrader5 as mt5
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

def minimal_training():
    """Minimal training to test the concept"""
    print("🤖 Minimal ML Training Test")
    print("=" * 35)
    
    if not mt5.initialize():
        print("❌ Failed to initialize MT5")
        return False
    
    try:
        symbol = "XAUUSD"
        n_days = 10
        
        # Get data
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, n_days * 24)
        if rates is None or len(rates) < 50:
            print("❌ Insufficient data")
            return False
            
        print(f"✅ Got {len(rates)} data points")
        
        # Create simple features and labels
        prices = np.array([rate[4] for rate in rates]).astype(np.float64)
        
        # Simple labeling: positive/negative returns
        returns = np.diff(prices) / prices[:-1]
        labels = np.where(returns > 0.001, 1, np.where(returns < -0.001, -1, 0))
        
        # Simple features: lagged returns
        features = []
        feature_labels = []
        
        for i in range(5, len(returns)):
            feature_vector = [
                returns[i-5],
                returns[i-4], 
                returns[i-3],
                returns[i-2],
                returns[i-1],
                np.std(returns[i-10:i]) if i >= 10 else 0.01
            ]
            features.append(feature_vector)
            feature_labels.append(labels[i])
            
        if len(features) < 20:
            print("❌ Insufficient training data")
            return False
            
        X = np.array(features)
        y = np.array(feature_labels)
        
        print(f"✅ Created {len(X)} training samples")
        print(f"   Label distribution: BUY={np.sum(y==1)}, SELL={np.sum(y==-1)}, HOLD={np.sum(y==0)}")
        
        # Train simple model
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.3, random_state=42, stratify=y
        )
        
        model = RandomForestClassifier(n_estimators=50, random_state=42)
        model.fit(X_train, y_train)
        
        train_acc = model.score(X_train, y_train)
        test_acc = model.score(X_test, y_test)
        
        print(f"✅ Model trained successfully!")
        print(f"   Training accuracy: {train_acc:.3f}")
        print(f"   Test accuracy: {test_acc:.3f}")
        
        # Test prediction
        sample_pred = model.predict([X_test[0]])
        sample_prob = model.predict_proba([X_test[0]])[0]
        print(f"   Sample prediction: {sample_pred[0]}, confidence: {np.max(sample_prob):.3f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Training error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        mt5.shutdown()

if __name__ == "__main__":
    success = minimal_training()
    exit(0 if success else 1)