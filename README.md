# RoboQuant - Donchian Breakout Strategy

This repository contains a Python implementation of a Donchian Breakout trading strategy for MetaTrader 5.

## Strategy Overview

The Donchian Breakout strategy is based on the classic trend-following system developed by Richard Donchian. This implementation includes additional filters based on momentum to reduce false breakouts.

### Key Features:
- Donchian Channel breakout detection
- Momentum filter to avoid trading in low volatility conditions
- Configurable trading hours
- Risk management with Stop Loss and Take Profit levels
- Integration with existing safety checks
- Webhook receiver for external signals
- Backtesting capabilities
- Performance dashboard
- Enhanced security with encrypted credential storage
- Comprehensive error handling with circuit breaker pattern
- Machine learning integration for hybrid trading signals
- Event-driven trading based on economic calendar
- Performance monitoring and optimization
- Trade quality scoring system with 5 heuristics (0-100 points)
- Market regime detection (trending/ranging) using ADX and slope
- Adaptive risk management with dynamic SL/TP based on ATR
- Session filtering based on historical performance

## Files

- [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py) - Main strategy implementation
- [webhook_receiver.py](file://c:\Users\edgar\roboquant\webhook_receiver.py) - Webhook receiver for external signals
- [backtest_apex_vectorbt.py](file://c:\Users\edgar\roboquant\backtest_apex_vectorbt.py) - Backtesting script using VectorBT
- [performance_dashboard.py](file://c:\Users\edgar\roboquant\performance_dashboard.py) - Performance visualization dashboard
- [mt5_utils.py](file://c:\Users\edgar\roboquant\mt5_utils.py) - Utility functions for MT5 interaction
- [safety.py](file://c:\Users\edgar\roboquant\safety.py) - Safety checks module
- [alerts.py](file://c:\Users\edgar\roboquant\alerts.py) - Alert notifications
- [security_manager.py](file://c:\Users\edgar\roboquant\security_manager.py) - Security manager with credential handling, input validation, and rate limiting
- [error_handler.py](file://c:\Users\edgar\roboquant\error_handler.py) - Error handling with circuit breaker and retry logic
- [ml_engine.py](file://c:\Users\edgar\roboquant\ml_engine.py) - Machine learning engine with XGBoost model for hybrid trading signals
- [post_mortem.py](file://c:\Users\edgar\roboquant\post_mortem.py) - Post-trade analysis and performance metrics
- [api_cache.py](file://c:\Users\edgar\roboquant\api_cache.py) - Caching system for API responses
- [config_manager.py](file://c:\Users\edgar\roboquant\config_manager.py) - Centralized configuration management
- [trade_scorer.py](file://c:\Users\edgar\roboquant\trade_scorer.py) - Trade quality scoring system with 5 heuristics
- [market_regime.py](file://c:\Users\edgar\roboquant\market_regime.py) - Market regime detection (trending/ranging)
- [adaptive_risk.py](file://c:\Users\edgar\roboquant\adaptive_risk.py) - Adaptive risk management with dynamic SL/TP
- [session_filter.py](file://c:\Users\edgar\roboquant\session_filter.py) - Session filtering based on historical performance
- [run_donchian.bat](file://c:\Users\edgar\roboquant\run_donchian.bat) - Batch file to run the strategy on Windows
- [run_webhook.bat](file://c:\Users\edgar\roboquant\run_webhook.bat) - Batch file to run the webhook receiver
- [run_backtest.bat](file://c:\Users\edgar\roboquant\run_backtest.bat) - Batch file to run backtesting
- [test_mt5_connection.py](file://c:\Users\edgar\roboquant\test_mt5_connection.py) - Script to test MT5 connection
- [test_security.py](file://c:\Users\edgar\roboquant\test_security.py) - Test script for security components
- [test_post_mortem.py](file://c:\Users\edgar\roboquant\test_post_mortem.py) - Test script for post-trade analysis

## Enhanced Security Features

### Encrypted Credential Storage
- Credentials are now stored using the keyring library for enhanced security
- Falls back to environment variables if keyring is not available
- Automatic encryption/decryption of sensitive data

### IP Whitelisting
- Webhook receiver now supports IP whitelisting for enhanced security
- Configure allowed IPs via WEBHOOK_ALLOWED_IPS environment variable

### Rate Limiting Improvements
- Enhanced rate limiting with both global and per-IP tracking
- Better retry-after calculation for clients

## Performance Monitoring and Optimization

### Execution Time Monitoring
- All critical functions now include performance monitoring
- Execution times are logged for optimization purposes
- Average execution time tracking for strategy functions

### Enhanced Trade Analysis
- Comprehensive post-trade analysis with advanced metrics
- Detailed performance reports with Sharpe ratio, Sortino ratio, and Calmar ratio
- Time-based performance analysis to identify optimal trading hours

## Machine Learning Enhancements

### Improved Feature Engineering
- Enhanced technical indicators with better calculation methods
- Additional features for more accurate market analysis
- Better handling of missing data and edge cases

### Hybrid Signal Generation
- Improved combination of technical and ML signals
- Better weighting system for different signal types
- Enhanced error handling for ML model predictions

## Configuration Management

### Centralized Configuration
- All configuration parameters are now managed through a centralized config manager
- Easy parameter adjustment through environment variables
- Secure credential management through the same interface

## Trade Quality Scoring System

The system now includes a comprehensive trade quality scoring mechanism that evaluates trade setups on a 0-100 point scale using 5 heuristics:

1. **Breakout Strength (25 points)**: Measures the strength of the breakout relative to the channel width
2. **Momentum Ratio (25 points)**: Compares current momentum to historical momentum
3. **Time Session (20 points)**: Evaluates if the trade is occurring during optimal trading sessions
4. **ATR Volatility (15 points)**: Assesses volatility using Average True Range
5. **Spread (15 points)**: Evaluates current market spread conditions

Only trades scoring 60+ points are recommended for execution, with position sizing adjusted based on the score:
- Score ≥ 80: 1.5x position size
- Score ≥ 70: 1.0x position size (normal)
- Score ≥ 60: 0.75x position size

## Market Regime Detection

The system can detect market regimes (trending/ranging) using ADX and slope analysis to adjust trading behavior accordingly.

## Adaptive Risk Management

Dynamic stop loss and take profit levels are calculated based on current market volatility (ATR) to maintain consistent risk levels across different market conditions.

## Session Filtering

Historical performance analysis by trading session helps identify the most favorable times for trading specific instruments.

## Testing Improvements

### Comprehensive Test Coverage
- Added unit tests for post-trade analysis module
- Enhanced existing test coverage for security components

## Configuración Actualizada

Los parámetros de trading han sido optimizados para operar eficazmente con el oro (XAUUSD), considerando su volatilidad y sesiones de mayor liquidez:

- **Período Donchian**: 50 (anteriormente 20) - Aumentado para reducir señales falsas
- **Stop Loss**: 150 puntos (anteriormente 50 puntos) - Ajustado críticamente para la volatilidad del oro
- **Take Profit**: 300 puntos (anteriormente 100 puntos) - Mantiene el ratio 1:2
- **Timeframe**: M5 (anteriormente M1) - Reduce el ruido del mercado
- **Horas de Trading**: 13:00-22:00 GMT (anteriormente 24/7) - Sesiones de Londres y NY para mejor liquidez

### Configuración de Seguridad Webhook

El webhook receiver ahora requiere autenticación HMAC para prevenir señales de trading no autorizadas:

- **WEBHOOK_SECRET_KEY**: Variable de entorno que debe añadirse al archivo [.env](file:///C:/Users/edgar/roboquant/.env) con una clave secreta larga y aleatoria

## Configuration

The strategy uses the following optimized parameters (can be adjusted in [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py)):

- Donchian Period: 50 (increased to reduce false signals)
- Momentum Period: 40
- Sample Period: 1000
- Lot Size: 0.01
- Stop Loss: 150 points (adjusted for gold volatility)
- Take Profit: 300 points (maintains 1:2 ratio)
- Timeframe: M5 (reduced noise, more reliable signals)
- Trading Hours: 13-22 (London and NY sessions)
- Magic Number: 234000

## Broker Setup - Exness Pro

Optimized for Exness Pro accounts:
- Account Type: Pro (ECN execution)
- Minimum Deposit: $500 (for 0.01 lot)
- Typical Spread: 1.5-2.5 pips on XAUUSD
- Free VPS with $500+ balance

Testing: Run test_complete_setup.py before live trading

## Requirements

- MetaTrader 5
- Python 3.7+
- See [requirements.txt](file:///C:/Users/edgar/roboquant/requirements.txt) for complete list of dependencies

### Key Dependencies:
- metatrader5==5.0.45
- python-dotenv==1.0.0
- pandas==2.1.0
- numpy==1.24.3
- requests==2.31.0
- flask==3.0.0
- vectorbt==0.26.0
- ta-lib==0.4.28
- plotly==5.17.0
- beautifulsoup4==4.12.2
- lxml==4.9.3
- pytz==2023.3
- xgboost==1.7.3
- keyring==24.2.0

## Installation

1. Clone this repository
2. Create a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
3. Install required packages:
   ```
   pip install -r requirements.txt
   ```
4. Install machine learning dependencies (optional):
   ```
   pip install xgboost==1.7.3
   ```
6. Install security dependencies:
   ```
   pip install keyring==24.2.0
   ```
7. Configure your MT5 credentials in the [.env](file:///C:/Users/edgar/roboquant/.env) file
8. Set up webhook security by adding a strong secret key to [.env](file:///C:/Users/edgar/roboquant/.env):
   ```
   WEBHOOK_SECRET_KEY=your_very_long_random_secret_key_here
   ```
9. Configure IP whitelisting for webhook receiver (optional):
   ```
   WEBHOOK_ALLOWED_IPS=127.0.0.1,::1,your_trusted_ip_addresses
   ```

## Usage

### Running the Strategy
Run the strategy using the batch file:
```
run_donchian.bat
```

Or run directly with Python:
```
python donchian_strategy.py
```