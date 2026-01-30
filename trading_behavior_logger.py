#!/usr/bin/env python3
"""Sistema de documentación estructurada del comportamiento del trading bot
Genera registros detallados de decisiones, performance y métricas en tiempo real
"""

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any


class TradingBehaviorLogger:
    """Logger avanzado para documentar comportamiento del sistema de trading"""

    def __init__(self, log_directory: str = "logs"):
        self.log_dir = Path(log_directory)
        self.log_dir.mkdir(exist_ok=True)

        # Archivos de log
        self.decision_log = self.log_dir / "decisiones_{}.csv".format(
            datetime.now().strftime("%Y%m%d")
        )
        self.performance_log = self.log_dir / "performance_{}.json".format(
            datetime.now().strftime("%Y%m%d")
        )
        self.summary_log = self.log_dir / "resumen_diario_{}.txt".format(
            datetime.now().strftime("%Y%m%d")
        )

        # Inicializar archivos
        self._initialize_logs()

        # Contadores y métricas
        self.metrics: dict[str, Any] = {
            'total_analisis': 0,
            'trades_aprobados': 0,
            'trades_rechazados': 0,
            'ml_aprobados': 0,
            'ml_rechazados': 0,
            'quant_aprobados': 0,
            'quant_rechazados': 0,
            'decisiones_por_simbolo': {},  # type: Dict[str, Dict[str, int]]
            'patrones_identificados': []  # type: List[str]
        }

        logging.info("TradingBehaviorLogger inicializado")

    def _initialize_logs(self):
        """Inicializar archivos de log con headers"""
        # Decision log CSV
        if not self.decision_log.exists():
            with open(self.decision_log, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'adx', 'di_plus', 'di_minus', 'di_diff',
                    'quant_score', 'quant_recommendation', 'ml_action', 'ml_confidence',
                    'ml_approved', 'final_decision', 'reason', 'market_conditions'
                ])

        # Performance log JSON
        if not self.performance_log.exists():
            with open(self.performance_log, 'w', encoding='utf-8') as f:
                json.dump({'sessions': []}, f, indent=2, ensure_ascii=False)

    def log_decision(self, analysis_result: dict[str, Any]):
        """Registrar una decisión del sistema"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Extraer datos del análisis
            symbol = analysis_result.get('symbol', 'UNKNOWN')
            market_data = analysis_result.get('market_data', {})
            ml_validation = analysis_result.get('ml_validation', {})

            # Datos de mercado
            adx = market_data.get('adx', 0)
            di_plus = market_data.get('di_plus', 0)
            di_minus = market_data.get('di_minus', 0)
            di_diff = market_data.get('di_difference', 0)

            # Análisis cuantitativo
            quant_score = analysis_result.get('entry_score', 0)
            quant_recommendation = analysis_result.get('recommendation', 'UNKNOWN')

            # Validación ML
            ml_action = ml_validation.get('ml_action', 'HOLD')
            ml_confidence = ml_validation.get('ml_confidence', 0)
            ml_approved = ml_validation.get('ml_approved', False)

            # Decisión final
            final_decision = analysis_result.get('should_trade', False)
            reason = analysis_result.get('reason', 'No especificado')

            # Condiciones de mercado resumidas
            market_conditions = self._summarize_market_conditions(
                adx, di_plus, di_minus, quant_score
            )

            # Registrar en CSV
            with open(self.decision_log, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    timestamp, symbol, adx, di_plus, di_minus, di_diff,
                    quant_score, quant_recommendation, ml_action, ml_confidence,
                    ml_approved, final_decision, reason, market_conditions
                ])

            # Actualizar métricas
            self._update_metrics(
                symbol, final_decision, ml_approved,
                quant_recommendation != 'AVOID'
            )

            logging.info(f"Decision registrada: {symbol} - {final_decision}")

        except Exception as e:
            logging.error(f"Error registrando decisión: {e}")

    def _summarize_market_conditions(self, adx: float, di_plus: float,
                                   di_minus: float, quant_score: float) -> str:
        """Resumir condiciones de mercado en texto legible"""
        conditions = []

        # Tendencia según ADX
        if adx > 25:
            conditions.append("Tendencia fuerte")
        elif adx > 20:
            conditions.append("Tendencia moderada")
        else:
            conditions.append("Sin tendencia clara")

        # Dirección
        if di_plus > di_minus:
            conditions.append("Alcista")
        else:
            conditions.append("Bajista")

        # Calidad de señal
        if quant_score > 0.7:
            conditions.append("Señal fuerte")
        elif quant_score > 0.5:
            conditions.append("Señal moderada")
        else:
            conditions.append("Señal débil")

        return " | ".join(conditions)

    def _update_metrics(self, symbol: str, final_decision: bool,
                       ml_approved: bool, quant_approved: bool):
        """Actualizar contadores y métricas"""
        self.metrics['total_analisis'] += 1

        if final_decision:
            self.metrics['trades_aprobados'] += 1
        else:
            self.metrics['trades_rechazados'] += 1

        if ml_approved:
            self.metrics['ml_aprobados'] += 1
        else:
            self.metrics['ml_rechazados'] += 1

        if quant_approved:
            self.metrics['quant_aprobados'] += 1
        else:
            self.metrics['quant_rechazados'] += 1

        # Contar por símbolo
        if symbol not in self.metrics['decisiones_por_simbolo']:
            self.metrics['decisiones_por_simbolo'][symbol] = {'aprobadas': 0, 'rechazadas': 0}

        if final_decision:
            self.metrics['decisiones_por_simbolo'][symbol]['aprobadas'] += 1
        else:
            self.metrics['decisiones_por_simbolo'][symbol]['rechazadas'] += 1

    def generate_daily_summary(self) -> str:
        """Generar resumen diario de performance"""
        try:
            total = self.metrics['total_analisis']
            if total == 0:
                return "No hay datos suficientes para generar resumen"

            approved_rate = float(self.metrics['trades_aprobados']) / float(total) * 100
            ml_approval_rate = float(self.metrics['ml_aprobados']) / float(total) * 100
            quant_approval_rate = float(self.metrics['quant_aprobados']) / float(total) * 100

            summary = f"""
