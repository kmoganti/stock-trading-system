# 🚀 Hybrid Architecture Setup Guide

## Architecture Overview

**Lightweight Docker Infrastructure + Native Python App**

```
┌─────────────────────────────────────────────┐
│   Docker Containers (Infrastructure Only)   │
│                                             │
│  ┌──────────────┐      ┌──────────────┐   │
│  │  PostgreSQL  │      │    Redis     │   │
│  │  (256MB RAM) │      │  (128MB RAM) │   │
│  │   Port 5432  │      │   Port 6379  │   │
│  └──────────────┘      └──────────────┘   │
└─────────────────────────────────────────────┘
                    ↕
┌─────────────────────────────────────────────┐
│     Native Python Process (Host)            │
│                                             │
│  • FastAPI Web Server                       │
│  • Trading Strategy Engine                  │
│  • Scheduler                                │
│  • Telegram Bot                             │
└─────────────────────────────────────────────┘
```

## Benefits

✅ **Low Resource Usage**
   - Only ~400MB RAM for Docker containers
   - Python runs natively (no container overhead)
   - Faster development/debugging

✅ **Production-Grade Database**
   - PostgreSQL handles concurrent requests perfectly
   - No more "database is locked" errors
   - True connection pooling (10 persistent + 20 overflow)

✅ **Redis Caching** (Optional, for future use)
   - Fast in-memory caching
   - Session management
   - Rate limiting

## Quick Start

### 1. Start Infrastructure

```bash
./start-infra.sh
```

This starts PostgreSQL and Redis in Docker containers.

### 2. Update Environment

Edit `.env` file:

```bash
# Replace SQLite with PostgreSQL
DATABASE_URL=postgresql+asyncpg://trading_user:trading_secure_password_2025@localhost:5432/trading_system

# Optional: Redis cache
REDIS_URL=redis://localhost:6379/0
```

### 3. Run Migrations (First Time Only)

```bash
# Create database schema
alembic upgrade head
```

### 4. Migrate Existing Data (Optional)

If you have existing SQLite data:

```bash
./migrate-to-postgres.sh
```

### 5. Start Trading System

```bash
./start.sh
```

Your Python app runs natively, connecting to PostgreSQL in Docker.

## Daily Operations

### Start Everything
```bash
# Start infrastructure (PostgreSQL + Redis)
./start-infra.sh

# Start trading app
./start.sh
```

### Stop Everything
```bash
# Stop trading app
./stop.sh

# Stop infrastructure
./stop-infra.sh
```

### Check Status
```bash
# Infrastructure status
docker-compose -f docker-compose.infra.yml ps

# App status
./status.sh
```

### View Logs
```bash
# Infrastructure logs
docker-compose -f docker-compose.infra.yml logs -f

# App logs
tail -f logs/trading_system.log
```

## Resource Usage

**Docker Containers:**
- PostgreSQL: ~150-200MB RAM
- Redis: ~30-50MB RAM
- **Total: ~200-250MB RAM**

**Python App:**
- Trading System: ~150-250MB RAM
- **Total: ~150-250MB RAM**

**Grand Total: ~400-500MB RAM** (very laptop-friendly!)

## Database Connection

**From Python App:**
```python
# Automatic via environment variable
DATABASE_URL=postgresql+asyncpg://trading_user:PASSWORD@localhost:5432/trading_system
```

**Direct Access (psql):**
```bash
# Connect to PostgreSQL
docker exec -it trading_postgres psql -U trading_user -d trading_system

# Or from host (if psql installed)
psql -h localhost -U trading_user -d trading_system
```

## Troubleshooting

### Infrastructure won't start
```bash
# Check Docker status
docker ps

# Check logs
docker-compose -f docker-compose.infra.yml logs
```

### Connection refused
```bash
# Verify PostgreSQL is ready
docker exec trading_postgres pg_isready -U trading_user

# Verify Redis is ready
docker exec trading_redis redis-cli ping
```

### Port already in use
```bash
# Check what's using port 5432
sudo lsof -i :5432

# Check what's using port 6379
sudo lsof -i :6379
```

## Performance Comparison

| Metric | SQLite | PostgreSQL |
|--------|--------|------------|
| Concurrent Writes | ❌ 1 at a time | ✅ Unlimited |
| Connection Pool | ❌ Doesn't work | ✅ 30 connections |
| Under Load | ❌ Hangs | ✅ Stable |
| Response Time | ~100ms | ~10ms |
| Scalability | ❌ Limited | ✅ Excellent |

## Cost

💰 **FREE** - All open source:
- PostgreSQL: Free
- Redis: Free  
- Docker: Free

🎯 **Resource-efficient**: Perfect for laptops and small VPS instances!
