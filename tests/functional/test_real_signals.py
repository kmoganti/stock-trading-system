#!/usr/bin/env python3
"""
Real Trading Signal Generation with Error Handling and Timeouts
"""

import asyncio
import logging
import sys
import os
from contextlib import asynccontextmanager

sys.path.insert(0, '/workspaces/stock-trading-system')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("real_trading_signals")

async def safe_run_trading_script(script_name, timeout=45):
    """Run a trading script with timeout and error handling"""
    logger.info(f"🚀 Running {script_name}...")
    
    try:
        # Run the script with timeout
        process = await asyncio.create_subprocess_exec(
            sys.executable, f"scripts/{script_name}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/workspaces/stock-trading-system"
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), 
            timeout=timeout
        )
        
        if process.returncode == 0:
            logger.info(f"✅ {script_name} completed successfully")
            if stdout:
                logger.info(f"Output: {stdout.decode()[:500]}...")
            return True
        else:
            logger.error(f"❌ {script_name} failed with return code {process.returncode}")
            if stderr:
                logger.error(f"Error: {stderr.decode()[:500]}...")
            return False
            
    except asyncio.TimeoutError:
        logger.warning(f"⏰ {script_name} timed out after {timeout} seconds")
        try:
            process.terminate()
            await process.wait()
        except:
            pass
        return False
    except Exception as e:
        logger.error(f"❌ Error running {script_name}: {e}")
        return False

async def test_individual_components():
    """Test individual components to identify hanging issues"""
    logger.info("🔍 Testing individual components...")
    
    try:
        # Test basic imports
        logger.info("📦 Testing imports...")
        from config.settings import get_settings
        from services.iifl_api import IIFLAPIService
        logger.info("✅ Imports successful")
        
        # Test settings
        logger.info("⚙️ Testing settings...")
        settings = get_settings()
        logger.info(f"✅ Settings loaded: Environment = {settings.environment}")
        
        # Test IIFL API with timeout
        logger.info("🔐 Testing IIFL API (with timeout)...")
        iifl = IIFLAPIService()
        
        # Quick auth test
        auth_task = asyncio.create_task(iifl.authenticate())
        try:
            auth_result = await asyncio.wait_for(auth_task, timeout=15.0)
            if auth_result:
                logger.info("✅ IIFL authentication successful")
            else:
                logger.warning("⚠️ IIFL authentication failed (using mock)")
        except asyncio.TimeoutError:
            logger.warning("⏰ IIFL authentication timed out")
            auth_task.cancel()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Component test failed: {e}")
        return False

async def run_simplified_strategy_test():
    """Run a simplified strategy test without external dependencies"""
    logger.info("🎯 Running simplified strategy test...")
    
    try:
        from models.database import AsyncSessionLocal
        from services.data_fetcher import DataFetcher
        from services.strategy import StrategyService
        from services.iifl_api import IIFLAPIService
        
        iifl = IIFLAPIService()
        
        async with AsyncSessionLocal() as session:
            fetcher = DataFetcher(iifl, db_session=session)
            strategy = StrategyService(fetcher, db=session)
            
            # Test with a single symbol and short timeout
            symbol = "RELIANCE"
            logger.info(f"📈 Testing strategy for {symbol}...")
            
            # Use a very short timeout for testing
            signals = await asyncio.wait_for(
                strategy.generate_signals(symbol, category="day_trading"),
                timeout=20.0
            )
            
            logger.info(f"✅ Generated {len(signals)} signals for {symbol}")
            for signal in signals[:3]:  # Show first 3 signals
                logger.info(f"   📊 {signal.signal_type.value} @ {signal.entry_price}")
            
            return len(signals) > 0
            
    except asyncio.TimeoutError:
        logger.warning("⏰ Strategy test timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Strategy test failed: {e}")
        return False

async def main():
    """Main function to test real trading signal generation"""
    logger.info("🎯 Testing Real Trading Signal Generation")
    logger.info("=" * 50)
    
    # Test 1: Component tests
    logger.info("\n1️⃣ Testing Components...")
    component_test = await test_individual_components()
    
    if not component_test:
        logger.error("❌ Component tests failed, skipping strategy tests")
        return
    
    # Test 2: Simplified strategy test
    logger.info("\n2️⃣ Testing Strategy Generation...")
    strategy_test = await run_simplified_strategy_test()
    
    if not strategy_test:
        logger.warning("⚠️ Strategy test failed or timed out")
        logger.info("💡 The original scripts likely hang due to:")
        logger.info("   - Long-running data fetching operations")
        logger.info("   - External API timeouts")
        logger.info("   - Database connection issues")
        logger.info("   - Missing required data or dependencies")
    
    # Test 3: Try actual scripts with short timeouts
    logger.info("\n3️⃣ Testing Actual Scripts (with timeouts)...")
    scripts = [
        "run_day_trading.py",
        "run_short_selling.py", 
        "run_short_term_trading.py",
        "run_long_term_trading.py"
    ]
    
    results = {}
    for script in scripts:
        result = await safe_run_trading_script(script, timeout=30)
        results[script] = result
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 REAL SIGNAL GENERATION TEST SUMMARY")
    logger.info("=" * 50)
    logger.info(f"📦 Component Test: {'✅ PASS' if component_test else '❌ FAIL'}")
    logger.info(f"🎯 Strategy Test:  {'✅ PASS' if strategy_test else '❌ FAIL'}")
    
    for script, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL/TIMEOUT"
        logger.info(f"📄 {script:25} {status}")
    
    if any(results.values()):
        logger.info("✅ At least some real signal generation is working!")
    else:
        logger.warning("⚠️ All scripts failed/timed out - using mock signals is recommended")

if __name__ == "__main__":
    asyncio.run(main())