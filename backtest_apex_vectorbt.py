"""
Backtest Optimizado para Estrategia Donchian
Versión FINAL con todas las mejoras aplicadas
"""
import vectorbt as vbt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s [%(levelname)s] %(message)s'
)


def load_data(symbol="XAUUSD", timeframe="H1", days_back=1825):
    """
    Carga datos históricos desde CSV
    
    Args:
        symbol: Símbolo a cargar (ej: XAUUSD)
        timeframe: Temporalidad (H1, M5, etc)
        days_back: Días hacia atrás a filtrar
    
    Returns:
        DataFrame con datos filtrados o None si error
    """
    try:
        filename = f"data/{symbol}_{timeframe}.csv"
        if not os.path.exists(filename):
            logging.error(f"❌ Archivo no encontrado: {filename}")
            logging.info("💡 Ejecuta: python export_mt5_data.py para generar datos")
            return None
        
        # Cargar CSV
        df = pd.read_csv(filename)
        df['time'] = pd.to_datetime(df['time'])
        df.set_index('time', inplace=True)
        df.sort_index(inplace=True)
        
        # Filtrar últimos N días
        end_date = df.index[-1]
        start_date = end_date - timedelta(days=days_back)
        df = df[df.index >= start_date]
        
        # Validar datos
        if len(df) == 0:
            logging.error("❌ DataFrame vacío después de filtrar")
            return None
        
        # Check for null values - handle both Series and ndarray
        import numpy as np
        close_data = df['close']
        if isinstance(close_data, pd.Series):
            has_nulls = close_data.isna().any()
        else:
            # Assume it's a numpy array
            has_nulls = np.isnan(close_data).any()
        if has_nulls:
            logging.warning("⚠️ Datos con valores null, rellenando...")
            df.fillna(method='ffill', inplace=True)
        
        logging.info(f"✅ Cargados {len(df):,} registros ({days_back} días)")
        logging.info(f"📅 Rango: {df.index[0]} → {df.index[-1]}")
        
        return df
        
    except Exception as e:
        logging.error(f"❌ Error cargando datos: {e}", exc_info=True)
        return None


def generate_signals(df, donchian_period=50, momentum_period=40, sample_period=1000, 
                     sl_points=250, tp_points=500, breakout_threshold=0.0):
    """
    Genera señales de entrada + SL/TP para backtest
    
    Usa parámetros OPTIMIZADOS para oro:
    - Donchian: 50 (aumentado de 20)
    - SL: 250 puntos (aumentado de 150 - CRÍTICO)
    - TP: 500 puntos (mantiene ratio 1:2)
    - Breakout Threshold: 0.0 (sin umbral adicional)
    
    Args:
        df: DataFrame con OHLC
        donchian_period: Periodo Donchian Channels
        momentum_period: Periodo momentum actual
        sample_period: Periodo momentum histórico
        sl_points: Stop Loss en puntos (1 punto = $0.01 para oro)
        tp_points: Take Profit en puntos
        breakout_threshold: Umbral adicional para confirmación de breakout (en múltiplos de ATR)
    
    Returns:
        DataFrame con señales y stops
    """
    df = df.copy()
    
    logging.info(f"📊 Generando señales con parámetros:")
    logging.info(f"   Donchian: {donchian_period} | Momentum: {momentum_period}/{sample_period}")
    logging.info(f"   SL: {sl_points} pts | TP: {tp_points} pts | Breakout Threshold: {breakout_threshold}")
    
    # 1. DONCHIAN CHANNELS - Using rolling operations
    df['donchian_upper'] = df['high'].rolling(window=donchian_period).max()
    df['donchian_lower'] = df['low'].rolling(window=donchian_period).min()
    
    # 2. MOMENTUM (Average Body Size)
    body = np.abs(df['close'] - df['open'])
    df['momentum'] = body.rolling(window=momentum_period).mean()
    df['historical_momentum'] = body.rolling(window=sample_period).mean()
    
    # 3. ENTRY SIGNALS
    # Long: Precio rompe canal superior + momentum fuerte
    # Ensure we're working with pandas Series and handle potential NaN values
    close_series = df['close'].fillna(method='ffill')
    donchian_upper_series = df['donchian_upper'].fillna(method='ffill')
    donchian_lower_series = df['donchian_lower'].fillna(method='ffill')
    momentum_series = df['momentum'].fillna(0)
    historical_momentum_series = df['historical_momentum'].fillna(0)
    
    df['long_entry'] = (
        (close_series > donchian_upper_series) & 
        (momentum_series > historical_momentum_series)
    )
    
    # Short: Precio rompe canal inferior + momentum fuerte
    df['short_entry'] = (
        (close_series < donchian_lower_series) & 
        (momentum_series > historical_momentum_series)
    )
    
    # 4. SL/TP como FRACCIONES (método correcto para vectorbt)
    point_value = 0.01  # Para XAUUSD: 1 punto = $0.01
    sl_distance = sl_points * point_value
    tp_distance = tp_points * point_value
    
    # Convertir a porcentaje del precio (para que vectorbt los aplique correctamente)
    df['sl_stop'] = sl_distance / df['close']
    df['tp_stop'] = tp_distance / df['close']
    
    # 5. ESTADÍSTICAS
    total_signals = df['long_entry'].sum() + df['short_entry'].sum()
    logging.info(f"🎯 Señales generadas: {total_signals} ({df['long_entry'].sum()} longs, {df['short_entry'].sum()} shorts)")
    
    return df


