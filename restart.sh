#!/bin/bash
# ============================================================================
# Trading System Restart Script
# ============================================================================
# This script restarts the trading system (stop + start)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}============================================================================${NC}"
echo -e "${BLUE}🔄 Stock Trading System - Restart Script${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""

# Stop the system
echo -e "${BLUE}Step 1: Stopping trading system...${NC}"
echo ""
./stop.sh

# Wait a moment
sleep 2

# Start the system
echo ""
echo -e "${BLUE}Step 2: Starting trading system...${NC}"
echo ""
./start.sh

echo ""
echo -e "${GREEN}✅ Restart complete!${NC}"
echo ""
