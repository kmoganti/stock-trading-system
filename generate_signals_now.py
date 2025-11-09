#!/usr/bin/env python3
"""
Manual Signal Generation for Today's Trading
Generates buy/sell signals for approval via Telegram
"""

import asyncio
import sys
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def generate_signals_now():
    """Generate trading signals immediately"""
    
    print("\n" + "="*80)
    print("🚀 MANUAL SIGNAL GENERATION")
    print("="*80)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Import required modules
        from services.iifl_api import IIFLAPIService
        from services.data_fetcher import DataFetcher
        from services.strategy import StrategyService
        
        logger.info("Initializing services...")
        
        # Initialize
        iifl_api = IIFLAPIService()
        data_fetcher = DataFetcher(iifl_api)
        strategy_service = StrategyService(data_fetcher)
        
        # Authenticate
        logger.info("Authenticating...")
        auth = await asyncio.wait_for(iifl_api.authenticate(), timeout=15.0)
        
        if not auth or "error" in str(auth):
            print(f"❌ Authentication failed")
            return False
        
        print("✅ Authenticated\n")
        
        # List of symbols to analyze
        symbols = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ITC"]
        
        print(f"📊 Generating signals for {len(symbols)} symbols...")
        print(f"   Symbols: {', '.join(symbols)}\n")
        
        total_signals = 0
        
        for symbol in symbols:
            print(f"🔍 Analyzing {symbol}...")
            
            try:
                signals = await asyncio.wait_for(
                    strategy_service.generate_signals(
                        symbol=symbol,
                        category="day_trading",
                        strategy_name=None
                    ),
                    timeout=30.0
                )
                
                if signals and len(signals) > 0:
                    print(f"   ✅ {len(signals)} signal(s) generated")
                    for sig in signals:
                        print(f"      • {sig.get('signal_type')} @ ₹{sig.get('entry_price', 0):.2f}")
                    total_signals += len(signals)
                else:
                    print(f"   ⚠️  No signals (conditions not met)")
                    
            except asyncio.TimeoutError:
                print(f"   ⏱️  Timeout analyzing {symbol}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        
        print(f"\n{'='*80}")
        print(f"📊 SUMMARY")
        print(f"{'='*80}")
        print(f"Total signals generated: {total_signals}")
        
        if total_signals > 0:
            print(f"\n✅ SUCCESS! {total_signals} signals ready for approval")
            print(f"\n📱 CHECK TELEGRAM:")
            print(f"   Bot: @AuraTrader_KK_Bot")
            print(f"   Action: Click 'Approve' to execute orders")
            print(f"\n🌐 OR CHECK WEB:")
            print(f"   URL: http://localhost:8000/signals")
        else:
            print(f"\n⚠️  No signals generated - market conditions not favorable")
            print(f"   This is normal - the system only generates signals when")
            print(f"   technical indicators meet strict criteria")
        
        print()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(generate_signals_now())
    sys.exit(0 if success else 1)
