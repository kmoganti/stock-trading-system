#!/usr/bin/env python3
"""
Prepare System for Buy/Sell Order Execution Today

This script:
1. Generates signals for a specific symbol
2. Creates buy signal (if conditions met)
3. Creates sell signal (if position exists)
4. Allows approval via Telegram for execution
"""

import asyncio
import sys
import logging
from datetime import datetime, timedelta
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def generate_test_signals():
    """Generate signals for today's trading"""
    
    print("\n" + "="*80)
    print("🎯 PREPARING SYSTEM FOR BUY/SELL ORDER EXECUTION")
    print("="*80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Import required services
        from services.iifl_api import IIFLAPIService
        from services.data_fetcher import DataFetcher
        from services.strategy import StrategyService
        from models.database import AsyncSessionLocal
        from models.signals import Signal, SignalStatus
        from sqlalchemy import select, func
        
        logger.info("Initializing services...")
        
        # Initialize services
        iifl_api = IIFLAPIService()
        data_fetcher = DataFetcher(iifl_api)
        strategy_service = StrategyService(data_fetcher)
        
        # Authenticate
        logger.info("Authenticating with IIFL API...")
        auth_result = await asyncio.wait_for(
            iifl_api.authenticate(),
            timeout=15.0
        )
        
        if not auth_result or "error" in str(auth_result):
            print(f"❌ Authentication failed: {auth_result}")
            return False
        
        print("✅ IIFL API authenticated successfully\n")
        
        # Get current portfolio to check positions
        logger.info("Fetching current portfolio...")
        portfolio = await asyncio.wait_for(
            data_fetcher.get_portfolio_data(force_refresh=True),
            timeout=10.0
        )
        
        print("📊 CURRENT PORTFOLIO:")
        if portfolio and len(portfolio) > 0:
            print(f"   Active positions: {len(portfolio)}")
            for position in portfolio[:5]:  # Show first 5
                print(f"   • {position.get('TradingSymbol', 'N/A')}: {position.get('BuyQty', 0)} @ ₹{position.get('BuyAvgPrice', 0)}")
        else:
            print("   No active positions")
        print()
        
        # Choose symbol for testing
        test_symbol = "RELIANCE"  # High liquidity, good for testing
        
        print(f"🎯 GENERATING SIGNALS FOR: {test_symbol}")
        print(f"   Category: day_trading")
        print(f"   Purpose: Generate BUY signal if conditions met\n")
        
        # Generate signals for day trading
        logger.info(f"Generating day trading signals for {test_symbol}...")
        signals = await asyncio.wait_for(
            strategy_service.generate_signals(
                symbol=test_symbol,
                category="day_trading",
                strategy_name=None
            ),
            timeout=60.0
        )
        
        if signals and len(signals) > 0:
            print(f"✅ SIGNALS GENERATED: {len(signals)} signal(s)")
            for signal in signals:
                print(f"   • Type: {signal.get('signal_type', 'N/A')}")
                print(f"     Entry: ₹{signal.get('entry_price', 0):.2f}")
                print(f"     Target: ₹{signal.get('target_price', 0):.2f}")
                print(f"     Stop Loss: ₹{signal.get('stop_loss', 0):.2f}")
                print(f"     Confidence: {signal.get('confidence', 0):.2f}")
        else:
            print(f"⚠️  No signals generated (conditions not met)")
            print(f"   This is normal - signals only generate when technical conditions are favorable\n")
        
        # Check database for pending signals
        async with AsyncSessionLocal() as session:
            # Get pending signals from today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            result = await session.execute(
                select(Signal).where(
                    Signal.status == SignalStatus.PENDING,
                    Signal.created_at >= today_start
                ).order_by(Signal.created_at.desc()).limit(10)
            )
            pending_signals = result.scalars().all()
            
            print("\n📋 PENDING SIGNALS (Awaiting Approval):")
            if pending_signals:
                for sig in pending_signals:
                    print(f"   • ID: {sig.id} | {sig.symbol} | {sig.signal_type} | ₹{sig.entry_price:.2f}")
                    print(f"     Created: {sig.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"\n   Total pending: {len(pending_signals)} signal(s)")
            else:
                print("   No pending signals")
        
        print("\n" + "="*80)
        print("📱 NEXT STEPS FOR ORDER EXECUTION")
        print("="*80)
        print()
        print("1. ✅ Check Telegram bot for signal notifications")
        print("   Bot: @AuraTrader_KK_Bot")
        print()
        print("2. 🔘 Click 'Approve' button on the signal you want to trade")
        print()
        print("3. 🚀 System will execute the order automatically:")
        print("   • Validates signal parameters")
        print("   • Checks risk limits")
        print("   • Places order via IIFL API")
        print("   • Monitors execution")
        print()
        print("4. 📊 Monitor position:")
        print("   • Check /portfolio page")
        print("   • View active orders")
        print("   • Track P&L")
        print()
        print("💡 TO GENERATE MORE SIGNALS:")
        print("   python prepare_orders.py")
        print()
        print("📊 TO CHECK CURRENT SIGNALS:")
        print("   curl http://localhost:8000/api/signals | jq '.[] | {id, symbol, signal_type, status}'")
        print()
        print("🔄 SCHEDULER STATUS:")
        print("   The optimized scheduler is running and will generate signals automatically")
        print("   according to configured strategies (day trading, short term, etc.)")
        print()
        
        return True
        
    except asyncio.TimeoutError:
        logger.error("❌ Operation timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return False

async def check_system_readiness():
    """Check if system is ready for order execution"""
    
    print("\n📋 SYSTEM READINESS CHECK")
    print("-" * 80)
    
    checks_passed = 0
    total_checks = 5
    
    # 1. Check server is running
    try:
        import requests
        response = requests.get("http://localhost:8000/health", timeout=3)
        if response.status_code == 200:
            print("✅ Server is running")
            checks_passed += 1
        else:
            print("❌ Server not responding correctly")
    except Exception as e:
        print(f"❌ Server not accessible: {e}")
    
    # 2. Check IIFL authentication
    try:
        from services.iifl_api import IIFLAPIService
        iifl = IIFLAPIService()
        auth = await asyncio.wait_for(iifl.authenticate(), timeout=10.0)
        if auth and "error" not in str(auth):
            print("✅ IIFL API authenticated")
            checks_passed += 1
        else:
            print(f"❌ IIFL authentication failed: {auth}")
    except Exception as e:
        print(f"❌ IIFL authentication error: {e}")
    
    # 3. Check Telegram bot
    import os
    if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
        print("✅ Telegram bot configured")
        checks_passed += 1
    else:
        print("⚠️  Telegram bot not configured (optional)")
        checks_passed += 0.5  # Partial credit
    
    # 4. Check DRY_RUN mode
    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    if not dry_run:
        print("✅ DRY_RUN disabled - LIVE TRADING ENABLED")
        checks_passed += 1
    else:
        print("⚠️  DRY_RUN enabled - Only paper trading")
    
    # 5. Check database
    try:
        from models.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
        print("✅ Database accessible")
        checks_passed += 1
    except Exception as e:
        print(f"❌ Database error: {e}")
    
    print(f"\n🎯 READINESS SCORE: {checks_passed}/{total_checks}")
    
    if checks_passed >= 4:
        print("✅ System is READY for order execution!")
        return True
    else:
        print("⚠️  System not fully ready - address issues above")
        return False

if __name__ == "__main__":
    async def main():
        # Check readiness first
        ready = await check_system_readiness()
        
        if not ready:
            print("\n⚠️  Fix readiness issues before generating signals")
            sys.exit(1)
        
        # Generate signals
        success = await generate_test_signals()
        
        sys.exit(0 if success else 1)
    
    asyncio.run(main())