📊 RESUMEN DE PERFORMANCE - {datetime.now().strftime('%Y-%m-%d')}
{'='*50}

📈 ESTADÍSTICAS GENERALES:
   • Análisis totales: {total}
   • Trades aprobados: {self.metrics['trades_aprobados']} ({approved_rate:.1f}%)
   • Trades rechazados: {self.metrics['trades_rechazados']} ({100-approved_rate:.1f}%)

🤖 VALIDACIÓN ML:
   • Aprobados: {self.metrics['ml_aprobados']} ({ml_approval_rate:.1f}%)
   • Rechazados: {self.metrics['ml_rechazados']} ({100-ml_approval_rate:.1f}%)

🔢 ANÁLISIS CUANTITATIVO:
   • Aprobados: {self.metrics['quant_aprobados']} ({quant_approval_rate:.1f}%)
   • Rechazados: {self.metrics['quant_rechazados']} ({100-quant_approval_rate:.1f}%)

💱 POR SÍMBOLO:
"""

            for symbol, counts in self.metrics['decisiones_por_simbolo'].items():
                total_symbol = counts['aprobadas'] + counts['rechazadas']
                approval_rate = float(counts['aprobadas']) / float(total_symbol) * 100 if total_symbol > 0 else 0
                summary += f"   • {symbol}: {counts['aprobadas']}/{total_symbol} aprobadas ({approval_rate:.1f}%)\n"

            # Guardar resumen
            with open(self.summary_log, 'w', encoding='utf-8') as f:
                f.write(summary)

            return summary.strip()

        except Exception as e:
            logging.error(f"Error generando resumen: {e}")
            return f"Error generando resumen: {e}"

    def get_current_metrics(self) -> dict[str, Any]:
        """Obtener métricas actuales"""
        return self.metrics.copy()


# Singleton instance
_behavior_logger: TradingBehaviorLogger | None = None

def get_behavior_logger() -> TradingBehaviorLogger:
    """Obtener instancia singleton del logger"""
    global _behavior_logger
    if _behavior_logger is None:
        _behavior_logger = TradingBehaviorLogger()
    return _behavior_logger
