import logging
import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trade_scorer import TradeScorer

def test_trade_scorer():
    """Test the TradeScorer implementation"""
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    
    # Create a TradeScorer instance
    scorer = TradeScorer()
    
    # Test data (simulated)
    symbol = "XAUUSD"
    price = 1950.50
    upper_channel = 1940.00
    lower_channel = 1920.00
    current_momentum = 2.5
    historical_momentum = 1.5
    atr = 5.2
    avg_atr = 4.8
    
    # Score a trade setup
    quality = scorer.score_trade_setup(
        symbol=symbol,
        price=price,
        upper_channel=upper_channel,
        lower_channel=lower_channel,
        current_momentum=current_momentum,
        historical_momentum=historical_momentum,
        atr=atr,
        avg_atr=avg_atr
    )
    
    print(f"Trade Quality Score: {quality['score']}/100")
    print(f"Grade: {quality['grade']}")
    print(f"Trade Recommended: {quality['trade_recommended']}")
    print(f"Details: {quality['details']}")
    
    # Test another scenario with lower quality
    quality2 = scorer.score_trade_setup(
        symbol=symbol,
        price=1935.00,  # Closer to middle of channel
        upper_channel=upper_channel,
        lower_channel=lower_channel,
        current_momentum=1.2,  # Lower momentum
        historical_momentum=1.5,
        atr=3.0,  # Lower volatility
        avg_atr=4.8
    )
    
    print("\n--- Second Test ---")
    print(f"Trade Quality Score: {quality2['score']}/100")
    print(f"Grade: {quality2['grade']}")
    print(f"Trade Recommended: {quality2['trade_recommended']}")

if __name__ == "__main__":
    test_trade_scorer()