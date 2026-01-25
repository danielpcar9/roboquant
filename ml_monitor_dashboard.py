#!/usr/bin/env python3
"""Dashboard de monitoreo del entrenamiento ML"""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def monitor_ml_performance():
    """Monitoriza el rendimiento del modelo ML"""
    print("📊 Dashboard de Monitorización ML")
    print("=" * 40)

    # Leer métricas
    metrics_file = Path("logs/training_metrics.csv")
    if not metrics_file.exists():
        print("❌ No hay datos de entrenamiento disponibles")
        print("💡 Ejecuta primero: uv run python train_ml_validator.py")
        return

    try:
        # Cargar datos
        df = pd.read_csv(metrics_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        print(f"📈 Historial de entrenamiento: {len(df)} ejecuciones")
        print(f"📅 Rango: {df['timestamp'].min()} a {df['timestamp'].max()}")
        print()

        # Estadísticas generales
        print("📊 Estadísticas Generales:")
        print(f"   Accuracy promedio: {df['test_accuracy'].mean():.3f}")
        print(f"   Mejor accuracy: {df['test_accuracy'].max():.3f}")
        print(f"   Peor accuracy: {df['test_accuracy'].min():.3f}")
        print(f"   Desviación estándar: {df['test_accuracy'].std():.3f}")
        print()

        # Distribución de etiquetas
        print("🏷️  Distribución de Etiquetas:")
        avg_buy = df['buy_labels'].mean()
        avg_sell = df['sell_labels'].mean()
        avg_hold = df['hold_labels'].mean()
        total_avg = avg_buy + avg_sell + avg_hold

        print(f"   BUY promedio: {avg_buy:.0f} ({avg_buy/total_avg*100:.1f}%)")
        print(f"   SELL promedio: {avg_sell:.0f} ({avg_sell/total_avg*100:.1f}%)")
        print(f"   HOLD promedio: {avg_hold:.0f} ({avg_hold/total_avg*100:.1f}%)")
        print()

        # Gráficos
        if len(df) > 1:
            create_visualizations(df)

        # Último entrenamiento
        latest = df.iloc[-1]
        print("🎯 Último Entrenamiento:")
        print(f"   Fecha: {latest['timestamp']}")
        print(f"   Accuracy: {latest['test_accuracy']:.3f}")
        print(f"   Samples: {latest['samples']}")
        print()

        # Tendencias
        if len(df) >= 3:
            recent_trend = df.tail(3)['test_accuracy'].mean()
            overall_trend = df['test_accuracy'].mean()

            trend = "↗️  Mejorando" if recent_trend > overall_trend else "↘️  Estable/Declinando"
            print(f"Tendencia reciente: {trend}")

    except Exception as e:
        print(f"❌ Error al leer métricas: {e}")
        logging.exception("Error en dashboard")

def create_visualizations(df):
    """Crea gráficos de visualización"""
    try:
        # Configurar estilo
        plt.style.use('seaborn-v0_8')
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('Dashboard de Entrenamiento ML', fontsize=16)

        # 1. Evolución del accuracy
        axes[0, 0].plot(df['timestamp'], df['test_accuracy'], marker='o', linewidth=2)
        axes[0, 0].set_title('Accuracy a lo largo del tiempo')
        axes[0, 0].set_ylabel('Test Accuracy')
        axes[0, 0].grid(True, alpha=0.3)
        axes[0, 0].tick_params(axis='x', rotation=45)

        # 2. Distribución de accuracy
        axes[0, 1].hist(df['test_accuracy'], bins=10, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0, 1].set_title('Distribución de Accuracy')
        axes[0, 1].set_xlabel('Test Accuracy')
        axes[0, 1].set_ylabel('Frecuencia')
        axes[0, 1].grid(True, alpha=0.3)

        # 3. Tamaño de muestras
        axes[1, 0].plot(df['timestamp'], df['samples'], marker='s', color='orange', linewidth=2)
        axes[1, 0].set_title('Evolución del tamaño de muestras')
        axes[1, 0].set_ylabel('Número de samples')
        axes[1, 0].grid(True, alpha=0.3)
        axes[1, 0].tick_params(axis='x', rotation=45)

        # 4. Distribución de etiquetas
        axes[1, 1].bar(['BUY', 'SELL', 'HOLD'],
                      [df['buy_labels'].mean(), df['sell_labels'].mean(), df['hold_labels'].mean()],
                      color=['green', 'red', 'gray'])
        axes[1, 1].set_title('Distribución promedio de etiquetas')
        axes[1, 1].set_ylabel('Cantidad promedio')
        axes[1, 1].grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig('logs/ml_dashboard.png', dpi=300, bbox_inches='tight')
        print("📊 Gráfico guardado en: logs/ml_dashboard.png")
        print()

    except Exception as e:
        print(f"❌ Error al crear visualizaciones: {e}")

def main():
    """Punto de entrada principal"""
    # Crear directorio de logs si no existe
    Path("logs").mkdir(exist_ok=True)

    monitor_ml_performance()

if __name__ == "__main__":
    main()
