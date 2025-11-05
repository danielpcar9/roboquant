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
- [forex_factory_scraper.py](file://c:\Users\edgar\roboquant\forex_factory_scraper.py) - Economic calendar scraper for event detection
- [api_cache.py](file://c:\Users\edgar\roboquant\api_cache.py) - Caching system for API responses
- [config_manager.py](file://c:\Users\edgar\roboquant\config_manager.py) - Centralized configuration management
- [run_donchian.bat](file://c:\Users\edgar\roboquant\run_donchian.bat) - Batch file to run the strategy on Windows
- [run_webhook.bat](file://c:\Users\edgar\roboquant\run_webhook.bat) - Batch file to run the webhook receiver
- [run_backtest.bat](file://c:\Users\edgar\roboquant\run_backtest.bat) - Batch file to run backtesting
- [test_mt5_connection.py](file://c:\Users\edgar\roboquant\test_mt5_connection.py) - Script to test MT5 connection
- [test_security.py](file://c:\Users\edgar\roboquant\test_security.py) - Test script for security components
- [test_post_mortem.py](file://c:\Users\edgar\roboquant\test_post_mortem.py) - Test script for post-trade analysis
- [test_forex_factory_scraper.py](file://c:\Users\edgar\roboquant\test_forex_factory_scraper.py) - Test script for economic calendar scraper

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

## Event-Driven Trading Improvements

### Robust Economic Calendar Integration
- Enhanced Forex Factory scraper with better error handling
- Improved caching system with TTL support
- Better parsing of calendar events with timezone handling

### Event State Management
- Enhanced state machine for event detection and trading
- Better tracking of event-related trades
- Improved cooldown periods between event trades

## Configuration Management

### Centralized Configuration
- All configuration parameters are now managed through a centralized config manager
- Easy parameter adjustment through environment variables
- Secure credential management through the same interface

## Testing Improvements

### Comprehensive Test Coverage
- Added unit tests for post-trade analysis module
- Added unit tests for economic calendar scraper
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

## Event Detection System

The bot uses Forex Factory's economic calendar to detect high-impact events:
- Automatically scrapes upcoming events every 30 minutes
- No API key required (web scraping with caching)
- Filters for High Impact events only
- Respects rate limits with intelligent caching

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
4. Install web scraping dependencies:
   ```
   pip install beautifulsoup4==4.12.2 lxml==4.9.3 pytz==2023.3
   ```
5. Install machine learning dependencies (optional):
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

### Webhook Receiver
To receive external trading signals:
```
run_webhook.bat
```

Or run directly:
```
python webhook_receiver.py
```

### Backtesting
To run backtesting:
```
run_backtest.bat
```

Or run directly:
```
python backtest_apex_vectorbt.py
```

### Performance Dashboard
To generate a performance dashboard:
```
python performance_dashboard.py
```

### Post-Trade Analysis
To generate a detailed performance report:
```
python post_mortem.py
```

## Webhook Security

The webhook receiver implements HMAC authentication to prevent unauthorized trading signals:

### For Signal Senders:
```python
import hmac
import hashlib
import json
import requests

# Your secret key from .env
SECRET_KEY = "your_secret_key_here"

# Signal data
body = json.dumps({"symbol": "XAUUSD", "order_type": "BUY"})

# Calculate signature
signature = hmac.new(
    SECRET_KEY.encode(), 
    body.encode(), 
    hashlib.sha256
).hexdigest()

# Send request with signature
headers = {"X-Webhook-Signature": signature}
response = requests.post("http://your-server:5000/webhook", data=body, headers=headers)
```

## How It Works

1. The strategy calculates Donchian channels (highest high and lowest low over the specified period)
2. It calculates momentum as the average absolute price movement over two periods
3. When the current price breaks above the upper channel AND momentum is higher than historical average, it enters a long position
4. When the current price breaks below the lower channel AND momentum is higher than historical average, it enters a short position
5. Positions are managed with fixed stop loss and take profit levels

## Security Features

This strategy now includes enhanced security features:

### Secure Credential Management
- Credentials are loaded securely from [.env](file:///C:/Users/edgar/roboquant/.env) without exposing them in logs
- Automatic validation of webhook secret key length (>32 characters)
- Encrypted credential storage using keyring library

### Input Validation
- Symbol validation with regex patterns
- Volume and price validation with reasonable limits
- Order type validation (BUY/SELL only)

### Rate Limiting
- Webhook receiver limits requests to 10 per minute
- Prevents abuse and denial of service attacks
- Enhanced rate limiting with global and per-IP tracking

### Error Sanitization
- Sensitive information is removed from error messages
- Constant-time signature comparison prevents timing attacks

### Circuit Breaker Pattern
- Prevents cascading failures during MT5 connection issues
- Automatic recovery after timeout periods

### IP Whitelisting
- Webhook receiver supports IP whitelisting for enhanced security
- Configure allowed IPs via WEBHOOK_ALLOWED_IPS environment variable

## Machine Learning Integration

The system includes a machine learning engine for enhanced trading signals:

### Feature Engineering
- RSI, MACD, ATR, Donchian channels, and other technical indicators
- Comprehensive feature set for market analysis

### XGBoost Model
- Gradient boosting model for pattern recognition
- Hybrid approach combining technical and ML signals (70/30 ratio)

### Gradual Rollout
- First logs predictions for monitoring
- Then validates with paper trading
- Finally enables live trading after validation

## Backtesting

The backtesting script uses VectorBT to simulate trading performance with proper exit conditions based on stop loss and take profit levels.

## Performance Monitoring

The performance dashboard generates interactive HTML visualizations including:
- Equity curve
- Drawdown analysis
- Win/loss distribution
- Hourly trading patterns
- Monthly performance
- Profit factor evolution

## Post-Trade Analysis

The post-mortem module provides comprehensive trade analysis:
- Detailed performance metrics (Sharpe ratio, Sortino ratio, Calmar ratio)
- Time-based performance analysis
- Best and worst performing hours
- Maximum drawdown and consecutive loss tracking

## Testing

### Security Testing
To test the security components:
```
python test_security.py
```

This test validates:
- Secure credential loading
- Input validation
- Rate limiting
- Error sanitization
- Constant-time comparison

### Post-Trade Analysis Testing
To test the post-mortem components:
```
python test_post_mortem.py
```

This test validates:
- Trade logging functionality
- Performance metrics calculation
- Report generation

### Economic Calendar Scraper Testing
To test the Forex Factory scraper:
```
python test_forex_factory_scraper.py
```

This test validates:
- Event fetching functionality
- Caching system
- Error handling

## Disclaimer

This is a educational example and should not be used for live trading without proper testing and risk management.