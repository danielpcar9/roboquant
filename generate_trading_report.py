#!/usr/bin/env python3
"""Generador de reportes del comportamiento del sistema de trading
Analiza logs históricos y genera insights para mejora del sistema
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from trading_behavior_logger import get_behavior_logger


class TradingPerformanceAnalyzer:
    """Analizador de performance y generador de insights"""
    
    def __init__(self, log_directory: str = "logs"):
        self.log_dir = Path(log_directory)
        self.behavior_logger = get_behavior_logger()
    
    def analyze_daily_performance(self, date_str: str = None) -> Dict[str, Any]:
        """Analizar performance diaria"""
        if date_str is None:
            date_str = datetime.now().strftime("%Y%m%d")
        
        # Leer archivo de decisiones
        decision_file = self.log_dir / f"decisiones_{date_str}.csv"
        if not decision_file.exists():
            return {"error": "No hay datos para la fecha especificada"}
        
        try:
            df = pd.read_csv(decision_file)
            
            analysis = {
                "fecha": date_str,
                "total_analisis": len(df),
                "aprobados": int(df['final_decision'].sum()),
                "rechazados": int((~df['final_decision']).sum()),
                "tasa_aprobacion": (df['final_decision'].mean() * 100),
                "metricas_ml": {
                    "aprobados": int(df['ml_approved'].sum()),
                    "tasa_aprobacion": (df['ml_approved'].mean() * 100)
                },
                "metricas_cuantitativas": {
                    "promedio_score": df['quant_score'].mean(),
                    "score_maximo": df['quant_score'].max(),
                    "score_minimo": df['quant_score'].min()
                },
                "por_simbolo": self._analyze_by_symbol(df),
                "patrones_comunes": self._identify_patterns(df),
                "condiciones_mercado": self._analyze_market_conditions(df)
            }
            
            return analysis
            
        except Exception as e:
            return {"error": f"Error analizando datos: {e}"}
    
    def _analyze_by_symbol(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizar performance por símbolo"""
        symbol_analysis = {}
        
        for symbol in df['symbol'].unique():
            symbol_df = df[df['symbol'] == symbol]
            symbol_analysis[symbol] = {
                "total": len(symbol_df),
                "aprobados": int(symbol_df['final_decision'].sum()),
                "tasa_aprobacion": (symbol_df['final_decision'].mean() * 100),
                "score_promedio": symbol_df['quant_score'].mean(),
                "confianza_ml_promedio": symbol_df['ml_confidence'].mean()
            }
        
        return symbol_analysis
    
    def _identify_patterns(self, df: pd.DataFrame) -> List[str]:
        """Identificar patrones comunes en las decisiones"""
        patterns = []
        
        # Patrones de aprobación
        high_confidence_approved = df[(df['ml_confidence'] > 0.8) & (df['final_decision'] == True)]
        if len(high_confidence_approved) > 0:
            patterns.append(f"Alta confianza ML (+80%) resultó en {len(high_confidence_approved)} aprobaciones")
        
        # Patrones de rechazo
        strong_signals_rejected = df[(df['quant_score'] > 0.7) & (df['final_decision'] == False)]
        if len(strong_signals_rejected) > 0:
            patterns.append(f"Señales fuertes cuantitativas (+70%) rechazadas {len(strong_signals_rejected)} veces")
        
        # Tendencias en condiciones de mercado
        trending_markets = df[df['market_conditions'].str.contains('Tendencia fuerte|Tendencia moderada', na=False)]
        if len(trending_markets) > 0:
            approval_rate = trending_markets['final_decision'].mean() * 100
            patterns.append(f"En mercados con tendencia: {approval_rate:.1f}% de aprobación")
        
        return patterns
    
    def _analyze_market_conditions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Analizar condiciones de mercado predominantes"""
        conditions = {
            "tendencia_fuerte": len(df[df['market_conditions'].str.contains('Tendencia fuerte', na=False)]),
            "tendencia_moderada": len(df[df['market_conditions'].str.contains('Tendencia moderada', na=False)]),
            "sin_tendencia": len(df[df['market_conditions'].str.contains('Sin tendencia clara', na=False)]),
            "alcistas": len(df[df['market_conditions'].str.contains('Alcista', na=False)]),
            "bajistas": len(df[df['market_conditions'].str.contains('Bajista', na=False)])
        }
        
        return conditions
    
    def generate_improvement_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generar recomendaciones basadas en el análisis"""
        recommendations = []
        
        if "error" in analysis:
            return [f"Error en análisis: {analysis['error']}"]
        
        # Recomendaciones basadas en métricas
        approval_rate = analysis['tasa_aprobacion']
        if approval_rate < 20:
            recommendations.append("Considerar reducir umbrales de aprobación - sistema muy restrictivo")
        elif approval_rate > 80:
            recommendations.append("Considerar aumentar umbrales de aprobación - sistema muy permisivo")
        
        # Recomendaciones por símbolo
        for symbol, metrics in analysis['por_simbolo'].items():
            if metrics['tasa_aprobacion'] < 10:
                recommendations.append(f"Revisar parámetros para {symbol} - muy pocas aprobaciones")
            elif metrics['tasa_aprobacion'] > 90:
                recommendations.append(f"Revisar filtros para {symbol} - demasiadas aprobaciones")
        
        # Recomendaciones basadas en patrones
        if analysis['metricas_ml']['tasa_aprobacion'] < 30:
            recommendations.append("Revisar modelo ML - baja tasa de aprobación")
        
        if len(analysis['patrones_comunes']) > 0:
            recommendations.append("Patrones identificados:")
            recommendations.extend([f"  • {pattern}" for pattern in analysis['patrones_comunes']])
        
        return recommendations
    
    def generate_comprehensive_report(self, date_str: str = None) -> str:
        """Generar reporte completo"""
        analysis = self.analyze_daily_performance(date_str)
        
        if "error" in analysis:
            return f"❌ {analysis['error']}"
        
        recommendations = self.generate_improvement_recommendations(analysis)
        
        report = f"""
🤖 REPORTE COMPREHENSIVO DE TRADING - {analysis['fecha']}
{'='*60}

📊 RESUMEN GENERAL:
   • Análisis totales: {analysis['total_analisis']}
   • Trades aprobados: {analysis['aprobados']} ({analysis['tasa_aprobacion']:.1f}%)
   • Trades rechazados: {analysis['rechazados']} ({100-analysis['tasa_aprobacion']:.1f}%)

🧠 VALIDACIÓN ML:
   • Aprobados: {analysis['metricas_ml']['aprobados']} ({analysis['metricas_ml']['tasa_aprobacion']:.1f}%)

📈 ANÁLISIS CUANTITATIVO:
   • Score promedio: {analysis['metricas_cuantitativas']['promedio_score']:.3f}
   • Score máximo: {analysis['metricas_cuantitativas']['score_maximo']:.3f}
   • Score mínimo: {analysis['metricas_cuantitativas']['score_minimo']:.3f}

💱 ANÁLISIS POR SÍMBOLO:
"""
        
        for symbol, metrics in analysis['por_simbolo'].items():
            report += f"   • {symbol}: {metrics['aprobados']}/{metrics['total']} aprobadas "
            report += f"({metrics['tasa_aprobacion']:.1f}%) - Score: {metrics['score_promedio']:.3f}\n"
        
        report += f"""
🔍 CONDICIONES DE MERCADO:
   • Tendencia fuerte: {analysis['condiciones_mercado']['tendencia_fuerte']}
   • Tendencia moderada: {analysis['condiciones_mercado']['tendencia_moderada']}
   • Sin tendencia clara: {analysis['condiciones_mercado']['sin_tendencia']}
   • Alcistas: {analysis['condiciones_mercado']['alcistas']}
   • Bajistas: {analysis['condiciones_mercado']['bajistas']}

💡 RECOMENDACIONES PARA MEJORA:
"""
        
        for i, rec in enumerate(recommendations, 1):
            report += f"   {i}. {rec}\n"
        
        return report


def main():
    """Generar reporte del día"""
    analyzer = TradingPerformanceAnalyzer()
    report = analyzer.generate_comprehensive_report()
    print(report)
    
    # Guardar reporte
    report_file = Path("logs") / f"reporte_completo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📄 Reporte guardado en: {report_file}")


if __name__ == "__main__":
    main()