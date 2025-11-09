#!/bin/bash
# ============================================================================
# Trading System Startup Script
# ============================================================================
# This script starts the trading system with Telegram bot and market stream
# enabled. It loads environment variables from .env and manages the process.

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Configuration
PID_FILE="$SCRIPT_DIR/.trading_system.pid"
LOG_DIR="$SCRIPT_DIR/logs"
STARTUP_LOG="$LOG_DIR/startup.log"
MAIN_LOG="$LOG_DIR/trading_system.log"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}🚀 Stock Trading System - Startup Script${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Check if already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if kill -0 "$OLD_PID" 2>/dev/null; then
        echo -e "${YELLOW}⚠️  Trading system is already running (PID: $OLD_PID)${NC}"
        echo -e "${YELLOW}   Use ./stop.sh to stop it first, or ./restart.sh to restart${NC}"
        exit 1
    else
        echo -e "${YELLOW}⚠️  Found stale PID file, removing...${NC}"
        rm -f "$PID_FILE"
    fi
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found${NC}"
    echo -e "${YELLOW}   Please create .env file with required configuration${NC}"
    echo -e "${YELLOW}   Copy from .env.example if needed: cp .env.example .env${NC}"
    exit 1
fi

# Backup .env before starting
BACKUP_ENV=".env.backup.$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP_ENV"
echo -e "${GREEN}✅ Created backup: $BACKUP_ENV${NC}"

# Load environment variables
echo -e "${BLUE}📋 Loading environment variables...${NC}"
# Read .env file line by line, handling quotes and special characters properly
while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "$line" ]] && continue
    
    # Only process valid variable assignments
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
        # Remove inline comments (but preserve quoted strings)
        line=$(echo "$line" | sed 's/[[:space:]]*#.*$//')
        # Export the variable
        export "$line"
    fi
done < .env

# SAFE_MODE allows running the server without full broker/DB readiness
SAFE_MODE_NORMALIZED="$(echo "${SAFE_MODE:-false}" | tr '[:upper:]' '[:lower:]')"