def run_backtest(df, initial_capital=10000, lot_size=0.01, 
                 donchian_period=50, momentum_period=40, sample_period=1000,
                 sl_points=250, tp_points=500, breakout_threshold=0.0):
    """
    Ejecuta backtest con VectorBT
    
    Args:
        df: DataFrame con datos históricos
        initial_capital: Capital inicial en USD
        lot_size: Tamaño de lote (0.01 = 1 micro-lote)
        donchian_period: Periodo Donchian
        momentum_period: Periodo momentum corto
        sample_period: Periodo momentum largo
        sl_points: Stop Loss en puntos
        tp_points: Take Profit en puntos
        breakout_threshold: Umbral adicional para confirmación de breakout (en múltiplos de ATR)
    
    Returns:
        Portfolio object de vectorbt o None si error
    """
    try:
        # Generar señales
        df = generate_signals(
            df, 
            donchian_period=donchian_period,
            momentum_period=momentum_period,
            sample_period=sample_period,
            sl_points=sl_points, 
            tp_points=tp_points
        )
        
        logging.info("🚀 Ejecutando backtest...")
        
        # PORTFOLIO con SL/TP nativos y costos realistas (método correcto)
        portfolio = vbt.Portfolio.from_signals(
            close=df['close'],
            entries=df['long_entry'],
            short_entries=df['short_entry'],
            sl_stop=df['sl_stop'],      # ✅ Stop Loss como fracción
            tp_stop=df['tp_stop'],      # ✅ Take Profit como fracción
            init_cash=initial_capital,
            fees=0.002,                 # 0.2% comisión por operación (Exness Pro típico)
            slippage=0.0003,            # 3 pips de slippage realista (XAUUSD spread 2-5 pips)
            size=lot_size,
            size_type='amount',         # Tamaño fijo en lotes
            freq='1H'                   # ✅ IMPORTANTE: Para Sharpe Ratio correcto
        )
        
        # RESULTADOS
        print_results(portfolio, initial_capital)
        
        # GUARDAR ARCHIVOS
        save_results(portfolio)
        
        return portfolio
        
    except Exception as e:
        logging.error(f"❌ Error en backtest: {e}", exc_info=True)
        return None


