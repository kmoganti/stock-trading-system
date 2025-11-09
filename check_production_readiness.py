#!/usr/bin/env python3
"""
Production Readiness Check - Verify both schedulers are running
"""

import requests
import json
from datetime import datetime
import time

print("\n" + "="*80)
print("🚀 PRODUCTION READINESS CHECK - PARALLEL SCHEDULER TESTING")
print("="*80)
print(f"Check started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

base_url = "http://localhost:8000"

def test_endpoint(url, name, timeout=5):
    """Test an API endpoint"""
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            print(f"✅ {name}: PASS")
            return response.json()
        else:
            print(f"❌ {name}: FAIL (Status: {response.status_code})")
            return None
    except requests.exceptions.Timeout:
        print(f"⏱️  {name}: TIMEOUT")
        return None
    except Exception as e:
        print(f"❌ {name}: ERROR - {e}")
        return None

# 1. Health Check
print("📋 BASIC HEALTH CHECKS:")
print("-" * 80)
health = test_endpoint(f"{base_url}/health", "Server Health")
print()

# 2. Check Signals
print("📊 DATA CHECKS:")
print("-" * 80)
signals = test_endpoint(f"{base_url}/api/signals", "Signals API")
if signals:
    print(f"   Total signals in database: {len(signals)}")
print()

# 3. Check Logs for Scheduler Startup
print("🔍 SCHEDULER STARTUP VERIFICATION:")
print("-" * 80)
try:
    with open('/tmp/production_test.log', 'r') as f:
        log_content = f.read()
        
    if 'OLD trading strategy scheduler started successfully' in log_content:
        print("✅ OLD Scheduler: Started")
    else:
        print("❌ OLD Scheduler: Not found in logs")
    
    if 'OPTIMIZED trading strategy scheduler started successfully' in log_content:
        print("✅ OPTIMIZED Scheduler: Started")
    else:
        print("❌ OPTIMIZED Scheduler: Not found in logs")
        
    if 'PARALLEL TESTING MODE: Both schedulers active' in log_content:
        print("✅ Parallel Testing Mode: ACTIVE")
    else:
        print("❌ Parallel Testing Mode: Not confirmed")
    
    print()
    
    # Extract timing info
    import re
    old_match = re.search(r'🚀 \[STARTUP\] ([\d.]+)s - OLD trading strategy scheduler started', log_content)
    new_match = re.search(r'🚀 \[STARTUP\] ([\d.]+)s - OPTIMIZED trading strategy scheduler started', log_content)
    
    if old_match and new_match:
        print(f"⏱️  OLD Scheduler started at: {old_match.group(1)}s")
        print(f"⏱️  OPTIMIZED Scheduler started at: {new_match.group(1)}s")
        print()
    
except FileNotFoundError:
    print("⚠️  Log file not found: /tmp/production_test.log")
    print()

# 4. Database Signal Stats
print("📈 DATABASE STATISTICS:")
print("-" * 80)
try:
    import sqlite3
    conn = sqlite3.connect('trading_system.db')
    cursor = conn.cursor()
    
    # Count signals by category
    cursor.execute("""
        SELECT category, COUNT(*) as count 
        FROM signals 
        GROUP BY category 
        ORDER BY count DESC
    """)
    results = cursor.fetchall()
    
    if results:
        print("Signal counts by category:")
        total = 0
        for category, count in results:
            print(f"   • {category}: {count} signals")
            total += count
        print(f"   TOTAL: {total} signals")
    else:
        print("   No signals found in database")
    
    conn.close()
    print()
    
except Exception as e:
    print(f"❌ Database check failed: {e}")
    print()

# 5. Production Summary
print("="*80)
print("📊 PRODUCTION SUMMARY")
print("="*80)

checks_passed = 0
total_checks = 5

if health:
    checks_passed += 1
    print("✅ Server is running and healthy")
else:
    print("❌ Server health check failed")

if signals is not None:
    checks_passed += 1
    print(f"✅ Signals API working ({len(signals)} signals)")
else:
    print("❌ Signals API failed")

try:
    with open('/tmp/production_test.log', 'r') as f:
        log = f.read()
    if 'OLD trading strategy scheduler started successfully' in log:
        checks_passed += 1
        print("✅ OLD Scheduler confirmed running")
    else:
        print("❌ OLD Scheduler not confirmed")
        
    if 'OPTIMIZED trading strategy scheduler started successfully' in log:
        checks_passed += 1
        print("✅ OPTIMIZED Scheduler confirmed running")
    else:
        print("❌ OPTIMIZED Scheduler not confirmed")
        
    if 'PARALLEL TESTING MODE' in log:
        checks_passed += 1
        print("✅ Parallel testing mode active")
    else:
        print("❌ Parallel testing mode not confirmed")
except:
    pass

print()
print(f"🎯 OVERALL SCORE: {checks_passed}/{total_checks} checks passed")
print()

if checks_passed == total_checks:
    print("🎉 ALL CHECKS PASSED - Production ready for parallel testing!")
    print()
    print("📅 Next Steps:")
    print("   1. Monitor scheduler executions over next 24 hours")
    print("   2. Compare signal generation between schedulers")
    print("   3. Track API call rates and cache hit ratios")
    print("   4. Verify 50%+ reduction in API calls")
    exit(0)
elif checks_passed >= 3:
    print("⚠️  MOSTLY READY - Some issues detected but core functionality working")
    exit(0)
else:
    print("❌ NOT READY - Critical issues detected")
    exit(1)
