"""
Unit tests for Database Models
Tests signals, watchlist, PnL reports, and risk events models
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.signals import Signal, SignalType, SignalStatus
from models.watchlist import Watchlist, WatchlistCategory
from models.pnl_reports import PnLReport
from models.risk_events import RiskEvent, RiskEventType
from models.database import init_db, get_db


class TestSignalModel:
    """Test suite for Signal model"""

    @pytest.fixture
    async def db_session(self):
        """Create test database session"""
        # Use in-memory SQLite for testing
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        # Create tables
        from models.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_signal_creation(self, db_session):
        """Test creating a new signal"""
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.00,
            quantity=100,
            reason="Bullish momentum",
            stop_loss=2400.00,
            take_profit=2600.00,
            expiry_time=datetime.utcnow() + timedelta(hours=24)
        )

        db_session.add(signal)
        await db_session.commit()

        # Verify signal was created
        result = await db_session.get(Signal, signal.id)
        assert result is not None
        assert result.symbol == "RELIANCE"
        assert result.signal_type == SignalType.BUY
        assert result.price == 2500.00

    @pytest.mark.asyncio
    async def test_signal_status_update(self, db_session):
        """Test updating signal status"""
        signal = Signal(
            symbol="TCS",
            signal_type=SignalType.SELL,
            price=3200.00,
            quantity=50,
            status=SignalStatus.PENDING,
            expiry_time=datetime.utcnow() + timedelta(hours=24)
        )

        db_session.add(signal)
        await db_session.commit()

        # Update status
        signal.status = SignalStatus.EXECUTED
        signal.executed_at = datetime.utcnow()

        await db_session.commit()

        # Verify update
        result = await db_session.get(Signal, signal.id)
        assert result.status == SignalStatus.EXECUTED
        assert result.executed_at is not None

    @pytest.mark.asyncio
    async def test_signal_query_by_symbol(self, db_session):
        """Test querying signals by symbol"""
        expiry = datetime.utcnow() + timedelta(hours=24)
        signals = [
            Signal(symbol="RELIANCE", signal_type=SignalType.BUY, price=2500.00, quantity=100, expiry_time=expiry),
            Signal(symbol="TCS", signal_type=SignalType.SELL, price=3200.00, quantity=50, expiry_time=expiry),
            Signal(symbol="RELIANCE", signal_type=SignalType.SELL, price=2550.00, quantity=100, expiry_time=expiry)
        ]

        for signal in signals:
            db_session.add(signal)
        await db_session.commit()

        # Query RELIANCE signals
        stmt = sa.select(Signal).where(Signal.symbol == "RELIANCE")
        result = await db_session.execute(stmt)
        reliance_signals = result.scalars().all()

        assert len(reliance_signals) == 2
        assert all(s.symbol == "RELIANCE" for s in reliance_signals)

    @pytest.mark.asyncio
    async def test_signal_query_by_date_range(self, db_session):
        """Test querying signals by date range"""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        expiry = now + timedelta(hours=24)

        signals = [
            Signal(symbol="INFY", signal_type=SignalType.BUY, price=1800.00, quantity=100,
                  created_at=yesterday, expiry_time=expiry),
            Signal(symbol="INFY", signal_type=SignalType.SELL, price=1850.00, quantity=50,
                  created_at=now, expiry_time=expiry),
            Signal(symbol="INFY", signal_type=SignalType.BUY, price=1820.00, quantity=75,
                  created_at=tomorrow, expiry_time=expiry)
        ]

        for signal in signals:
            db_session.add(signal)
        await db_session.commit()

        # Query signals from today onwards
        stmt = sa.select(Signal).where(Signal.created_at >= now.date())
        result = await db_session.execute(stmt)
        recent_signals = result.scalars().all()

        assert len(recent_signals) == 2

    @pytest.mark.asyncio
    async def test_signal_performance_metrics(self, db_session):
        """Test calculating signal performance"""
        signal = Signal(
            symbol="HDFC",
            signal_type=SignalType.BUY,
            price=1500.00,
            quantity=100,
            status=SignalStatus.EXECUTED,
            expiry_time=datetime.utcnow() + timedelta(hours=24)
        )

        db_session.add(signal)
        await db_session.commit()

        # Calculate performance (mock current price)
        current_price = 1520.00
        if signal.signal_type == SignalType.BUY:
            pnl = current_price - signal.price
            pnl_percent = (pnl / signal.price) * 100
        
        assert pnl == 20.00
        assert pnl_percent == pytest.approx(1.33, rel=1e-2)


class TestWatchlistModel:
    """Test suite for Watchlist model"""

    @pytest.fixture
    async def db_session(self):
        """Create test database session"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        from models.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_watchlist_creation(self, db_session):
        """Test creating a new watchlist item"""
        watchlist_item = Watchlist(
            symbol="RELIANCE",
            category=WatchlistCategory.LONG_TERM.value,
            is_active=True
        )

        db_session.add(watchlist_item)
        await db_session.commit()

        result = await db_session.get(Watchlist, watchlist_item.id)
        assert result.symbol == "RELIANCE"
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_watchlist_category_filtering(self, db_session):
        """Test filtering watchlist by category"""
        items = [
            Watchlist(symbol="TCS", category=WatchlistCategory.SHORT_TERM.value),
            Watchlist(symbol="INFY", category=WatchlistCategory.LONG_TERM.value),
            Watchlist(symbol="WIPRO", category=WatchlistCategory.DAY_TRADING.value)
        ]

        for item in items:
            db_session.add(item)
        await db_session.commit()

        # Query short-term items
        stmt = sa.select(Watchlist).where(Watchlist.category == WatchlistCategory.SHORT_TERM.value)
        result = await db_session.execute(stmt)
        short_term_items = result.scalars().all()

        assert len(short_term_items) == 1
        assert short_term_items[0].symbol == "TCS"

    @pytest.mark.asyncio
    async def test_watchlist_active_filtering(self, db_session):
        """Test filtering active watchlist items"""
        items = [
            Watchlist(symbol="RELIANCE", is_active=True),
            Watchlist(symbol="TCS", is_active=False),
            Watchlist(symbol="INFY", is_active=True)
        ]

        for item in items:
            db_session.add(item)
        await db_session.commit()

        # Query active items
        stmt = sa.select(Watchlist).where(Watchlist.is_active == True)
        result = await db_session.execute(stmt)
        active_items = result.scalars().all()

        assert len(active_items) == 2
        symbols = [item.symbol for item in active_items]
        assert "RELIANCE" in symbols
        assert "INFY" in symbols


