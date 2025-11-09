#!/bin/bash
# Monitor scheduler execution and detect hangs

LOG_FILE="/workspaces/stock-trading-system/logs/strategy.log"
ALERT_THRESHOLD=600  # Alert if scan takes more than 10 minutes

echo "=========================================="
echo "Scheduler Monitoring Dashboard"
echo "=========================================="
echo "Current time: $(date)"
echo ""

# Check if server is running
SERVER_PID=$(ps aux | grep -E "python.*uvicorn.*main:app" | grep -v grep | awk '{print $2}' | head -1)
if [ -z "$SERVER_PID" ]; then
    echo "❌ Server is NOT running"
    exit 1
else
    echo "✅ Server running (PID: $SERVER_PID)"
fi

# Check last heartbeat
LAST_LOG=$(tail -1 "$LOG_FILE" 2>/dev/null)
if [ -z "$LAST_LOG" ]; then
    echo "⚠️  No scheduler logs found"
else
    LAST_TIME=$(echo "$LAST_LOG" | jq -r .timestamp 2>/dev/null)
    echo "📝 Last scheduler log: $LAST_TIME"
fi

echo ""
echo "📅 Scheduled Jobs:"
echo "─────────────────────────────────────────"

# Parse next run times from logs
grep "Next run at" "$LOG_FILE" 2>/dev/null | tail -4 | while IFS= read -r line; do
    JOB=$(echo "$line" | jq -r .message 2>/dev/null || echo "$line")
    echo "$JOB"
done

echo ""
echo "🔍 Recent Scan Activity (last 10):"
echo "─────────────────────────────────────────"

# Show recent scan executions
grep -E "Starting unified|completed|failed|TIMEOUT" "$LOG_FILE" 2>/dev/null | tail -10 | while IFS= read -r line; do
    TIMESTAMP=$(echo "$line" | jq -r .timestamp 2>/dev/null | cut -c12-19)
    MESSAGE=$(echo "$line" | jq -r .message 2>/dev/null || echo "$line")
    echo "[$TIMESTAMP] $MESSAGE"
done

echo ""
echo "⚠️  Errors/Warnings (last 5):"
echo "─────────────────────────────────────────"

# Show recent errors
grep -E "ERROR|WARNING|TIMEOUT" "$LOG_FILE" 2>/dev/null | tail -5 | while IFS= read -r line; do
    TIMESTAMP=$(echo "$line" | jq -r .timestamp 2>/dev/null | cut -c12-19)
    MESSAGE=$(echo "$line" | jq -r .message 2>/dev/null || echo "$line")
    echo "[$TIMESTAMP] $MESSAGE"
done

echo ""
echo "🎯 Current Execution Status:"
echo "─────────────────────────────────────────"

# Check if a scan is currently running
RUNNING_SCAN=$(grep -E "Starting unified" "$LOG_FILE" 2>/dev/null | tail -1)
COMPLETED_SCAN=$(grep -E "completed|failed|TIMEOUT" "$LOG_FILE" 2>/dev/null | tail -1)

if [ -n "$RUNNING_SCAN" ]; then
    RUNNING_TIME=$(echo "$RUNNING_SCAN" | jq -r .timestamp 2>/dev/null)
    COMPLETED_TIME=$(echo "$COMPLETED_SCAN" | jq -r .timestamp 2>/dev/null)
    
    if [[ "$RUNNING_TIME" > "$COMPLETED_TIME" ]]; then
        echo "🏃 SCAN IN PROGRESS (started at $RUNNING_TIME)"
        
        # Calculate duration
        START_EPOCH=$(date -d "$RUNNING_TIME" +%s 2>/dev/null)
        NOW_EPOCH=$(date +%s)
        DURATION=$((NOW_EPOCH - START_EPOCH))
        
        echo "   Duration: ${DURATION}s"
        
        if [ $DURATION -gt $ALERT_THRESHOLD ]; then
            echo "   ⚠️  WARNING: Scan running longer than ${ALERT_THRESHOLD}s!"
        fi
    else
        echo "✅ No active scans"
    fi
else
    echo "✅ No active scans"
fi

echo ""
echo "🔄 Server Health:"
echo "─────────────────────────────────────────"

# Test server responsiveness
HEALTH_STATUS=$(timeout 3 curl -s http://localhost:8000/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "✅ Server responding to health checks"
else
    echo "❌ Server NOT responding (timeout after 3s)"
fi

# Check CPU and memory
CPU=$(ps -p $SERVER_PID -o %cpu --no-headers 2>/dev/null | tr -d ' ')
MEM=$(ps -p $SERVER_PID -o rss --no-headers 2>/dev/null)
MEM_MB=$((MEM / 1024))

echo "   CPU: ${CPU}%"
echo "   Memory: ${MEM_MB}MB"

# Check PostgreSQL connections
PG_CONNECTIONS=$(docker exec trading_postgres psql -U trading_user -d trading_system -t -c "SELECT count(*) FROM pg_stat_activity WHERE datname='trading_system';" 2>/dev/null | tr -d ' ')
if [ -n "$PG_CONNECTIONS" ]; then
    echo "   PostgreSQL connections: $PG_CONNECTIONS/100"
fi

echo ""
echo "=========================================="
echo "Monitoring complete at $(date)"
echo "=========================================="
