#!/usr/bin/env python3
"""
Simple test script to verify navigation is working
"""
import os
import sys
import uvicorn
import signal
import time
from multiprocessing import Process
import requests

def start_server():
    """Start the server with minimal configuration"""
    # Disable all heavy features
    os.environ.update({
        'STARTUP_LOGGING': 'false',
        'ENABLE_SCHEDULER': 'false',
        'TELEGRAM_BOT_ENABLED': 'false',
        'ENABLE_MARKET_STREAM': 'false',
        'TELEGRAM_BACKGROUND_TASKS_ENABLED': 'false',
        'PERFORMANCE_MONITORING_ENABLED': 'false',
        'METRICS_COLLECTION_ENABLED': 'false'
    })
    
    uvicorn.run('main:app', host='0.0.0.0', port=8000, log_level='error')

def test_navigation():
    """Test navigation endpoints"""
    base_url = "http://localhost:8000"
    
    pages = [
        ('Dashboard', '/'),
        ('Portfolio', '/portfolio'),
        ('Signals', '/signals'),
        ('Risk Monitor', '/risk-monitor'),
        ('Settings', '/settings'),
        ('Watchlist', '/watchlist'),
        ('Backtest', '/backtest'),
        ('Reports', '/reports')
    ]
    
    print("🧪 Testing navigation...")
    
    # Wait for server to start
    max_retries = 10
    for i in range(max_retries):
        try:
            response = requests.get(f"{base_url}/", timeout=5)
            if response.status_code == 200:
                print("✅ Server is ready")
                break
        except:
            print(f"⏳ Waiting for server... ({i+1}/{max_retries})")
            time.sleep(2)
    else:
        print("❌ Server failed to start")
        return False
    
    # Test each page
    all_passed = True
    for name, path in pages:
        try:
            response = requests.get(f"{base_url}{path}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {name:12} - {response.status_code}")
            else:
                print(f"❌ {name:12} - {response.status_code}")
                all_passed = False
        except Exception as e:
            print(f"❌ {name:12} - Error: {str(e)}")
            all_passed = False
    
    return all_passed

if __name__ == "__main__":
    print("🚀 Starting Navigation Test")
    
    # Start server in background
    server_process = Process(target=start_server)
    server_process.start()
    
    try:
        # Test navigation
        success = test_navigation()
        
        if success:
            print("\n🎉 All navigation tests passed!")
            print("✅ Navigation between pages is working correctly")
        else:
            print("\n⚠️  Some navigation tests failed")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    finally:
        # Clean up
        print("\n🧹 Cleaning up...")
        server_process.terminate()
        server_process.join(timeout=5)
        if server_process.is_alive():
            server_process.kill()
        print("✅ Test complete")