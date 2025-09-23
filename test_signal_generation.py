#!/usr/bin/env python3
"""
Test signal generation for today's trading
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
import argparse
from typing import Optional, Dict
import logging

# Optional deps
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False
try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from models.database import init_db, get_db
from config import get_settings

logger = logging.getLogger(__name__)

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
                    # 1. Generate signals for this symbol
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
    try:
        asyncio.run(test_signal_generation(symbols_to_test=args.symbols))
    except KeyboardInterrupt:
        print("\n[INFO] Script interrupted by user. Exiting.")
        sys.exit(0)