class TestPnLReportModel:
    """Test suite for PnL Report model"""

    @pytest.fixture
    async def db_session(self):
        """Create test database session"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        from models.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_pnl_report_creation(self, db_session):
        """Test creating PnL report"""
        report = PnLReport(
            date=datetime.utcnow().date(),
            daily_pnl=1500.00,
            realized_pnl=1200.00,
            unrealized_pnl=300.00,
            total_trades=15,
            winning_trades=10,
            losing_trades=5,
            win_rate=66.67
        )

        db_session.add(report)
        await db_session.commit()

        result = await db_session.get(PnLReport, report.id)
        assert result.daily_pnl == 1500.00
        assert result.win_rate == 66.67

    @pytest.mark.asyncio
    async def test_pnl_metrics_calculation(self, db_session):
        """Test PnL metrics calculations"""
        report = PnLReport(
            date=datetime.utcnow().date(),
            realized_pnl=100.00,
            unrealized_pnl=50.00,
            total_trades=4,
            winning_trades=3,
            losing_trades=1
        )

        db_session.add(report)
        await db_session.commit()

        # Test computed properties
        assert report.total_pnl == 150.00  # realized + unrealized
        assert report.win_rate == 0.75  # 3/4

    @pytest.mark.asyncio
    async def test_pnl_report_date_query(self, db_session):
        """Test querying PnL reports by date"""
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)

        reports = [
            PnLReport(date=yesterday, daily_pnl=100.00),
            PnLReport(date=today, daily_pnl=200.00)
        ]

        for report in reports:
            db_session.add(report)
        await db_session.commit()

        # Query today's report
        stmt = sa.select(PnLReport).where(PnLReport.date == today)
        result = await db_session.execute(stmt)
        today_report = result.scalar_one()

        assert today_report.daily_pnl == 200.00


class TestRiskEventModel:
    """Test suite for Risk Event model"""

    @pytest.fixture
    async def db_session(self):
        """Create test database session"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        from models.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_risk_event_creation(self, db_session):
        """Test creating risk events"""
        event = RiskEvent(
            event_type=RiskEventType.POSITION_LIMIT_EXCEEDED,
            symbol="RELIANCE",
            message="Position size exceeded 10% of portfolio",
            meta={"position_percent": 12.5, "max_allowed": 10.0},
            severity="high",
            resolved="N"
        )

        db_session.add(event)
        await db_session.commit()

        result = await db_session.get(RiskEvent, event.id)
        assert result.event_type == RiskEventType.POSITION_LIMIT_EXCEEDED
        assert result.severity == "high"
        assert result.resolved == "N"

    @pytest.mark.asyncio
    async def test_risk_event_resolution(self, db_session):
        """Test resolving risk events"""
        event = RiskEvent(
            event_type=RiskEventType.MARGIN_CALL,
            message="Margin requirement not met",
            severity="critical",
            resolved="N"
        )

        db_session.add(event)
        await db_session.commit()

        # Resolve the event
        event.resolved = "Y"
        event.resolved_at = datetime.utcnow()

        await db_session.commit()

        result = await db_session.get(RiskEvent, event.id)
        assert result.resolved == "Y"
        assert result.resolved_at is not None

    @pytest.mark.asyncio
    async def test_risk_event_querying(self, db_session):
        """Test querying risk events by severity"""
        events = [
            RiskEvent(event_type=RiskEventType.DRAWDOWN_HALT, severity="low", message="Minor drawdown"),
            RiskEvent(event_type=RiskEventType.API_ERROR, severity="medium", message="API timeout"),
            RiskEvent(event_type=RiskEventType.MARGIN_INSUFFICIENT, severity="high", message="Low margin"),
            RiskEvent(event_type=RiskEventType.MARGIN_CALL, severity="critical", message="Margin call")
        ]

        for event in events:
            db_session.add(event)
        await db_session.commit()

        # Query high and critical events
        stmt = sa.select(RiskEvent).where(
            RiskEvent.severity.in_(["high", "critical"])
        )
        result = await db_session.execute(stmt)
        critical_events = result.scalars().all()

        assert len(critical_events) == 2
        severities = [event.severity for event in critical_events]
        assert "high" in severities
        assert "critical" in severities


