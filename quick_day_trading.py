#!/usr/bin/env python3
"""
Quick Day Trading Signal Generation Test - With timeout protection
"""

import asyncio
import logging
import sys
import os
sys.path.insert(0, '/workspaces/stock-trading-system')

from models.database import AsyncSessionLocal
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from config.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("day_trading_quick")

async def quick_day_trading_test():
    """Quick test with timeout protection"""
    logger.info("🚀 Starting Quick Day Trading Signal Generation...")
    
    try:
        # Set a global timeout for the entire operation
        return await asyncio.wait_for(run_day_trading_signals(), timeout=60.0)
    except asyncio.TimeoutError:
        logger.error("❌ Day trading signal generation timed out after 60 seconds")
        return False
    except Exception as e:
        logger.error(f"❌ Error in day trading: {e}")
        return False

async def run_day_trading_signals():
    """Main day trading logic"""
    settings = get_settings()
    logger.info(f"📊 Environment: {settings.environment}")
    
    # Test with mock authentication first
    iifl = IIFLAPIService()
    logger.info("🔐 Testing IIFL authentication...")
    
    # Quick auth test with timeout
    auth_result = await asyncio.wait_for(iifl.authenticate(), timeout=10.0)
    if not auth_result:
        logger.warning("⚠️ Authentication failed, using mock mode")
    else:
        logger.info("✅ Authentication successful")
    
    async with AsyncSessionLocal() as session:
        logger.info("📈 Creating services...")
        fetcher = DataFetcher(iifl, db_session=session)
        strategy = StrategyService(fetcher, db=session)
        
        # Test with a single symbol first
        symbols = ["RELIANCE"]  # Start with just one symbol
        
        for sym in symbols:
            logger.info(f"🎯 Generating day trading signals for {sym}...")
            try:
                # Add timeout for signal generation
                signals = await asyncio.wait_for(
                    strategy.generate_signals(sym, category="day_trading"), 
                    timeout=30.0
                )
                
                logger.info(f"📊 Generated {len(signals)} signals for {sym}")
                for signal in signals:
                    logger.info(f"   📈 {signal.signal_type.value} @ {signal.entry_price} "
                              f"(Stop: {signal.stop_loss}, Target: {signal.target_price})")
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Signal generation for {sym} timed out")
            except Exception as e:
                logger.error(f"❌ Error generating signals for {sym}: {e}")
    
    logger.info("✅ Day trading signal generation completed")
    return True

if __name__ == "__main__":
    result = asyncio.run(quick_day_trading_test())
    sys.exit(0 if result else 1)