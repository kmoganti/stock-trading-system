#!/usr/bin/env python3
"""
Comprehensive server verification script
Tests all critical endpoints to ensure the server is functioning properly
"""

import requests
import time
import sys

BASE_URL = "http://localhost:8000"
TIMEOUT = 3

def test_endpoint(name, url, check_html=False):
    """Test a single endpoint"""
    try:
        start = time.time()
        response = requests.get(url, timeout=TIMEOUT)
        duration = time.time() - start
        
        if response.status_code == 200:
            if check_html and '<html' in response.text.lower():
                print(f"✅ {name}: OK ({duration:.2f}s)")
                return True
            elif not check_html:
                print(f"✅ {name}: OK ({duration:.2f}s)")
                return True
            else:
                print(f"❌ {name}: No HTML content")
                return False
        else:
            print(f"❌ {name}: HTTP {response.status_code}")
            return False
    except requests.exceptions.Timeout:
        print(f"❌ {name}: TIMEOUT")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ {name}: CONNECTION REFUSED")
        return False
    except Exception as e:
        print(f"❌ {name}: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Stock Trading System - Server Verification")
    print("=" * 60)
    print()
    
    results = []
    
    # Test JSON API endpoints
    print("Testing JSON API Endpoints:")
    print("-" * 40)
    results.append(test_endpoint("Health Check", f"{BASE_URL}/health"))
    results.append(test_endpoint("Test Endpoint", f"{BASE_URL}/test"))
    results.append(test_endpoint("Signals API", f"{BASE_URL}/api/signals"))
    results.append(test_endpoint("System Status", f"{BASE_URL}/api/system/status"))
    results.append(test_endpoint("Portfolio API", f"{BASE_URL}/api/portfolio/summary"))
    print()
    
    # Test HTML pages
    print("Testing HTML Pages:")
    print("-" * 40)
    results.append(test_endpoint("Homepage", f"{BASE_URL}/", check_html=True))
    results.append(test_endpoint("Signals Page", f"{BASE_URL}/signals", check_html=True))
    results.append(test_endpoint("Portfolio Page", f"{BASE_URL}/portfolio", check_html=True))
    results.append(test_endpoint("Backtest Page", f"{BASE_URL}/backtest", check_html=True))
    results.append(test_endpoint("Settings Page", f"{BASE_URL}/settings", check_html=True))
    print()
    
    # Summary
    print("=" * 60)
    total = len(results)
    passed = sum(results)
    failed = total - passed
    
    print(f"Results: {passed}/{total} passed, {failed} failed")
    
    if failed == 0:
        print("✅ All tests passed! Server is working properly.")
        sys.exit(0)
    else:
        print(f"❌ {failed} tests failed. Please check the server.")
        sys.exit(1)

if __name__ == "__main__":
    main()
