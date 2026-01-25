#!/usr/bin/env python3
"""Script to train the ML Strategy Validator"""

import logging

from core.quant.validators.ml_validator import MLStrategyValidator


def train_ml_validator(data_days: int = 60, symbol: str = "XAUUSD"):
    """Train the ML validator model
    
    Args:
        data_days: Number of days of historical data to use for training
        symbol: Trading symbol to train on
    """
    logging.basicConfig(level=logging.INFO)

    print("🤖 Training ML Strategy Validator")
    print("=" * 50)
    print(f"📊 Using {data_days} days of {symbol} data")
    print()

    try:
        # Initialize validator
        validator = MLStrategyValidator()

        # Train model
        print("Training model with historical data...")
        results = validator.train_from_history(symbol=symbol, n_days=data_days)

        if "error" in results:
            print(f"❌ Training failed: {results['error']}")
            return False

        # Display results
        print("✅ Training completed successfully!")
        print("📊 Training Results:")
        print(f"   - Training samples: {results['training_samples']}")
        print(f"   - Test samples: {results['test_samples']}")
        print(f"   - Training accuracy: {results['train_accuracy']:.3f}")
        print(f"   - Test accuracy: {results['test_accuracy']:.3f}")

        print("\n📈 Classification Report:")
        report = results['classification_report']
        for class_label, metrics in report.items():
            if isinstance(metrics, dict):
                precision = metrics.get('precision', 0)
                recall = metrics.get('recall', 0)
                f1 = metrics.get('f1-score', 0)
                support = metrics.get('support', 0)
                print(f"   {class_label}: Precision={precision:.3f}, "
                      f"Recall={recall:.3f}, F1={f1:.3f}, Support={support}")

        print("\n🎯 Feature Importances:")
        importances = results['feature_importances']
        sorted_features = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        for feature, importance in sorted_features:
            print(f"   {feature}: {importance:.3f}")

        print(f"\n💾 Model saved to: {validator.model_path}")

        return True

    except Exception as e:
        print(f"❌ Error during training: {e}")
        logging.exception("Training error")
        return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Train ML Strategy Validator')
    parser.add_argument('--days', type=int, default=60,
                       help='Number of days of historical data (default: 60)')
    parser.add_argument('--symbol', type=str, default='XAUUSD',
                       help='Trading symbol (default: XAUUSD)')

    args = parser.parse_args()

    success = train_ml_validator(data_days=args.days, symbol=args.symbol)
    exit(0 if success else 1)
