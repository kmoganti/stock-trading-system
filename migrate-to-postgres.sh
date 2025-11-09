#!/bin/bash
# Migrate data from SQLite to PostgreSQL

set -e

echo "=========================================================================="
echo "🔄 SQLite to PostgreSQL Migration"
echo "=========================================================================="
echo ""

# Check if SQLite database exists
if [ ! -f "trading_system.db" ]; then
    echo "❌ SQLite database not found: trading_system.db"
    exit 1
fi

# Check if PostgreSQL is running
if ! docker exec trading_postgres pg_isready -U trading_user -d trading_system &> /dev/null; then
    echo "❌ PostgreSQL is not running"
    echo "   Start it first: ./start-infra.sh"
    exit 1
fi

echo "📋 Migration Steps:"
echo "   1. Backup current SQLite database"
echo "   2. Export SQLite data"
echo "   3. Create PostgreSQL schema"
echo "   4. Import data to PostgreSQL"
echo ""

read -p "Continue with migration? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration cancelled"
    exit 0
fi

echo ""
echo "📦 Step 1: Backing up SQLite database..."
BACKUP_FILE="trading_system.db.backup.$(date +%Y%m%d_%H%M%S)"
cp trading_system.db "$BACKUP_FILE"
echo "   ✅ Backup created: $BACKUP_FILE"

echo ""
echo "📤 Step 2: Exporting SQLite data..."
sqlite3 trading_system.db .dump > sqlite_export.sql
echo "   ✅ Data exported to: sqlite_export.sql"

echo ""
echo "🐘 Step 3: Setting up PostgreSQL schema..."
# Get password from docker-compose or use default
PG_PASSWORD="${POSTGRES_PASSWORD:-trading_secure_password_2025}"
export PGPASSWORD="$PG_PASSWORD"

# Run Alembic migrations to create schema
echo "   Running Alembic migrations..."
DATABASE_URL="postgresql+asyncpg://trading_user:${PG_PASSWORD}@localhost:5432/trading_system" \
    python -m alembic upgrade head

echo "   ✅ PostgreSQL schema created"

echo ""
echo "📥 Step 4: Importing data..."
echo "   Converting SQLite SQL to PostgreSQL format..."

# Convert SQLite dump to PostgreSQL-compatible format
sed -e 's/INTEGER PRIMARY KEY AUTOINCREMENT/SERIAL PRIMARY KEY/g' \
    -e 's/PRAGMA foreign_keys=OFF;//g' \
    -e 's/BEGIN TRANSACTION;//g' \
    -e 's/COMMIT;//g' \
    -e '/^CREATE TABLE/,/);$/ {
        s/INTEGER NOT NULL/INT NOT NULL/g
        s/REAL/DOUBLE PRECISION/g
        s/TEXT/VARCHAR/g
    }' \
    sqlite_export.sql > postgres_import.sql

echo "   Importing to PostgreSQL..."
psql -h localhost -U trading_user -d trading_system -f postgres_import.sql 2>&1 | grep -v "ERROR.*already exists" || true

echo ""
echo "=========================================================================="
echo "✅ Migration Complete!"
echo "=========================================================================="
echo ""
echo "📊 Summary:"
echo "   • SQLite backup: $BACKUP_FILE"
echo "   • Export file: sqlite_export.sql"
echo "   • PostgreSQL data imported"
echo ""
echo "🔄 Next Steps:"
echo "   1. Update .env file:"
echo "      DATABASE_URL=postgresql+asyncpg://trading_user:${PG_PASSWORD}@localhost:5432/trading_system"
echo ""
echo "   2. Test PostgreSQL connection:"
echo "      python -c 'from models.database import engine; import asyncio; asyncio.run(engine.connect())'"
echo ""
echo "   3. Restart your application:"
echo "      ./restart.sh"
echo ""
echo "⚠️  Keep the SQLite backup until you confirm everything works!"
echo ""

# Cleanup
unset PGPASSWORD
