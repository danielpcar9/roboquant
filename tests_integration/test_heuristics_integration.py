import logging
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from analysis.trade_scorer import TradeScorer
from core.market_regime import market_regime_detector
from risk.adaptive_risk import adaptive_risk_manager
from core.session_filter import session_filter

def test_heuristics_integration():
    """Test the integration of all heuristic components"""
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    
    print("=== Testing Heuristics Integration ===\n")
    
    # 1. Test Trade Scorer
    print("1. Testing Trade Scorer")
    scorer = TradeScorer()
    
    # High quality trade setup
    quality1 = scorer.score_trade_setup(
        symbol="XAUUSD",
        price=1950.50,
        upper_channel=1940.00,
        lower_channel=1920.00,
        current_momentum=2.5,
        historical_momentum=1.5,
        atr=5.2,
        avg_atr=4.8
    )
    
    print(f"   High quality trade score: {quality1['score']}/100 (Grade: {quality1['grade']})")
    print(f"   Trade recommended: {quality1['trade_recommended']}")
    
    # Low quality trade setup
    quality2 = scorer.score_trade_setup(
        symbol="XAUUSD",
        price=1935.00,  # Closer to middle of channel
        upper_channel=1940.00,
        lower_channel=1920.00,
        current_momentum=1.2,  # Lower momentum
        historical_momentum=1.5,
        atr=3.0,  # Lower volatility
        avg_atr=4.8
    )
    
    print(f"   Low quality trade score: {quality2['score']}/100 (Grade: {quality2['grade']})")
    print(f"   Trade recommended: {quality2['trade_recommended']}\n")
    
    # 2. Test Market Regime Detector
    print("2. Testing Market Regime Detector")
    # Note: This would require MT5 connection in real usage
    current_session = session_filter.get_current_session()
    print(f"   Current trading session: {current_session}")
    
    is_favorable, confidence = session_filter.is_favorable_session("XAUUSD")
    print(f"   Session favorable: {is_favorable} (confidence: {confidence:.2f})\n")
    
    # 3. Test Adaptive Risk Manager
    print("3. Testing Adaptive Risk Manager")
    
    # Calculate dynamic stops
    sl, tp = adaptive_risk_manager.calculate_dynamic_stops(
        symbol="XAUUSD",
        entry_price=1950.0,
        order_type="BUY",
        atr=5.2,
        risk_reward_ratio=2.0
    )
    
    print(f"   Dynamic stops for BUY order: SL={sl:.2f}, TP={tp:.2f}")
    
    # Adjust position size by volatility
    base_lots = 0.1
    adjusted_lots = adaptive_risk_manager.adjust_position_size_by_volatility(
        base_lots=base_lots,
        atr=5.2,
        avg_atr=4.8
    )
    
    print(f"   Position size adjustment: {base_lots:.2f} -> {adjusted_lots:.2f}\n")
    
    # 4. Combined decision making
    print("4. Combined Decision Making Example")
    
    # Only trade if:
    # 1. Trade quality score >= 70
    # 2. Current session is favorable
    # 3. Market regime is trending (if we had real data)
    
    if quality1['score'] >= 70 and is_favorable:
        print("   ✅ ALL CONDITIONS MET - EXECUTE TRADE")
        print(f"      - Quality Score: {quality1['score']}/100")
        print(f"      - Session: {current_session} (favorable)")
        print(f"      - Adjusted Position Size: {adjusted_lots:.2f} lots")
        print(f"      - Dynamic Stops: SL={sl:.2f}, TP={tp:.2f}")
    else:
        print("   ❌ CONDITIONS NOT MET - SKIP TRADE")
        if quality1['score'] < 70:
            print(f"      - Quality Score too low: {quality1['score']}/100")
        if not is_favorable:
            print(f"      - Session not favorable: {current_session}")

if __name__ == "__main__":
    test_heuristics_integration()