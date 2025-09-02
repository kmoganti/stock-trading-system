#!/usr/bin/env python3
"""
Test signal generation for today's trading
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService

async def test_signal_generation():
    """Test signal generation for today's trading"""
    print("=== Trading Signal Generation Test ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    strategy_service = StrategyService(data_fetcher)
    
    # Test authentication
    auth_result = await iifl_service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    
    if not iifl_service.session_token.startswith('mock_'):
        print("Using real IIFL data\n")
        
        # Test signal generation for watchlist stocks
        watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"]
        
        print("Generating signals for watchlist stocks...")
        print("=" * 50)
        
        total_signals = 0
        
        for symbol in watchlist:
            print(f"\nAnalyzing {symbol}:")
            
            try:
                # Generate signals for this symbol
                signals = await strategy_service.generate_signals(symbol)
                
                if signals:
                    total_signals += len(signals)
                    print(f"  Found {len(signals)} signal(s)")
                    
                    for i, signal in enumerate(signals, 1):
                        signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type
                        print(f"    Signal {i}: {signal_type}")
                        print(f"      Strategy: {signal.strategy}")
                        print(f"      Entry Price: Rs.{signal.entry_price:.2f}")
                        print(f"      Stop Loss: Rs.{signal.stop_loss:.2f}")
                        print(f"      Target: Rs.{signal.target_price:.2f}")
                        print(f"      Confidence: {signal.confidence:.1%}")
                        
                        # Calculate potential returns
                        if signal_type == "BUY":
                            potential_gain = ((signal.target_price - signal.entry_price) / signal.entry_price) * 100
                            potential_loss = ((signal.entry_price - signal.stop_loss) / signal.entry_price) * 100
                        else:
                            potential_gain = ((signal.entry_price - signal.target_price) / signal.entry_price) * 100
                            potential_loss = ((signal.stop_loss - signal.entry_price) / signal.entry_price) * 100
                            
                        print(f"      Potential Gain: {potential_gain:.1f}%")
                        print(f"      Potential Loss: {potential_loss:.1f}%")
                        print(f"      Risk/Reward: 1:{potential_gain/potential_loss:.1f}")
                else:
                    print(f"  No signals generated")
                    
            except Exception as e:
                print(f"  Error analyzing {symbol}: {str(e)}")
        
        print("\n" + "=" * 50)
        print(f"SUMMARY: Generated {total_signals} total signals across {len(watchlist)} stocks")
        
        if total_signals > 0:
            print("\nRECOMMENDATIONS:")
            print("1. Review each signal's risk/reward ratio")
            print("2. Check available margin for position sizing")
            print("3. Validate signals with current market conditions")
            print("4. Consider portfolio diversification")
        else:
            print("\nNo signals found - Market may be:")
            print("1. In consolidation phase")
            print("2. Lacking clear technical setups")
            print("3. Outside trading hours")
            
    else:
        print("Using mock data - update auth code in .env for live testing")

if __name__ == "__main__":
    asyncio.run(test_signal_generation())
