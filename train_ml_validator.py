#!/usr/bin/env python3
"""Script to train the ML Strategy Validator"""

import logging

from core.quant.validators.ml_validator import MLStrategyValidator


def train_ml_validator():
    """Train the ML validator model"""
    logging.basicConfig(level=logging.INFO)

    print("🤖 Training ML Strategy Validator")
    print("=" * 50)

    try:
        # Initialize validator
        validator = MLStrategyValidator()

        # Train model
        print("Training model with available historical data...")
        results = validator.train_from_history(symbol="XAUUSD", n_days=30)  # Reduced to 30 days

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
                print(f"   {class_label}: Precision={metrics.get('precision', 0):.3f}, "
                      f"Recall={metrics.get('recall', 0):.3f}, F1={metrics.get('f1-score', 0):.3f}")

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
    success = train_ml_validator()
    exit(0 if success else 1)
