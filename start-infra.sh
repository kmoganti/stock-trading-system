#!/bin/bash
# Start lightweight infrastructure services (PostgreSQL + Redis)
# Python app runs separately on host

set -e

echo "=========================================================================="
echo "🚀 Starting Trading System Infrastructure"
echo "=========================================================================="
echo ""

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    echo "   Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose is not installed"
    echo "   Install: sudo apt-get install docker-compose"
    exit 1
fi

echo "📋 Checking existing containers..."
if docker-compose -f docker-compose.infra.yml ps | grep -q "Up"; then
    echo "⚠️  Infrastructure containers already running"
    echo ""
    docker-compose -f docker-compose.infra.yml ps
    echo ""
    read -p "Do you want to restart them? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing containers running"
        exit 0
    fi
    echo ""
    echo "🔄 Stopping existing containers..."
    docker-compose -f docker-compose.infra.yml down
fi

echo ""
echo "🐘 Starting PostgreSQL..."
echo "📦 Starting Redis..."
echo ""

# Start infrastructure services
docker-compose -f docker-compose.infra.yml up -d

echo ""
echo "⏳ Waiting for services to be ready..."

# Wait for PostgreSQL
echo -n "   PostgreSQL: "
for i in {1..30}; do
    if docker exec trading_postgres pg_isready -U trading_user -d trading_system &> /dev/null; then
        echo "✅ Ready"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 30 ]; then
        echo ""
        echo "❌ PostgreSQL failed to start in 30 seconds"
        docker-compose -f docker-compose.infra.yml logs postgres
        exit 1
    fi
done

# Wait for Redis
echo -n "   Redis: "
for i in {1..15}; do
    if docker exec trading_redis redis-cli ping &> /dev/null; then
        echo "✅ Ready"
        break
    fi
    echo -n "."
    sleep 1
    if [ $i -eq 15 ]; then
        echo ""
        echo "❌ Redis failed to start in 15 seconds"
        docker-compose -f docker-compose.infra.yml logs redis
        exit 1
    fi
done

echo ""
echo "=========================================================================="
echo "✅ Infrastructure Started Successfully"
echo "=========================================================================="
echo ""
echo "📊 Service Information:"
echo "   🐘 PostgreSQL: localhost:5432"
echo "      Database: trading_system"
echo "      User: trading_user"
echo "      Password: (set in docker-compose.infra.yml)"
echo ""
echo "   📦 Redis: localhost:6379"
echo "      Memory limit: 100MB"
echo "      Persistence: enabled"
echo ""
echo "🔗 Connection Strings:"
echo "   PostgreSQL: postgresql+asyncpg://trading_user:PASSWORD@localhost:5432/trading_system"
echo "   Redis: redis://localhost:6379/0"
echo ""
echo "📝 Management Commands:"
echo "   Status:  docker-compose -f docker-compose.infra.yml ps"
echo "   Logs:    docker-compose -f docker-compose.infra.yml logs -f"
echo "   Stop:    docker-compose -f docker-compose.infra.yml down"
echo "   Restart: docker-compose -f docker-compose.infra.yml restart"
echo ""
echo "💡 Next Steps:"
echo "   1. Update .env with PostgreSQL connection string"
echo "   2. Install Python dependencies: pip install -r requirements.txt"
echo "   3. Run migrations: alembic upgrade head"
echo "   4. Start Python app: ./start.sh"
echo ""
