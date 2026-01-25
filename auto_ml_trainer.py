#!/usr/bin/env python3
"""Automated ML Training Scheduler
Entrena el modelo ML automáticamente con nueva información de mercado
"""

import logging
import time
from datetime import datetime
from pathlib import Path

import schedule

from core.quant.validators.ml_validator import MLStrategyValidator


class AutoMLTrainer:
    """Sistema automático de entrenamiento ML"""

    def __init__(self, training_interval_days: int = 7, data_days: int = 60):
        self.training_interval = training_interval_days
        self.data_days = data_days
        self.validator = MLStrategyValidator()
        self.log_file = Path("logs/ml_training.log")
        self.log_file.parent.mkdir(exist_ok=True)

        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info("AutoMLTrainer initialized")

    def train_model(self) -> bool:
        """Entrena el modelo con datos recientes"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.info(f"🚀 Iniciando entrenamiento automático - {timestamp}")

            # Entrenar modelo
            results = self.validator.train_from_history(
                symbol="XAUUSD",
                n_days=self.data_days
            )

            if "error" in results:
                self.logger.error(f"❌ Entrenamiento fallido: {results['error']}")
                return False

            # Registrar resultados
            self.logger.info("✅ Entrenamiento completado exitosamente")
            self.logger.info(f"📊 Accuracy: {results['test_accuracy']:.3f}")
            self.logger.info(f"📈 Samples: {results['training_samples']} training, {results['test_samples']} test")

            # Guardar métricas
            self._save_training_metrics(results, timestamp)

            return True

        except Exception as e:
            self.logger.error(f"❌ Error en entrenamiento: {e}")
            return False

    def _save_training_metrics(self, results: dict, timestamp: str):
        """Guarda métricas de entrenamiento en archivo CSV"""
        metrics_file = Path("logs/training_metrics.csv")

        # Crear header si no existe
        if not metrics_file.exists():
            with open(metrics_file, 'w') as f:
                f.write("timestamp,train_accuracy,test_accuracy,samples,buy_labels,sell_labels,hold_labels\n")

        # Guardar métricas
        buy_count = sum(1 for label in results.get('classification_report', {}).get('1', {}).get('support', 0))
        sell_count = sum(1 for label in results.get('classification_report', {}).get('-1', {}).get('support', 0))
        hold_count = sum(1 for label in results.get('classification_report', {}).get('0', {}).get('support', 0))

        with open(metrics_file, 'a') as f:
            f.write(f"{timestamp},{results['train_accuracy']:.4f},{results['test_accuracy']:.4f},"
                   f"{results['training_samples']},{buy_count},{sell_count},{hold_count}\n")

    def start_scheduler(self):
        """Inicia el scheduler de entrenamiento"""
        self.logger.info(f"⏰ Scheduler iniciado - Entrenamiento cada {self.training_interval} días")

        # Programar entrenamiento
        schedule.every(self.training_interval).days.do(self.train_model)

        # Ejecutar entrenamiento inicial
        self.logger.info("🎯 Ejecutando entrenamiento inicial...")
        self.train_model()

        # Mantener scheduler corriendo
        try:
            while True:
                schedule.run_pending()
                time.sleep(3600)  # Revisar cada hora
        except KeyboardInterrupt:
            self.logger.info("🛑 Scheduler detenido por usuario")
        except Exception as e:
            self.logger.error(f"❌ Error en scheduler: {e}")


def main():
    """Punto de entrada principal"""
    print("🤖 Auto ML Trainer - Sistema de Aprendizaje Continuo")
    print("=" * 55)
    print("Este sistema entrenará automáticamente el modelo ML")
    print("con nueva información de mercado de forma periódica.")
    print()

    # Configurar parámetros
    training_days = 7   # Entrenar cada 7 días
    data_days = 60      # Usar 60 días de datos históricos

    print("⚙️  Configuración:")
    print(f"   - Intervalo de entrenamiento: {training_days} días")
    print(f"   - Datos históricos: {data_days} días")
    print("   - Símbolo: XAUUSD")
    print()

    # Iniciar trainer
    trainer = AutoMLTrainer(training_interval_days=training_days, data_days=data_days)
    trainer.start_scheduler()


if __name__ == "__main__":
    main()
