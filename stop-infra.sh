#!/bin/bash
# Stop infrastructure services

echo "🛑 Stopping Trading System Infrastructure..."
echo ""

docker-compose -f docker-compose.infra.yml down

echo ""
echo "✅ Infrastructure stopped"
echo ""
echo "💡 To remove all data volumes as well, run:"
echo "   docker-compose -f docker-compose.infra.yml down -v"
echo ""