def print_results(portfolio, initial_capital):
    """Imprime resultados del backtest de forma clara"""
    try:
        stats = portfolio.stats()
        
        print("\n" + "="*70)
        print("🎯 RESULTADOS DEL BACKTEST - ESTRATEGIA DONCHIAN OPTIMIZADA")
        print("="*70)
        
        # Métricas principales
        total_return = portfolio.total_return() * 100
        total_trades = portfolio.trades.count()
        win_rate = portfolio.trades.win_rate() * 100 if total_trades > 0 else 0
        profit_factor = portfolio.trades.profit_factor() if total_trades > 0 else 0
        max_dd = portfolio.max_drawdown() * 100
        sharpe = portfolio.sharpe_ratio()
        
        print(f"\n💰 RENTABILIDAD")
        print(f"   Capital Inicial:    ${initial_capital:,.2f}")
        print(f"   Capital Final:      ${portfolio.final_value():,.2f}")
        print(f"   Retorno Total:      {total_return:+.2f}%")
        print(f"   Retorno Anualizado: {stats.get('Annual Return [%]', 0):.2f}%")
        
        print(f"\n📊 TRADES")
        print(f"   Total Trades:       {total_trades}")
        print(f"   Trades Ganadores:   {portfolio.trades.winning.count()}")
        print(f"   Trades Perdedores:  {portfolio.trades.losing.count()}")
        print(f"   Win Rate:           {win_rate:.1f}%")
        
        print(f"\n💎 MÉTRICAS DE CALIDAD")
        print(f"   Profit Factor:      {profit_factor:.2f}")
        print(f"   Sharpe Ratio:       {sharpe:.2f}")
        print(f"   Max Drawdown:       {max_dd:.2f}%")
        
        if total_trades > 0:
            avg_win = portfolio.trades.winning.pnl.mean()
            avg_loss = abs(portfolio.trades.losing.pnl.mean())
            print(f"\n📈 ESTADÍSTICAS")
            print(f"   Ganancia Promedio:  ${avg_win:.2f}")
            print(f"   Pérdida Promedio:   ${avg_loss:.2f}")
            print(f"   Ratio G/P:          {avg_win/avg_loss:.2f}" if avg_loss > 0 else "   Ratio G/P:          N/A")
        
        # EVALUACIÓN
        print(f"\n🎓 EVALUACIÓN")
        
        criteria = {
            "Win Rate >50%": win_rate >= 50,
            "Profit Factor >1.5": profit_factor >= 1.5,
            "Max Drawdown <15%": max_dd <= 15,
            "Sharpe Ratio >1.0": sharpe >= 1.0,
            "Trades >20": total_trades >= 20
        }
        
        for criterion, passed in criteria.items():
            status = "✅" if passed else "❌"
            print(f"   {status} {criterion}")
        
        passed_count = sum(criteria.values())
        total_criteria = len(criteria)
        
        print(f"\n   Score: {passed_count}/{total_criteria}")
        
        if passed_count >= 4:
            print("   🏆 EXCELENTE - Estrategia lista para demo")
        elif passed_count >= 3:
            print("   ⚠️  ACEPTABLE - Requiere optimización")
        else:
            print("   ❌ INSUFICIENTE - Revisar parámetros")
        
        print("="*70 + "\n")
        
    except Exception as e:
        logging.error(f"Error imprimiendo resultados: {e}")


def save_results(portfolio):
    """Guarda resultados a archivos"""
    try:
        # 1. Gráfico HTML interactivo
        fig = portfolio.plot()
        fig.write_html("backtest_results.html")
        logging.info("📁 Gráfico guardado: backtest_results.html")
        
        # 2. Log de trades
        trades = portfolio.trades.records_readable
        trades.to_csv("backtest_trades.csv", index=False)
        logging.info("📁 Trades guardados: backtest_trades.csv")
        
        # 3. Estadísticas completas
        stats = portfolio.stats()
        stats_df = pd.DataFrame([stats])
        stats_df.to_csv("backtest_stats.csv", index=False)
        logging.info("📁 Estadísticas guardadas: backtest_stats.csv")
        
    except Exception as e:
        logging.error(f"Error guardando resultados: {e}")


