# Heuristics Implementation Summary

This document summarizes the implementation of the trade scoring system and related heuristic components added to the RoboQuant trading system.

## Overview

The implementation includes a comprehensive trade quality scoring system with 5 heuristics, plus additional optional components for enhanced trading decision making.

## Components Implemented

### 1. Trade Scorer (`trade_scorer.py`)

A complete implementation of a trade quality scoring system that evaluates trade setups on a 0-100 point scale using 5 heuristics:

#### Heuristics Breakdown:

1. **Breakout Strength (25 points)**
   - Measures the strength of the breakout relative to the channel width
   - >15% breakout: 25 points
   - 10-15% breakout: 20 points
   - 5-10% breakout: 15 points
   - 2-5% breakout: 10 points
   - <2% breakout: 0 points

2. **Momentum Ratio (25 points)**
   - Compares current momentum to historical momentum
   - >1.5 ratio: 25 points
   - 1.2-1.5 ratio: 20 points
   - 1.0-1.2 ratio: 15 points
   - 0.8-1.0 ratio: 10 points
   - <0.8 ratio: 0 points

3. **Time Session (20 points)**
   - Evaluates if the trade is occurring during optimal trading sessions
   - Best sessions (7-10h, 13-16h UTC): 20 points
   - Good sessions: 10 points
   - Other sessions: 0 points

4. **ATR Volatility (15 points)**
   - Assesses volatility using Average True Range
   - Optimal volatility (1.0-1.5 ATR ratio): 15 points
   - Acceptable volatility (0.8-2.0): 10 points
   - Moderate volatility (0.5-2.5): 5 points
   - Extreme volatility: 0 points

5. **Spread (15 points)**
   - Evaluates current market spread conditions
   - Excellent spread (<20 points): 15 points
   - Good spread (20-30 points): 12 points
   - Acceptable spread (30-50 points): 8 points
   - High spread (50-100 points): 4 points
   - Very high spread (>100 points): 0 points

#### Integration with Donchian Strategy

The trade scorer has been integrated into [donchian_strategy.py](file:///C:/Users/edgar/roboquant/donchian_strategy.py) with the following logic:

```python
if bullish_breakout:
    quality = TradeScorer().score_trade_setup(...)
    
    if quality['score'] < 60: 
        return
        
    # Adjust risk by quality
    risk_mult = 1.5 if score >= 80 else 1.0 if score >= 70 else 0.75
    lots = LOTS * risk_mult
    execute_trade(lots)
```

### 2. Market Regime Detector (`market_regime.py`)

Detects market regime (trending/ranging) using ADX and slope analysis:

- **TRENDING**: High ADX (>25) + significant slope
- **RANGING**: Low ADX (<20)
- **TRANSITION**: Between the two

### 3. Adaptive Risk Manager (`adaptive_risk.py`)

Implements dynamic risk management with:

- Dynamic SL/TP calculation based on ATR
- Position size adjustment based on volatility
- Risk/reward ratio maintenance

### 4. Session Filter (`session_filter.py`)

Filters trades based on historical performance by session:

- ASIAN: 00:00-07:00 UTC
- EUROPEAN: 07:00-15:00 UTC
- AMERICAN: 13:00-21:00 UTC
- OVERLAP: 07:00-10:00 UTC (London/NY overlap)
- LATE_NY: 20:00-23:00 UTC

## Testing

Comprehensive tests have been created for all components:

1. `test_trade_scorer.py` - Tests the trade scoring system
2. `test_session_filter.py` - Tests the session filter component
3. `test_heuristics_integration.py` - Tests the integration of all components

## Key Benefits

1. **Improved Trade Quality**: Only high-quality trades (score ≥ 60) are executed
2. **Adaptive Position Sizing**: Position size is adjusted based on trade quality
3. **Market Context Awareness**: Trading decisions consider market regime and session performance
4. **Dynamic Risk Management**: SL/TP levels adapt to current market volatility
5. **Data-Driven Decisions**: All heuristics are based on quantitative analysis

## Usage Examples

### Trade Scoring
```python
scorer = TradeScorer()
quality = scorer.score_trade_setup(
    symbol="XAUUSD",
    price=1950.50,
    upper_channel=1940.00,
    lower_channel=1920.00,
    current_momentum=2.5,
    historical_momentum=1.5,
    atr=5.2,
    avg_atr=4.8
)
# Returns: {'score': 73, 'grade': 'C', 'trade_recommended': True, 'details': {...}}
```

### Market Regime Detection
```python
regime, adx, slope = market_regime_detector.detect_regime("XAUUSD")
# Returns: ("TRENDING", 28.5, 0.15)
```

### Adaptive Risk Management
```python
sl, tp = adaptive_risk_manager.calculate_dynamic_stops(
    symbol="XAUUSD",
    entry_price=1950.0,
    order_type="BUY",
    atr=5.2,
    risk_reward_ratio=2.0
)
# Returns dynamic stop loss and take profit levels
```

### Session Filtering
```python
is_favorable, confidence = session_filter.is_favorable_session("XAUUSD")
# Returns: (True, 0.75) if current session is favorable
```

## Future Enhancements

Potential future enhancements could include:

1. Machine learning-based optimization of heuristic weights
2. Additional heuristics based on economic calendar events
3. Real-time adjustment of scoring thresholds based on market conditions
4. Integration with sentiment analysis from news sources
5. Advanced pattern recognition for breakout confirmation