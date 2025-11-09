#!/usr/bin/env python3
"""Quick test of approval endpoint in TEST_MODE"""

import os
import asyncio
import httpx
from datetime import datetime, timedelta
from models.database import AsyncSessionLocal
from models.signals import Signal, SignalType, SignalStatus
from sqlalchemy import select

# Set TEST_MODE before importing FastAPI app
os.environ["TEST_MODE"] = "true"

async def test_approval():
    """Test signal approval flow"""
    
    # Create a test signal
    print("Creating test signal...")
    async with AsyncSessionLocal() as session:
        signal = Signal(
            symbol="TEST",
            signal_type=SignalType.BUY,
            price=100.0,
            quantity=1,
            stop_loss=95.0,
            take_profit=110.0,
            margin_required=100.0,
            status=SignalStatus.PENDING,
            expiry_time=datetime.now() + timedelta(hours=1)
        )
        session.add(signal)
        await session.commit()
        await session.refresh(signal)
        signal_id = signal.id
        print(f"✅ Created signal #{signal_id}")
    
    # Test approval via direct function call (bypass HTTP)
    print(f"\nTesting direct approval of signal #{signal_id}...")
    from api.signals import approve_signal
    from models.database import get_db
    
    # Create a mock API key dependency
    async def mock_get_api_key():
        return "test-key"
    
    # Get DB session
    async for db in get_db():
        try:
            result = await approve_signal(
                signal_id=signal_id,
                api_key="test-key",
                db=db
            )
            print(f"✅ Approval result: {result}")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Verify signal status
    print(f"\nVerifying signal #{signal_id} status...")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Signal).where(Signal.id == signal_id)
        )
        signal = result.scalar_one()
        print(f"Status: {signal.status}")
        print(f"Approved at: {signal.approved_at}")
        
        if signal.status == SignalStatus.APPROVED:
            print("✅ TEST PASSED: Signal was approved!")
        else:
            print("❌ TEST FAILED: Signal not approved")

if __name__ == "__main__":
    asyncio.run(test_approval())
