#!/usr/bin/env python3
"""
Test signal generation for today's trading
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta
import argparse

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from models.database import init_db, get_db
from config import get_settings

async def test_signal_generation(symbols_to_test: list = None):
    """
    Backtest and debug signal generation logic for today's trading.
    This script fetches the latest market data, displays it, and then runs the
    signal generation logic to help diagnose why signals may not be generating.
    """
    print("=== Signal Generation Diagnostic Test ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize database
    await init_db()
    
    # Load settings to check filters
    settings = get_settings()
    print("--- System Settings ---")
    print(f"Min Price Filter: {settings.min_price}")
    print(f"Min Liquidity Filter: {settings.min_liquidity}")
    print("-" * 23)

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

            if symbols_to_test:
                watchlist = [s.upper() for s in symbols_to_test]
                print(f"Testing specified symbols: {', '.join(watchlist)}")
            else:
                # Test signal generation for watchlist stocks
                watchlist = await strategy_service.get_watchlist(category="day_trading")
                if not watchlist:
                    watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"] # Fallback
                print(f"Testing {len(watchlist)} stocks from 'day_trading' watchlist...")

            print("=" * 50)
            
            total_signals = 0
            
            for symbol in watchlist:
                print(f"\nAnalyzing {symbol}:")
                try:
                    # 1. Fetch recent data to show what the strategy service will be using
                    print("  Fetching latest data for analysis...")
                    to_date = datetime.now()
                    from_date = to_date - timedelta(days=90) # Fetch 90 days for indicator calculation
                    
                    # Assuming DataFetcher can return a DataFrame, which is a common pattern.
                    # If this method doesn't exist, it would need to be added to DataFetcher.
                    hist_data_df = await data_fetcher.get_historical_data_df(
                        symbol, '1D', from_date.strftime('%Y-%m-%d'), to_date.strftime('%Y-%m-%d')
                    )

                    if hist_data_df is None or hist_data_df.empty:
                        print(f"  [FAIL] Could not fetch historical data for {symbol}. Skipping.")
                        continue
                    
                    last_record = hist_data_df.iloc[-1]
                    print(f"  - Latest Close: {last_record['close']:.2f} on {last_record.name.strftime('%Y-%m-%d')}")
                    print(f"  - Latest Volume: {last_record['volume']:,.0f}")

                    # Check against system filters
                    if last_record['close'] < settings.min_price:
                        print(f"  - [FILTERED] Price {last_record['close']:.2f} is below min_price of {settings.min_price}")
                    
                    # 2. Generate signals for this symbol
                    print("  Running signal generation logic...")
                    signals = await strategy_service.generate_signals(symbol)
                    
                    if signals:
                        total_signals += len(signals)
                        print(f"  [SUCCESS] Found {len(signals)} signal(s) for {symbol}!")
                        
                        for i, signal in enumerate(signals, 1):
                            signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type
                            print(f"    -> Signal {i}: {signal_type.upper()}")
                            print(f"       Strategy: {signal.strategy}")
                            print(f"       Entry: Rs.{signal.entry_price:.2f}, SL: Rs.{signal.stop_loss:.2f}, TGT: Rs.{signal.target_price:.2f}")
                            print(f"       Confidence: {signal.confidence:.1%}")
                            
                    else:
                        print(f"  [INFO] No signals generated for {symbol}. Conditions not met.")
                        
                except Exception as e:
                    print(f"  [ERROR] An exception occurred while analyzing {symbol}: {str(e)}")
            
            print("\n" + "=" * 50)
            print(f"SUMMARY: Generated {total_signals} total signals across {len(watchlist)} stocks")
            if total_signals == 0:
                print("If no signals are generated, check strategy logic in 'services/strategy.py' against the data shown above.")
            
        else:
            print("Using mock data - update auth code in .env for live testing")
        break # Exit after one loop with the db session

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest and debug signal generation.")
    parser.add_argument(
        '--symbols', 
        nargs='+', 
        help='A list of specific stock symbols to test (e.g., RELIANCE TCS INFY). Overrides watchlist.'
    )
    args = parser.parse_args()
    asyncio.run(test_signal_generation(symbols_to_test=args.symbols))
