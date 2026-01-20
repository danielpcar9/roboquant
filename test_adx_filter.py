"""Quick ADX Filter Test"""
import MetaTrader5 as mt5
from core.market_regime import market_regime_detector

# Initialize MT5
mt5.initialize()

# Test current market regime
regime, adx, slope = market_regime_detector.detect_regime('XAUUSD', adx_period=14, adx_threshold=18)

print('\n' + '='*50)
print('CURRENT MARKET STATUS - XAUUSD')
print('='*50)
print(f'ADX Value: {adx:.2f}')
print(f'Slope: {slope:.4f}')
print(f'Regime: {regime}')
print('ADX Threshold: 18')
print('='*50)

if regime == 'TRENDING':
    print('\n✅ TRADING ALLOWED')
    print(f'   Market is TRENDING (ADX {adx:.2f} > 18)')
    print('   Strategy will execute trades normally')
else:
    print('\n❌ TRADING BLOCKED')
    print(f'   Market is RANGING (ADX {adx:.2f} < 18)')
    print('   Strategy will skip trades to avoid false breakouts')

# Get current price
tick = mt5.symbol_info_tick('XAUUSD')
if tick:
    print('\nCurrent Price:')
    print(f'   BID: {tick.bid:.2f}')
    print(f'   ASK: {tick.ask:.2f}')

print('\n' + '='*50 + '\n')

mt5.shutdown()
