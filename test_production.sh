#!/bin/bash

# Production Testing Script
# Tests all major components of the trading system

# Don't exit on error - we want to see all test results
# set -e

echo "=========================================================================="
echo "🧪 Stock Trading System - Production Tests"
echo "=========================================================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

test_result() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $1"
        ((PASS++))
    else
        echo -e "${RED}❌ FAIL${NC}: $1"
        ((FAIL++))
    fi
}

# Test 1: Infrastructure Running
echo "Test 1: Checking infrastructure..."
docker ps | grep -q trading_postgres && docker ps | grep -q trading_redis
test_result "Docker containers running"

# Test 2: Server Health
echo "Test 2: Checking server health..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
[ "$HEALTH" = "200" ]
test_result "Server health endpoint"

# Test 3: Redis Connection
echo "Test 3: Checking Redis cache..."
CACHE_STATUS=$(curl -s http://localhost:8000/api/system/cache/stats | python -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
[ "$CACHE_STATUS" = "connected" ]
test_result "Redis cache connected"

# Test 4: System Status
echo "Test 4: Checking system status..."
curl -s http://localhost:8000/api/system/status | grep -q '"database_connected":true'
test_result "Database connected"

# Test 5: API Documentation
echo "Test 5: Checking API docs..."
DOCS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs)
[ "$DOCS" = "200" ]
test_result "API documentation accessible"

# Test 6: Dashboard
echo "Test 6: Checking web dashboard..."
DASHBOARD=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
[ "$DASHBOARD" = "200" ]
test_result "Dashboard accessible"

# Test 7: Watchlist Endpoint
echo "Test 7: Testing watchlist endpoint..."
curl -s http://localhost:8000/api/watchlist > /dev/null
test_result "Watchlist endpoint responds"

# Test 8: Cache Performance
echo "Test 8: Testing cache performance..."
START=$(date +%s%N)
curl -s http://localhost:8000/api/watchlist > /dev/null
END=$(date +%s%N)
FIRST_CALL=$((($END - $START) / 1000000))

START=$(date +%s%N)
curl -s http://localhost:8000/api/watchlist > /dev/null
END=$(date +%s%N)
SECOND_CALL=$((($END - $START) / 1000000))

echo -e "   First call: ${FIRST_CALL}ms"
echo -e "   Second call: ${SECOND_CALL}ms"

# Second call should be faster (cache hit)
[ $SECOND_CALL -lt $FIRST_CALL ]
test_result "Cache improves performance"

# Test 9: Load Test (20 concurrent requests)
echo "Test 9: Load testing (20 concurrent requests)..."
SUCCESS=0
for i in {1..20}; do
    (curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health | grep -q "200" && ((SUCCESS++))) &
done
wait
[ $SUCCESS -eq 20 ]
test_result "Handle 20 concurrent requests"

# Test 10: Server Still Responsive After Load
echo "Test 10: Checking server after load..."
sleep 2
HEALTH_AFTER=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health)
[ "$HEALTH_AFTER" = "200" ]
test_result "Server responsive after load test"

# Test 11: Cache Stats
echo "Test 11: Checking cache statistics..."
CACHE_HITS=$(curl -s http://localhost:8000/api/system/cache/stats | python -c "import sys, json; print(json.load(sys.stdin)['hits'])" 2>/dev/null)
[ "$CACHE_HITS" -ge 0 ]
test_result "Cache statistics available"

# Test 12: Authentication Status
echo "Test 12: Checking IIFL authentication..."
AUTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/auth/status)
if [ "$AUTH_STATUS" = "200" ]; then
    AUTH_RESULT=$(curl -s http://localhost:8000/api/auth/status | python -c "import sys, json; print(json.load(sys.stdin).get('authenticated', False))" 2>/dev/null)
    if [ "$AUTH_RESULT" = "True" ]; then
        test_result "IIFL authentication successful"
    else
        echo -e "${YELLOW}⚠️  WARNING${NC}: IIFL not authenticated (update IIFL_AUTH_CODE in .env)"
        ((FAIL++))
    fi
else
    echo -e "${YELLOW}⚠️  WARNING${NC}: Auth endpoint not responding"
    ((FAIL++))
fi

# Test 13: PostgreSQL Connection
echo "Test 13: Testing PostgreSQL connection..."
docker exec trading_postgres psql -U trading_user -d trading_system -c "SELECT 1;" > /dev/null 2>&1
test_result "PostgreSQL connection"

# Test 14: Redis Connection
echo "Test 14: Testing Redis connection..."
docker exec trading_redis redis-cli ping > /dev/null 2>&1
test_result "Redis connection"

# Test 15: Database Schema
echo "Test 15: Checking database schema..."
TABLES=$(docker exec trading_postgres psql -U trading_user -d trading_system -c "\dt" 2>/dev/null | grep -c "watchlist\|signals\|settings")
[ "$TABLES" -ge 3 ]
test_result "Database tables exist"

echo ""
echo "=========================================================================="
echo "📊 Test Results Summary"
echo "=========================================================================="
echo -e "${GREEN}✅ Passed: $PASS${NC}"
echo -e "${RED}❌ Failed: $FAIL${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! System is ready for production.${NC}"
    echo ""
    echo "Next Steps:"
    echo "1. Access dashboard: http://localhost:8000"
    echo "2. Monitor logs: tail -f logs/trading_system.log"
    echo "3. Check cache stats: curl http://localhost:8000/api/system/cache/stats"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  Some tests failed. Please check the issues above.${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check logs: tail -n 100 logs/startup.log"
    echo "2. Restart infrastructure: ./stop-infra.sh && ./start-infra.sh"
    echo "3. Restart server: ./restart.sh"
    echo "4. Update IIFL auth code in .env if authentication failed"
    echo ""
    exit 1
fi
