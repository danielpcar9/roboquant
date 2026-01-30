#!/usr/bin/env python3
"""Monitor en tiempo real del comportamiento del sistema de trading
Muestra estadísticas actualizadas y alertas importantes
"""

import os
import time
from datetime import datetime

from trading_behavior_logger import get_behavior_logger


class RealTimeMonitor:
    """Monitor en tiempo real del sistema de trading"""

    def __init__(self, refresh_interval: int = 30):
        self.refresh_interval = refresh_interval
        self.behavior_logger = get_behavior_logger()
        self.previous_metrics = None

    def clear_screen(self):
        """Limpiar pantalla"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def display_current_status(self):
        """Mostrar estado actual del sistema"""
        self.clear_screen()

        metrics = self.behavior_logger.get_current_metrics()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print("🤖 MONITOR EN TIEMPO REAL - SISTEMA DE TRADING")
        print("=" * 55)
        print(f"🕐 Última actualización: {current_time}")
        print()

        # Estadísticas generales
        total = metrics['total_analisis']
        if total > 0:
            approval_rate = (metrics['trades_aprobados'] / total) * 100
            ml_approval_rate = (metrics['ml_aprobados'] / total) * 100
            quant_approval_rate = (metrics['quant_aprobados'] / total) * 100

            print("📊 ESTADÍSTICAS ACTUALES:")
            print(f"   Análisis totales: {total}")
            print(f"   Trades aprobados: {metrics['trades_aprobados']} ({approval_rate:.1f}%)")
            print(f"   Trades rechazados: {metrics['trades_rechazados']} ({100-approval_rate:.1f}%)")
            print()

            print("🤖 VALIDACIÓN ML:")
            print(f"   Aprobados: {metrics['ml_aprobados']} ({ml_approval_rate:.1f}%)")
            print(f"   Rechazados: {metrics['ml_rechazados']} ({100-ml_approval_rate:.1f}%)")
            print()

            print("🔢 ANÁLISIS CUANTITATIVO:")
            print(f"   Aprobados: {metrics['quant_aprobados']} ({quant_approval_rate:.1f}%)")
            print(f"   Rechazados: {metrics['quant_rechazados']} ({100-quant_approval_rate:.1f}%)")
            print()

            # Análisis por símbolo
            if metrics['decisiones_por_simbolo']:
                print("💱 POR SÍMBOLO:")
                for symbol, counts in metrics['decisiones_por_simbolo'].items():
                    symbol_total = counts['aprobadas'] + counts['rechazadas']
                    if symbol_total > 0:
                        symbol_rate = (counts['aprobadas'] / symbol_total) * 100
                        print(f"   {symbol}: {counts['aprobadas']}/{symbol_total} ({symbol_rate:.1f}%)")
                print()

            # Detectar cambios importantes
            self.detect_significant_changes(metrics)

        else:
            print("⏳ Esperando primeras decisiones...")
            print()

        print(f"🔄 Próxima actualización en {self.refresh_interval} segundos...")
        print(".presione Ctrl+C para salir")

    def detect_significant_changes(self, current_metrics: dict):
        """Detectar cambios significativos en el comportamiento"""
        if self.previous_metrics is None:
            self.previous_metrics = current_metrics.copy()
            return

        changes = []
        total_prev = self.previous_metrics['total_analisis']
        total_curr = current_metrics['total_analisis']

        if total_curr > total_prev:
            # Nuevo análisis detectado
            new_decisions = total_curr - total_prev

            # Verificar si hay aprobaciones
            new_approvals = current_metrics['trades_aprobados'] - self.previous_metrics['trades_aprobados']
            if new_approvals > 0:
                changes.append(f"✅ {new_approvals} NUEVA(S) APROBACIÓN(ES) DE TRADE")

            # Verificar cambios en tasas
            if total_curr >= 10:  # Suficientes datos para estadísticas significativas
                prev_rate = (self.previous_metrics['trades_aprobados'] / total_prev * 100) if total_prev > 0 else 0
                curr_rate = (current_metrics['trades_aprobados'] / total_curr * 100) if total_curr > 0 else 0

                if abs(curr_rate - prev_rate) > 5:  # Cambio significativo de 5%
                    direction = "aumentó" if curr_rate > prev_rate else "disminuyó"
                    changes.append(f"📈 Tasa de aprobación {direction}: {prev_rate:.1f}% → {curr_rate:.1f}%")

        # Alertas de comportamiento inusual
        if current_metrics['ml_aprobados'] > current_metrics['trades_aprobados']:
            changes.append("⚠️  ML aprueba más que sistema final - revisar umbrales")

        if changes:
            print("🔔 ALERTAS Y CAMBIOS:")
            for change in changes:
                print(f"   {change}")
            print()

        self.previous_metrics = current_metrics.copy()

    def start_monitoring(self):
        """Iniciar monitoreo continuo"""
        print("🚀 Iniciando monitor en tiempo real...")
        print("Presione Ctrl+C para detener")
        print()

        try:
            while True:
                self.display_current_status()
                time.sleep(self.refresh_interval)
        except KeyboardInterrupt:
            print("\n🛑 Monitor detenido por usuario")
            self.generate_final_summary()

    def generate_final_summary(self):
        """Generar resumen final al detener el monitor"""
        print("\n" + "="*50)
        print("📋 RESUMEN FINAL DE LA SESIÓN")
        print("="*50)

        summary = self.behavior_logger.generate_daily_summary()
        print(summary)

        # Guardar resumen
        print(f"\n💾 Resumen guardado en: logs/resumen_diario_{datetime.now().strftime('%Y%m%d')}.txt")


def main():
    """Punto de entrada principal"""
    monitor = RealTimeMonitor(refresh_interval=30)
    monitor.start_monitoring()


if __name__ == "__main__":
    main()