# Verify critical environment variables unless SAFE_MODE=true
if [ "$SAFE_MODE_NORMALIZED" != "true" ]; then
    REQUIRED_VARS=(
        "IIFL_CLIENT_ID"
        "IIFL_AUTH_CODE"
        "IIFL_APP_SECRET"
    )

    MISSING_VARS=()
    for var in "${REQUIRED_VARS[@]}"; do
        if [ -z "${!var}" ]; then
            MISSING_VARS+=("$var")
        fi
    done

    if [ ${#MISSING_VARS[@]} -gt 0 ]; then
        echo -e "${RED}❌ Error: Missing required environment variables:${NC}"
        for var in "${MISSING_VARS[@]}"; do
            echo -e "${RED}   - $var${NC}"
        done
        echo ""
        echo -e "${YELLOW}   Please update your .env file with these variables or set SAFE_MODE=true to bypass this check${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️  SAFE_MODE=true - skipping strict env validation for broker credentials${NC}"
fi

# Check optional but recommended variables
if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo -e "${YELLOW}⚠️  Warning: Telegram bot credentials not set${NC}"
    echo -e "${YELLOW}   Bot notifications will be disabled${NC}"
fi

# Display configuration summary
echo ""
echo -e "${BLUE}⚙️  Configuration Summary:${NC}"
echo "   Environment: ${ENVIRONMENT:-production}"
echo "   Port: ${PORT:-8000}"
echo "   Auto Trade: ${AUTO_TRADE:-false}"
echo "   Dry Run: ${DRY_RUN:-true}"
echo "   Market Stream: ${ENABLE_MARKET_STREAM:-false}"
echo "   Telegram Bot: ${TELEGRAM_BOT_ENABLED:-false}"
echo "   Scheduler: ${ENABLE_SCHEDULER:-true}"
echo ""

# In SAFE_MODE, prefer the simple server to avoid strict production checks
if [ "$SAFE_MODE_NORMALIZED" = "true" ]; then
    export USE_SIMPLE_SERVER="true"
    # Also ensure production server won't abort on failed checks if used
    export STRICT_STARTUP_CHECKS="false"
    echo -e "${YELLOW}ℹ️  SAFE_MODE=true - forcing USE_SIMPLE_SERVER=true and STRICT_STARTUP_CHECKS=false${NC}"
fi

# Prefer PostgreSQL automatically if available or if DATABASE_URL is not set
if [ -z "$DATABASE_URL" ] || [[ "$DATABASE_URL" == sqlite* ]]; then
    echo -e "${BLUE}🔎 Checking for local PostgreSQL to auto-wire DATABASE_URL...${NC}"
    # Try common local ports 5432 then 5433 using bash /dev/tcp (no netcat dependency)
    if timeout 1 bash -c '>/dev/tcp/127.0.0.1/5432' 2>/dev/null; then
        export DATABASE_URL="postgresql+asyncpg://trading_user:trading_secure_password_2025@localhost:5432/trading_system"
        echo -e "${GREEN}✅ Using PostgreSQL at localhost:5432${NC}"
    elif timeout 1 bash -c '>/dev/tcp/127.0.0.1/5433' 2>/dev/null; then
        export DATABASE_URL="postgresql+asyncpg://trading_user:trading_secure_password_2025@localhost:5433/trading_system"
        echo -e "${GREEN}✅ Using PostgreSQL at localhost:5433${NC}"
    else
        echo -e "${YELLOW}⚠️  No local PostgreSQL detected; continuing with DATABASE_URL='${DATABASE_URL:-sqlite}'${NC}"
    fi
fi

echo -e "${BLUE}🗄️  Database URL in use:${NC} ${DATABASE_URL:-<not set>}"

# Safety check for production
if [ "${AUTO_TRADE}" = "true" ] && [ "${DRY_RUN}" = "false" ]; then
    echo -e "${RED}⚠️  WARNING: LIVE TRADING MODE ENABLED${NC}"
    echo -e "${RED}   AUTO_TRADE=true and DRY_RUN=false${NC}"
    echo -e "${YELLOW}   This will place REAL orders with REAL money!${NC}"
    echo ""
    read -p "   Are you sure you want to continue? (type 'YES' to confirm): " confirm
    if [ "$confirm" != "YES" ]; then
        echo -e "${YELLOW}   Startup cancelled by user${NC}"
        exit 0
    fi
fi

# Start the trading system
echo -e "${BLUE}🚀 Starting trading system...${NC}"
echo ""

# Preflight: ensure desired port is free
PORT_TO_USE="${PORT:-8000}"
echo -e "${BLUE}🔎 Checking for processes already listening on port ${PORT_TO_USE}...${NC}"
if command -v lsof >/dev/null 2>&1; then
    CONFLICT_PIDS=$(lsof -t -iTCP:${PORT_TO_USE} -sTCP:LISTEN || true)
    if [ -n "${CONFLICT_PIDS}" ]; then
        echo -e "${YELLOW}⚠️  Port ${PORT_TO_USE} is in use by the following process(es):${NC}"
        lsof -nP -iTCP:${PORT_TO_USE} -sTCP:LISTEN || true
        echo -e "${YELLOW}   Attempting to stop conflicting process(es) gracefully...${NC}"
        for pid in ${CONFLICT_PIDS}; do
            kill -TERM "$pid" 2>/dev/null || true
        done
        # Wait briefly for processes to exit
        sleep 2
        # Re-check
        CONFLICT_PIDS=$(lsof -t -iTCP:${PORT_TO_USE} -sTCP:LISTEN || true)
        if [ -n "${CONFLICT_PIDS}" ]; then
            echo -e "${YELLOW}⚠️  Processes still holding port ${PORT_TO_USE}. Forcing termination...${NC}"
            for pid in ${CONFLICT_PIDS}; do
                kill -9 "$pid" 2>/dev/null || true
            done
            sleep 1
        fi
        # Final check
        if lsof -t -iTCP:${PORT_TO_USE} -sTCP:LISTEN >/dev/null 2>&1; then
            echo -e "${RED}❌ Unable to free port ${PORT_TO_USE}. Please stop the process using the port and retry.${NC}"
            exit 1
        else
            echo -e "${GREEN}✅ Port ${PORT_TO_USE} is now free${NC}"
        fi
    else
        echo -e "${GREEN}✅ Port ${PORT_TO_USE} is free${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  lsof not available; skipping port preflight check${NC}"
fi

# Choose startup method based on availability or override
if [ "${USE_SIMPLE_SERVER}" = "true" ] || [ ! -f "production/production_server.py" ]; then
    echo -e "${GREEN}   Using uvicorn directly${NC}"
    nohup python -m uvicorn main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}" >> "$STARTUP_LOG" 2>&1 &
    SERVER_PID=$!
else
    echo -e "${GREEN}   Using production server runner${NC}"
    nohup python production/production_server.py >> "$STARTUP_LOG" 2>&1 &
    SERVER_PID=$!
fi

# Save PID
echo $SERVER_PID > "$PID_FILE"

echo -e "${GREEN}✅ Trading system started (PID: $SERVER_PID)${NC}"
echo ""

# Wait a moment for startup
echo -e "${BLUE}⏳ Waiting for server initialization...${NC}"
sleep 3

# Check if process is still running
if ! kill -0 "$SERVER_PID" 2>/dev/null; then
    echo -e "${RED}❌ Error: Server process died immediately after startup${NC}"
    echo -e "${YELLOW}   Check logs for details:${NC}"
    echo -e "${YELLOW}   tail -n 50 $STARTUP_LOG${NC}"
    rm -f "$PID_FILE"
    exit 1
fi

# Verify server health
echo -e "${BLUE}🔍 Checking server health...${NC}"
MAX_RETRIES=5
RETRY_COUNT=0
SERVER_URL="http://localhost:${PORT:-8000}"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Use timeout to prevent hanging (2 second timeout per attempt)
    if timeout 2 curl -s -f "$SERVER_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Server is healthy and responding${NC}"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "   Attempt $RETRY_COUNT/$MAX_RETRIES - waiting..."
        sleep 2
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${YELLOW}⚠️  Warning: Health check failed after $MAX_RETRIES attempts${NC}"
    echo -e "${YELLOW}   Server is running but may be having issues responding${NC}"
    echo -e "${YELLOW}   Check logs: tail -f $STARTUP_LOG${NC}"
fi

# Display service status
echo ""
echo -e "${BLUE}============================================================================${NC}"
echo -e "${GREEN}✅ Startup complete!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "${BLUE}📊 Server Information:${NC}"
echo "   PID: $SERVER_PID"
echo "   URL: $SERVER_URL"
echo "   Dashboard: $SERVER_URL/"
echo "   API Docs: $SERVER_URL/docs"
echo "   Health Check: $SERVER_URL/health"
echo ""
echo -e "${BLUE}📝 Log Files:${NC}"
echo "   Startup: $STARTUP_LOG"
echo "   Main: $MAIN_LOG"
echo ""
echo -e "${BLUE}🛠️  Management Commands:${NC}"
echo "   Status:  ./status.sh"
echo "   Stop:    ./stop.sh"
echo "   Restart: ./restart.sh"
echo "   Logs:    tail -f $MAIN_LOG"
echo ""
echo -e "${BLUE}💡 Quick Checks:${NC}"
echo "   timeout 3 curl $SERVER_URL/health"
echo "   timeout 3 curl $SERVER_URL/api/system/status"
echo ""

# Show last few lines of startup log
echo -e "${BLUE}📋 Recent startup log entries:${NC}"
tail -n 10 "$STARTUP_LOG" | sed 's/^/   /'
echo ""

echo -e "${GREEN}🎉 Trading system is now running!${NC}"
echo ""