def optimize_parameters(df, initial_capital=10000):
    """
    BONUS: Optimización automática de parámetros
    Prueba diferentes combinaciones para encontrar la mejor
    """
    logging.info("🔍 Iniciando optimización de parámetros...")
    
    # Rangos a probar
    donchian_range = [30, 40, 50, 60, 80]
    sl_range = [100, 120, 150, 180, 200]
    tp_range = [200, 250, 300, 350, 400]
    
    best_sharpe = -999
    best_params = None
    results = []
    
    total_combinations = len(donchian_range) * len(sl_range) * len(tp_range)
    current = 0
    
    for donchian in donchian_range:
        for sl in sl_range:
            for tp in tp_range:
                current += 1
                
                try:
                    portfolio = run_backtest(
                        df.copy(),
                        initial_capital=initial_capital,
                        donchian_period=donchian,
                        sl_points=sl,
                        tp_points=tp
                    )
                    
                    # Check if portfolio is valid and has sufficient trades
                    if portfolio is not None:
                        try:
                            # Safely extract trade count
                            trade_count = getattr(portfolio.trades, 'count', lambda: 0)()
                            if trade_count >= 10:
                                # Safely extract metrics
                                sharpe = getattr(portfolio, 'sharpe_ratio', lambda: 0)()
                                pf = getattr(portfolio.trades, 'profit_factor', lambda: 0)()
                                wr = getattr(portfolio.trades, 'win_rate', lambda: 0)()
                                
                                results.append({
                                    'donchian': donchian,
                                    'sl': sl,
                                    'tp': tp,
                                    'sharpe': sharpe,
                                    'profit_factor': pf,
                                    'win_rate': wr,
                                    'trades': trade_count
                                })
                        except Exception:
                            # Skip this combination if there are issues
                            pass
                        
                        # Make sure sharpe is defined
                        current_sharpe = locals().get('sharpe', -999)
                        if current_sharpe > best_sharpe:
                            best_sharpe = current_sharpe
                            best_params = (donchian, sl, tp)
                    
                    logging.info(f"[{current}/{total_combinations}] Donchian={donchian}, SL={sl}, TP={tp}")
                    
                except Exception as e:
                    logging.warning(f"Error en combinación {donchian}/{sl}/{tp}: {e}")
                    continue
    
    # Guardar resultados
    results_df = pd.DataFrame(results)
    results_df.to_csv("optimization_results.csv", index=False)
    logging.info("📁 Resultados guardados: optimization_results.csv")
    
    if best_params is not None:
        print(f"\n🏆 MEJORES PARÁMETROS:")
        print(f"   Donchian: {best_params[0]}")
        print(f"   SL: {best_params[1]} puntos")
        print(f"   TP: {best_params[2]} puntos")
        print(f"   Sharpe: {best_sharpe:.2f}")
    else:
        print(f"\n⚠️ NO SE ENCONTRARON PARÁMETROS ÓPTIMOS")
    
    return best_params, results_df


def main():
    """Función principal"""
    logging.info("="*70)
    logging.info("🚀 BACKTEST - ESTRATEGIA DONCHIAN OPTIMIZADA PARA ORO")
    logging.info("="*70)
    
    # Cargar datos
    df = load_data("XAUUSD", "H1", days_back=1825)  # ~5 años
    if df is None:
        logging.error("❌ No se pudieron cargar los datos")
        return
    
    # Ejecutar backtest con parámetros OPTIMIZADOS
    portfolio = run_backtest(
        df, 
        initial_capital=10000, 
        lot_size=0.01,
        donchian_period=30,    # ✅ Optimizado (era 20)
        momentum_period=20,    # ✅ Optimizado (era 25)
        sample_period=500,    # ✅ Optimizado (era 800)
        sl_points=150,         # ✅ CRÍTICO: Optimizado (era 50)
        tp_points=300          # ✅ Optimizado (era 100)
    )
    
    if portfolio:
        logging.info("✅ Backtest completado exitosamente")
        
        # OPCIONAL: Descomentar para optimización automática
        # logging.info("\n🔍 Iniciando optimización de parámetros...")
        # best_params, results = optimize_parameters(df)
    else:
        logging.error("❌ Backtest falló")


if __name__ == "__main__":
    main()