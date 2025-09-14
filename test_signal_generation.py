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
from models.database import init_db, get_db

async def test_signal_generation():
    """Test signal generation for today's trading"""
    print("=== Trading Signal Generation Test ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize database
    await init_db()

    # Get DB session and run tests
    async for db in get_db():
        # Initialize services
        iifl_service = IIFLAPIService()
        data_fetcher = DataFetcher(iifl_service, db_session=db)
        strategy_service = StrategyService(data_fetcher, db)
        
        # Test authentication
        auth_result = await iifl_service.authenticate()
        print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
        
        if not iifl_service.session_token.startswith('mock_'):
            print("Using real IIFL data\n")
            
            # Test signal generation for watchlist stocks
            watchlist = await strategy_service.get_watchlist(category="day_trading")
            if not watchlist:
                watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"] # Fallback
            
            print(f"Generating signals for {len(watchlist)} stocks in 'day_trading' watchlist...")
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
                            
                    else:
                        print(f"  No signals generated")
                        
                except Exception as e:
                    print(f"  Error analyzing {symbol}: {str(e)}")
            
            print("\n" + "=" * 50)
            print(f"SUMMARY: Generated {total_signals} total signals across {len(watchlist)} stocks")
            
        else:
            print("Using mock data - update auth code in .env for live testing")
        break # Exit after one loop with the db session

if __name__ == "__main__":
    asyncio.run(test_signal_generation())