class TestDatabaseIntegration:
    """Test suite for database integration and relationships"""

    @pytest.fixture
    async def db_session(self):
        """Create test database session"""
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        async_session = async_sessionmaker(engine, expire_on_commit=False)
        
        from models.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_database_initialization(self):
        """Test database initialization"""
        # Test that init_db works without errors
        try:
            await init_db()
            assert True
        except Exception as e:
            pytest.fail(f"Database initialization failed: {e}")

    @pytest.mark.asyncio
    async def test_session_management(self):
        """Test database session management"""
        async for session in get_db():
            assert session is not None
            assert isinstance(session, AsyncSession)
            break

    @pytest.mark.asyncio
    async def test_concurrent_database_access(self, db_session):
        """Test concurrent database operations"""
        async def create_signal(symbol, price):
            signal = Signal(
                symbol=symbol,
                signal_type=SignalType.BUY,
                price=price,
                quantity=100,
                expiry_time=datetime.utcnow() + timedelta(hours=24)
            )
            db_session.add(signal)
            await db_session.commit()
            return signal.id

        # Create signals concurrently
        tasks = [
            create_signal("STOCK1", 100.00),
            create_signal("STOCK2", 200.00),
            create_signal("STOCK3", 300.00)
        ]

        signal_ids = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all signals were created
        assert len(signal_ids) == 3
        assert all(isinstance(sid, int) for sid in signal_ids)

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, db_session):
        """Test transaction rollback on error"""
        try:
            # Create a signal
            signal = Signal(
                symbol="TEST",
                signal_type=SignalType.BUY,
                price=100.00,
                confidence=0.8
            )
            db_session.add(signal)
            
            # Intentionally cause an error
            raise Exception("Test error")
            
        except Exception:
            await db_session.rollback()

        # Verify signal was not saved
        stmt = sa.select(Signal).where(Signal.symbol == "TEST")
        result = await db_session.execute(stmt)
        signals = result.scalars().all()
        assert len(signals) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])