#!/bin/bash

# Simple server startup for testing
# Uses uvicorn directly without production overhead

echo "=========================================================================="
echo "🚀 Starting Trading System Server (Testing Mode)"
echo "=========================================================================="

cd /workspaces/stock-trading-system

# Check if Redis and PostgreSQL are running
echo "📋 Checking infrastructure..."
if ! docker ps | grep -q trading_postgres; then
    echo "❌ PostgreSQL not running. Starting infrastructure..."
    ./start-infra.sh
fi

if ! docker ps | grep -q trading_redis; then
    echo "❌ Redis not running. Starting infrastructure..."
    ./start-infra.sh
fi

echo "✅ Infrastructure ready"
echo ""

# Kill any existing server
echo "🛑 Stopping existing servers..."
pkill -f "uvicorn main:app" 2>/dev/null || true
pkill -f "production_server.py" 2>/dev/null || true
sleep 2

# Start server
echo "🚀 Starting server..."
echo "   URL: http://localhost:8000"
echo "   Logs: logs/server_simple.log"
echo ""

nohup python -m uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    > logs/server_simple.log 2>&1 &

SERVER_PID=$!
echo "✅ Server started (PID: $SERVER_PID)"

# Wait for server to be ready
echo "⏳ Waiting for server to be ready..."
sleep 5

# Test health endpoint
for i in {1..10}; do
    if curl -s -f http://localhost:8000/health > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        echo ""
        echo "=========================================================================="
        echo "📊 Server Information"
        echo "=========================================================================="
        echo "   Dashboard: http://localhost:8000"
        echo "   API Docs: http://localhost:8000/docs"
        echo "   Health: http://localhost:8000/health"
        echo "   Cache Stats: http://localhost:8000/api/system/cache/stats"
        echo ""
        echo "   PID: $SERVER_PID"
        echo "   Logs: logs/server_simple.log"
        echo ""
        echo "🛠️  Management:"
        echo "   Stop: pkill -f 'uvicorn main:app'"
        echo "   Logs: tail -f logs/server_simple.log"
        echo "   Tests: ./test_production.sh"
        echo ""
        echo "🎉 Ready for testing!"
        echo "=========================================================================="
        exit 0
    fi
    echo "   Waiting... ($i/10)"
    sleep 2
done

echo "❌ Server failed to start. Check logs:"
echo "   tail -n 50 logs/server_simple.log"
exit 1
