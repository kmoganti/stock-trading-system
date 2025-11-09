#!/bin/bash
# ============================================================================
# Trading System Stop Script
# ============================================================================
# This script gracefully stops the trading system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PID_FILE="$SCRIPT_DIR/.trading_system.pid"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}🛑 Stock Trading System - Stop Script${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo -e "${YELLOW}⚠️  No PID file found - system may not be running${NC}"
    echo -e "${YELLOW}   PID file: $PID_FILE${NC}"
    exit 0
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! kill -0 "$PID" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Process $PID is not running${NC}"
    echo -e "${GREEN}   Removing stale PID file${NC}"
    rm -f "$PID_FILE"
    exit 0
fi

echo -e "${BLUE}📋 Found running process (PID: $PID)${NC}"
echo ""

# Graceful shutdown
echo -e "${BLUE}🛑 Sending SIGTERM (graceful shutdown)...${NC}"
kill -TERM "$PID" 2>/dev/null || true

# Wait for process to exit
echo -e "${BLUE}⏳ Waiting for process to stop...${NC}"
WAIT_COUNT=0
MAX_WAIT=30

while kill -0 "$PID" 2>/dev/null; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo ""
        echo -e "${YELLOW}⚠️  Process did not stop gracefully after ${MAX_WAIT}s${NC}"
        echo -e "${YELLOW}   Sending SIGKILL (force kill)...${NC}"
        kill -9 "$PID" 2>/dev/null || true
        sleep 2
        break
    fi
    
    if [ $((WAIT_COUNT % 5)) -eq 0 ]; then
        echo "   Still waiting... (${WAIT_COUNT}s)"
    fi
done

# Verify process stopped
if kill -0 "$PID" 2>/dev/null; then
    echo -e "${RED}❌ Error: Failed to stop process $PID${NC}"
    echo -e "${YELLOW}   You may need to manually kill it: kill -9 $PID${NC}"
    exit 1
fi

# Remove PID file
rm -f "$PID_FILE"

echo ""
echo -e "${GREEN}✅ Trading system stopped successfully${NC}"
echo ""
echo -e "${BLUE}💡 To start again:${NC}"
echo "   ./start.sh"
echo ""
