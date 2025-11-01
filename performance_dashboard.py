"""
Dashboard HTML interactivo con métricas de performance
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def generate_dashboard(trades_csv='logs/trades.csv', output_html='dashboard.html'):
    """Genera dashboard HTML con métricas visuales"""
    if not os.path.exists(trades_csv):
        print(f"No se encontró {trades_csv}")
        return
    
    try:
        df = pd.read_csv(trades_csv)
        df['timestamp_open'] = pd.to_datetime(df['timestamp_open'])
        
        # Calcular equity curve
        df['cumulative_pnl'] = df['pnl'].cumsum()
        
        # Crear subplots
        fig = make_subplots(
            rows=3, cols=2,
            subplot_titles=(
                'Equity Curve', 
                'Drawdown %',
                'Win/Loss Distribution', 
                'Trades by Hour of Day',
                'Monthly Performance', 
                'Profit Factor Evolution'
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}],
                [{"type": "histogram"}, {"type": "bar"}],
                [{"type": "bar"}, {"type": "scatter"}]
            ]
        )
        
        # 1. Equity Curve
        fig.add_trace(
            go.Scatter(
                x=df['timestamp_open'], 
                y=df['cumulative_pnl'],
                mode='lines',
                name='Equity',
                line=dict(color='cyan', width=2)
            ),
            row=1, col=1
        )
        
        # 2. Drawdown
        running_max = df['cumulative_pnl'].cummax()
        drawdown = ((df['cumulative_pnl'] - running_max) / running_max * 100)
        fig.add_trace(
            go.Scatter(
                x=df['timestamp_open'], 
                y=drawdown,
                fill='tozeroy',
                name='Drawdown',
                line=dict(color='red')
            ),
            row=1, col=2
        )
        
        # 3. Win/Loss Distribution
        fig.add_trace(
            go.Histogram(
                x=df['pnl'],
                nbinsx=50,
                name='P&L Distribution',
                marker=dict(
                    color=df['pnl'],
                    colorscale='RdYlGn',
                    showscale=True
                )
            ),
            row=2, col=1
        )
        
        # 4. Trades by Hour
        if 'hour_of_day' in df.columns:
            trades_by_hour = df.groupby('hour_of_day').size()
            fig.add_trace(
                go.Bar(
                    x=trades_by_hour.index,
                    y=trades_by_hour.values,
                    name='Trades/Hour',
                    marker=dict(color='lightblue')
                ),
                row=2, col=2
            )
        
        # 5. Monthly Performance
        df['month'] = df['timestamp_open'].dt.to_period('M').astype(str)
        monthly_pnl = df.groupby('month')['pnl'].sum()
        fig.add_trace(
            go.Bar(
                x=monthly_pnl.index,
                y=monthly_pnl.values,
                name='Monthly P&L',
                marker=dict(
                    color=monthly_pnl.values,
                    colorscale='RdYlGn',
                    showscale=False
                )
            ),
            row=3, col=1
        )
        
        # 6. Profit Factor Evolution (rolling 20 trades)
        if len(df) >= 20:
            window = min(20, len(df))
            wins = df['pnl'].rolling(window).apply(lambda x: x[x > 0].sum() if len(x[x > 0]) > 0 else 0)
            losses = df['pnl'].rolling(window).apply(lambda x: abs(x[x < 0].sum()) if len(x[x < 0]) > 0 else 1)
            pf = wins / losses.replace(0, 1)
            
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=pf,
                    mode='lines',
                    name='Profit Factor (20 trades)',
                    line=dict(color='purple', width=2)
                ),
                row=3, col=2
            )
        
        # Update layout
        fig.update_layout(
            title="Trading Performance Dashboard",
            height=900,
            showlegend=False
        )
        
        # Save to HTML
        fig.write_html(output_html)
        print(f"Dashboard saved to {output_html}")
        
    except Exception as e:
        logging.error(f"Error generating dashboard: {e}")

def main():
    """Main function"""
    logging.info("Generating performance dashboard...")
    generate_dashboard()

if __name__ == "__main__":
    main()