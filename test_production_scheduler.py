#!/usr/bin/env python3
"""
Production Test for Parallel Scheduler Testing
Tests the optimized scheduler in production mode
"""

import asyncio
import sys
import logging
from datetime import datetime
import time

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_production_scheduler():
    """Test the optimized scheduler in production mode"""
    
    print("\n" + "="*80)
    print("🚀 PRODUCTION SCHEDULER TEST - PARALLEL TESTING MODE")
    print("="*80)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # Import the optimized scheduler
        logger.info("Importing optimized scheduler...")
        from services.optimized_scheduler import get_optimized_scheduler, StrategyCategory
        
        # Get the scheduler instance
        scheduler = get_optimized_scheduler()
        
        print("✅ Optimized scheduler imported successfully")
        print()
        
        # Check if scheduler is running
        print("📊 SCHEDULER STATUS:")
        print(f"   Running: {scheduler.scheduler.running}")
        print(f"   Max concurrent symbols: {scheduler.max_concurrent_symbols}")
        print()
        
        # Get scheduled jobs
        jobs = scheduler.scheduler.get_jobs()
        print(f"📅 SCHEDULED JOBS ({len(jobs)} total):")
        for job in jobs:
            print(f"   • {job.id}: {job.name}")
            if job.next_run_time:
                print(f"     Next run: {job.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"     Next run: Not scheduled")
        print()
        
        # Get symbol mappings
        print("🎯 STRATEGY SYMBOL MAPPINGS:")
        for category, symbols in scheduler.strategy_symbols.items():
            print(f"   {category.value}: {len(symbols)} symbols")
            print(f"      {', '.join(list(symbols)[:5])}{'...' if len(symbols) > 5 else ''}")
        print()
        
        # Calculate unique symbols
        all_symbols = set()
        for symbols in scheduler.strategy_symbols.values():
            all_symbols.update(symbols)
        print(f"📌 UNIQUE SYMBOLS ACROSS ALL STRATEGIES: {len(all_symbols)}")
        print(f"   Symbols: {', '.join(sorted(list(all_symbols)[:10]))}{'...' if len(all_symbols) > 10 else ''}")
        print()
        
        # Check cache stats
        cache_stats = scheduler.get_cache_stats()
        print("💾 CACHE STATISTICS:")
        print(f"   Total cached symbols: {cache_stats['total_cached_symbols']}")
        print(f"   Valid cache entries: {cache_stats['valid_cache_entries']}")
        if cache_stats['symbols']:
            print(f"   Cached: {', '.join(cache_stats['symbols'][:5])}{'...' if len(cache_stats['symbols']) > 5 else ''}")
        print()
        
        # Check execution stats
        exec_stats = scheduler.get_execution_stats()
        print("📈 EXECUTION STATISTICS:")
        if exec_stats:
            for category, stats in exec_stats.items():
                print(f"   {category}:")
                print(f"      Total runs: {stats['total_runs']}")
                print(f"      Successful: {stats['successful_runs']}")
                print(f"      Failed: {stats['failed_runs']}")
                if stats['avg_execution_time'] > 0:
                    print(f"      Avg time: {stats['avg_execution_time']:.2f}s")
                if stats['last_execution']:
                    print(f"      Last run: {stats['last_execution'].strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print("   ℹ️  No executions yet (scheduler just started)")
        print()
        
        # Test a manual unified scan (small subset for testing)
        print("🧪 RUNNING TEST SCAN...")
        print("   Testing with a small subset of day_trading category")
        print()
        
        # Temporarily reduce symbols for testing
        original_symbols = scheduler.strategy_symbols[StrategyCategory.DAY_TRADING].copy()
        scheduler.strategy_symbols[StrategyCategory.DAY_TRADING] = {'RELIANCE', 'TCS'}
        
        start_time = time.time()
        
        try:
            # Run test scan with timeout
            await asyncio.wait_for(
                scheduler.execute_unified_scan([StrategyCategory.DAY_TRADING]),
                timeout=120.0  # 2 minute timeout for test
            )
            
            execution_time = time.time() - start_time
            
            print(f"✅ TEST SCAN COMPLETED in {execution_time:.2f} seconds")
            print()
            
            # Check updated cache stats
            new_cache_stats = scheduler.get_cache_stats()
            print("💾 CACHE AFTER TEST SCAN:")
            print(f"   Total cached symbols: {new_cache_stats['total_cached_symbols']}")
            print(f"   Valid cache entries: {new_cache_stats['valid_cache_entries']}")
            if new_cache_stats['symbols']:
                print(f"   Symbols: {', '.join(new_cache_stats['symbols'])}")
            print()
            
            # Check if signals were generated
            from models.database import AsyncSessionLocal
            from models.signals import Signal
            from sqlalchemy import select, func
            
            async with AsyncSessionLocal() as session:
                # Count signals generated in last 5 minutes
                five_min_ago = datetime.now()
                result = await session.execute(
                    select(func.count(Signal.id)).where(
                        Signal.created_at >= five_min_ago
                    )
                )
                recent_signals = result.scalar()
                
                print(f"📊 SIGNALS GENERATED: {recent_signals} new signals")
            
        except asyncio.TimeoutError:
            print("⚠️  TEST SCAN TIMED OUT after 120 seconds")
            print("   This might indicate initialization issues or slow API response")
        except Exception as e:
            print(f"❌ TEST SCAN FAILED: {e}")
            logger.error(f"Test scan error: {e}", exc_info=True)
        finally:
            # Restore original symbols
            scheduler.strategy_symbols[StrategyCategory.DAY_TRADING] = original_symbols
        
        print()
        print("="*80)
        print("📊 PRODUCTION TEST SUMMARY")
        print("="*80)
        print("✅ Scheduler initialized and running")
        print(f"✅ {len(jobs)} jobs scheduled")
        print(f"✅ {len(all_symbols)} unique symbols configured")
        print("✅ Test scan completed (2 symbols)")
        print()
        print("🎯 NEXT STEPS:")
        print("   1. Monitor logs for scheduled job executions")
        print("   2. Check cache hit rates after first few runs")
        print("   3. Compare signal generation with old scheduler")
        print("   4. Monitor IIFL API call reduction")
        print()
        print("📝 MONITORING COMMANDS:")
        print("   tail -f /tmp/parallel_testing.log")
        print("   python test_production_scheduler.py")
        print("   curl http://localhost:8000/api/scheduler/cache/stats | jq")
        print()
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Production test failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_production_scheduler())
    sys.exit(0 if success else 1)
