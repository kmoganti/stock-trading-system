#!/bin/bash
# ============================================================================
# Trading System Status Check Script
# ============================================================================
# This script checks the status of all services and displays health info

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/.trading_system.pid"
LOG_DIR="$SCRIPT_DIR/logs"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Load port from .env if available
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | grep '^PORT=' | xargs) 2>/dev/null || true
fi
PORT=${PORT:-8000}
SERVER_URL="http://localhost:$PORT"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}📊 Stock Trading System - Status Check${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${RED}❌ System Status: NOT RUNNING${NC}"
    echo -e "${YELLOW}   No PID file found: $PID_FILE${NC}"
    echo ""
    echo -e "${BLUE}💡 To start the system:${NC}"
    echo "   ./start.sh"
    echo ""
    exit 1
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}❌ System Status: NOT RUNNING${NC}"
    echo -e "${YELLOW}   PID file exists but process $PID is not running${NC}"
    echo -e "${YELLOW}   (Stale PID file)${NC}"
    echo ""
    echo -e "${BLUE}💡 Clean up and restart:${NC}"
    echo "   rm $PID_FILE"
    echo "   ./start.sh"
    echo ""
    exit 1
fi

echo -e "${GREEN}✅ System Status: RUNNING${NC}"
echo -e "${BLUE}   PID: $PID${NC}"
echo ""

# Get process info
PS_INFO=$(ps -p "$PID" -o pid,ppid,%cpu,%mem,etime,cmd --no-headers | sed 's/^/   /')
echo -e "${BLUE}📋 Process Information:${NC}"
echo "$PS_INFO"
echo ""

# Check health endpoint
echo -e "${BLUE}🔍 Health Check:${NC}"
if HEALTH_RESPONSE=$(curl -s -f "$SERVER_URL/health" 2>&1); then
    echo -e "${GREEN}   ✅ Server responding${NC}"
    echo "   URL: $SERVER_URL"
    echo "   Response: $(echo $HEALTH_RESPONSE | jq -r '.status' 2>/dev/null || echo $HEALTH_RESPONSE)"
else
    echo -e "${RED}   ❌ Health check failed${NC}"
    echo -e "${YELLOW}   Server may still be starting up or there's a network issue${NC}"
fi
echo ""

# Check system status endpoint
echo -e "${BLUE}⚙️  System Status:${NC}"
if STATUS_RESPONSE=$(curl -s -f "$SERVER_URL/api/system/status" 2>&1); then
    # Parse key fields
    AUTO_TRADE=$(echo $STATUS_RESPONSE | jq -r '.auto_trade' 2>/dev/null || echo "unknown")
    IIFL_CONNECTED=$(echo $STATUS_RESPONSE | jq -r '.iifl_api_connected' 2>/dev/null || echo "unknown")
    DB_CONNECTED=$(echo $STATUS_RESPONSE | jq -r '.database_connected' 2>/dev/null || echo "unknown")
    
    if [ "$AUTO_TRADE" = "true" ]; then
        echo -e "   🟢 Auto Trade: ${GREEN}ENABLED${NC}"
    else
        echo -e "   🔴 Auto Trade: ${YELLOW}DISABLED${NC}"
    fi
    
    if [ "$IIFL_CONNECTED" = "true" ]; then
        echo -e "   ✅ IIFL API: ${GREEN}CONNECTED${NC}"
    else
        echo -e "   ❌ IIFL API: ${RED}DISCONNECTED${NC}"
    fi
    
    if [ "$DB_CONNECTED" = "true" ]; then
        echo -e "   ✅ Database: ${GREEN}CONNECTED${NC}"
    else
        echo -e "   ❌ Database: ${RED}DISCONNECTED${NC}"
    fi
else
    echo -e "${RED}   ❌ Could not fetch system status${NC}"
fi
echo ""

# Check log files
echo -e "${BLUE}📝 Log Files:${NC}"
if [ -d "$LOG_DIR" ]; then
    for log in "$LOG_DIR"/*.log; do
        if [ -f "$log" ]; then
            SIZE=$(du -h "$log" | cut -f1)
            MODIFIED=$(stat -c %y "$log" 2>/dev/null | cut -d'.' -f1 || stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "$log" 2>/dev/null)
            echo "   $(basename $log): $SIZE (modified: $MODIFIED)"
        fi
    done
else
    echo -e "${YELLOW}   No log directory found${NC}"
fi
echo ""

# Show recent errors from logs
if [ -f "$LOG_DIR/trading_system.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR" "$LOG_DIR/trading_system.log" 2>/dev/null || echo 0)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        echo -e "${YELLOW}⚠️  Recent Errors: $ERROR_COUNT errors found in logs${NC}"
        echo -e "${BLUE}   Last 5 errors:${NC}"
        grep "ERROR" "$LOG_DIR/trading_system.log" | tail -5 | sed 's/^/   /' || true
    else
        echo -e "${GREEN}✅ No recent errors in logs${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Main log file not found${NC}"
fi
echo ""

# Management commands
echo -e "${BLUE}🛠️  Management Commands:${NC}"
echo "   Stop:    ./stop.sh"
echo "   Restart: ./restart.sh"
echo "   Logs:    tail -f $LOG_DIR/trading_system.log"
echo ""

# Quick access URLs
echo -e "${BLUE}🌐 Quick Access:${NC}"
echo "   Dashboard:   $SERVER_URL/"
echo "   API Docs:    $SERVER_URL/docs"
echo "   Health:      $SERVER_URL/health"
echo "   Status API:  $SERVER_URL/api/system/status"
echo ""

echo -e "${BLUE}============================================================================${NC}"
