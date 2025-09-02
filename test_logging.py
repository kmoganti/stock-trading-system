#!/usr/bin/env python3
"""
Test script to verify logging functionality
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.logging_service import trading_logger
from services.iifl_api import IIFLAPIService
from config.settings import get_settings

async def test_logging():
    """Test all logging functionality"""
    print("Testing logging functionality...")
    
    # Test system event logging
    print("1. Testing system event logging...")
    trading_logger.log_system_event("test_startup", {"test": True, "version": "1.0.0"})
    
    # Test trade logging
    print("2. Testing trade logging...")
    trading_logger.log_trade("TEST001", "BUY", "RELIANCE", 10, 2500.50, {"test": True})
    
    # Test risk event logging
    print("3. Testing risk event logging...")
    trading_logger.log_risk_event("POSITION_LIMIT", "HIGH", "Test risk event", {"test": True})
    
    # Test API call logging
    print("4. Testing API call logging...")
    trading_logger.log_api_call("https://test.api.com/endpoint", "POST", 200, 0.5)
    trading_logger.log_api_call("https://test.api.com/error", "GET", 500, 1.2, "Server Error")
    
    # Test error logging
    print("5. Testing error logging...")
    try:
        raise ValueError("Test error for logging")
    except Exception as e:
        trading_logger.log_error("test_component", e, {"test": True})
    
    # Test IIFL API logging (authentication only - won't make real calls)
    print("6. Testing IIFL API logging...")
    try:
        iifl_service = IIFLAPIService()
        # This will trigger authentication logging
        await iifl_service.authenticate()
    except Exception as e:
        print(f"IIFL test completed (expected): {e}")
    
    print("\nLogging test completed!")
    print("Check the following log files:")
    
    log_dir = Path("logs")
    for log_file in log_dir.glob("*.log"):
        size = log_file.stat().st_size
        print(f"  - {log_file}: {size} bytes")

def check_log_files():
    """Check if log files exist and have content"""
    log_dir = Path("logs")
    
    if not log_dir.exists():
        print("❌ Logs directory does not exist!")
        return False
    
    expected_logs = [
        "trading_system.log",
        "api_calls.log", 
        "trades.log",
        "risk_events.log",
        "errors.log"
    ]
    
    all_good = True
    for log_name in expected_logs:
        log_path = log_dir / log_name
        if log_path.exists():
            size = log_path.stat().st_size
            print(f"[OK] {log_name}: {size} bytes")
        else:
            print(f"[MISSING] {log_name}: Missing!")
            all_good = False
    
    return all_good

if __name__ == "__main__":
    print("=== Logging System Test ===\n")
    
    # Check initial state
    print("Initial log file status:")
    check_log_files()
    print()
    
    # Run logging tests
    asyncio.run(test_logging())
    
    print("\nFinal log file status:")
    check_log_files()
