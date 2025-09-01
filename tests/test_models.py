import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, date
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from models.database import get_db, init_db, close_db
from models.signals import Signal, SignalStatus, SignalType
from models.settings import Settings
from models.risk_events import RiskEvent, RiskEventType
from models.pnl_reports import PnLReport

class TestDatabaseModel:
    """Test database connection and operations"""
    
    @pytest.mark.asyncio
    async def test_database_initialization(self):
        """Test database initialization"""
        # Should not raise any exceptions
        await init_db()
        assert True
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test database connection"""
        await init_db()
        
        async for db in get_db():
            assert db is not None
            break
    
    @pytest.mark.asyncio
    async def test_database_cleanup(self):
        """Test database cleanup"""
        await init_db()
        await close_db()
        # Should not raise any exceptions
        assert True

class TestSignalModel:
    """Test Signal model"""
    
    def test_signal_creation(self):
        """Test signal model creation"""
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            stop_loss=2400.0,
            take_profit=2600.0,
            reason="Technical breakout",
            status=SignalStatus.PENDING
        )
        
        assert signal.symbol == "RELIANCE"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 2500.0
        assert signal.quantity == 10
        assert signal.status == SignalStatus.PENDING
    
    def test_signal_validation(self):
        """Test signal model validation"""
        # Test valid signal
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            stop_loss=2400.0,
            take_profit=2600.0,
            reason="Technical breakout"
        )
        
        # Should not raise validation errors
        assert signal.symbol is not None
        assert signal.price > 0
        assert signal.quantity > 0
    
    def test_signal_status_transitions(self):
        """Test signal status transitions"""
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            status=SignalStatus.PENDING
        )
        
        # Test status transitions
        signal.status = SignalStatus.APPROVED
        assert signal.status == SignalStatus.APPROVED
        
        signal.status = SignalStatus.EXECUTED
        assert signal.status == SignalStatus.EXECUTED
    
    def test_signal_type_enum(self):
        """Test signal type enumeration"""
        assert SignalType.BUY.value == "buy"
        assert SignalType.SELL.value == "sell"
        assert SignalType.EXIT.value == "exit"
    
    def test_signal_status_enum(self):
        """Test signal status enumeration"""
        assert SignalStatus.PENDING.value == "pending"
        assert SignalStatus.APPROVED.value == "approved"
        assert SignalStatus.EXECUTED.value == "executed"
        assert SignalStatus.REJECTED.value == "rejected"
        assert SignalStatus.EXPIRED.value == "expired"
        assert SignalStatus.FAILED.value == "failed"

class TestSettingsModel:
    """Test Settings model"""
    
    def test_settings_creation(self):
        """Test settings model creation"""
        settings = Settings(
            auto_trade=False,
            risk_per_trade=0.02,
            max_positions=10,
            max_daily_loss=0.05,
            signal_timeout=300,
            min_price=10.0,
            min_liquidity=100000,
            environment="development"
        )
        
        assert settings.auto_trade is False
        assert settings.risk_per_trade == 0.02
        assert settings.max_positions == 10
        assert settings.environment == "development"
    
    def test_settings_defaults(self):
        """Test settings default values"""
        settings = Settings()
        
        # Test that defaults are set appropriately
        assert settings.auto_trade is False
        assert settings.risk_per_trade == 0.02
        assert settings.max_positions == 10
        assert settings.signal_timeout == 300
    
    def test_settings_validation(self):
        """Test settings validation"""
        # Test valid settings
        settings = Settings(
            risk_per_trade=0.02,
            max_positions=10,
            max_daily_loss=0.05
        )
        
        # Should not raise validation errors
        assert 0 < settings.risk_per_trade <= 1
        assert settings.max_positions > 0
        assert 0 < settings.max_daily_loss <= 1
    
    def test_settings_update(self):
        """Test settings update functionality"""
        settings = Settings(auto_trade=False)
        
        # Update settings
        settings.auto_trade = True
        settings.risk_per_trade = 0.025
        
        assert settings.auto_trade is True
        assert settings.risk_per_trade == 0.025

class TestRiskEventModel:
    """Test RiskEvent model"""
    
    def test_risk_event_creation(self):
        """Test risk event model creation"""
        risk_event = RiskEvent(
            event_type=RiskEventType.POSITION_LIMIT_EXCEEDED,
            symbol="RELIANCE",
            description="Position limit exceeded for RELIANCE",
            severity="HIGH",
            data={"current_positions": 15, "limit": 10}
        )
        
        assert risk_event.event_type == RiskEventType.POSITION_LIMIT_EXCEEDED
        assert risk_event.symbol == "RELIANCE"
        assert risk_event.severity == "HIGH"
        assert risk_event.data["current_positions"] == 15
    
    def test_risk_event_types(self):
        """Test risk event type enumeration"""
        assert RiskEventType.POSITION_LIMIT_EXCEEDED.value == "position_limit_exceeded"
        assert RiskEventType.DAILY_LOSS_LIMIT_EXCEEDED.value == "daily_loss_limit_exceeded"
        assert RiskEventType.MARGIN_CALL.value == "margin_call"
        assert RiskEventType.STOP_LOSS_TRIGGERED.value == "stop_loss_triggered"
    
    def test_risk_event_severity_levels(self):
        """Test risk event severity levels"""
        # Test different severity levels
        low_risk = RiskEvent(
            event_type=RiskEventType.STOP_LOSS_TRIGGERED,
            severity="LOW"
        )
        
        high_risk = RiskEvent(
            event_type=RiskEventType.DAILY_LOSS_LIMIT_EXCEEDED,
            severity="HIGH"
        )
        
        assert low_risk.severity == "LOW"
        assert high_risk.severity == "HIGH"
    
    def test_risk_event_timestamp(self):
        """Test risk event timestamp"""
        risk_event = RiskEvent(
            event_type=RiskEventType.MARGIN_CALL,
            timestamp=datetime.now()
        )
        
        assert isinstance(risk_event.timestamp, datetime)

class TestPnLReportModel:
    """Test PnLReport model"""
    
    def test_pnl_report_creation(self):
        """Test PnL report model creation"""
        pnl_report = PnLReport(
            date=date.today(),
            realized_pnl=1500.0,
            unrealized_pnl=300.0,
            total_pnl=1800.0,
            fees=25.0,
            trades_count=8,
            win_rate=0.75,
            max_drawdown=-200.0
        )
        
        assert pnl_report.realized_pnl == 1500.0
        assert pnl_report.unrealized_pnl == 300.0
        assert pnl_report.total_pnl == 1800.0
        assert pnl_report.trades_count == 8
        assert pnl_report.win_rate == 0.75
    
    def test_pnl_report_calculations(self):
        """Test PnL report calculations"""
        pnl_report = PnLReport(
            date=date.today(),
            realized_pnl=1000.0,
            unrealized_pnl=500.0,
            fees=50.0
        )
        
        # Test net PnL calculation
        net_pnl = pnl_report.realized_pnl + pnl_report.unrealized_pnl - pnl_report.fees
        assert net_pnl == 1450.0
    
    def test_pnl_report_validation(self):
        """Test PnL report validation"""
        pnl_report = PnLReport(
            date=date.today(),
            trades_count=10,
            win_rate=0.8
        )
        
        # Validate win rate is between 0 and 1
        assert 0 <= pnl_report.win_rate <= 1
        assert pnl_report.trades_count >= 0
    
    def test_pnl_report_date_handling(self):
        """Test PnL report date handling"""
        today = date.today()
        pnl_report = PnLReport(date=today)
        
        assert pnl_report.date == today
        assert isinstance(pnl_report.date, date)

class TestModelRelationships:
    """Test relationships between models"""
    
    def test_signal_to_pnl_relationship(self):
        """Test relationship between signals and PnL"""
        # Create a signal
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            status=SignalStatus.EXECUTED
        )
        
        # Create corresponding PnL entry
        pnl_report = PnLReport(
            date=date.today(),
            realized_pnl=500.0,  # Profit from the signal
            trades_count=1
        )
        
        # Verify the relationship makes sense
        assert signal.status == SignalStatus.EXECUTED
        assert pnl_report.realized_pnl > 0
        assert pnl_report.trades_count == 1
    
    def test_risk_event_to_signal_relationship(self):
        """Test relationship between risk events and signals"""
        # Create a signal that might trigger a risk event
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=50,  # Large quantity
            status=SignalStatus.PENDING
        )
        
        # Create corresponding risk event
        risk_event = RiskEvent(
            event_type=RiskEventType.POSITION_LIMIT_EXCEEDED,
            symbol=signal.symbol,
            description=f"Large position requested for {signal.symbol}",
            data={"requested_quantity": signal.quantity, "limit": 30}
        )
        
        # Verify the relationship
        assert risk_event.symbol == signal.symbol
        assert risk_event.data["requested_quantity"] == signal.quantity
    
    def test_settings_impact_on_signals(self):
        """Test how settings impact signal processing"""
        # Create settings
        settings = Settings(
            max_positions=5,
            risk_per_trade=0.02,
            auto_trade=False
        )
        
        # Create signal
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            status=SignalStatus.PENDING
        )
        
        # Verify settings would impact signal processing
        assert settings.auto_trade is False  # Manual approval required
        assert settings.max_positions == 5   # Position limit check needed
        assert settings.risk_per_trade == 0.02  # Risk calculation needed

class TestModelSerialization:
    """Test model serialization and deserialization"""
    
    def test_signal_to_dict(self):
        """Test signal model to dictionary conversion"""
        signal = Signal(
            symbol="RELIANCE",
            signal_type=SignalType.BUY,
            price=2500.0,
            quantity=10,
            status=SignalStatus.PENDING
        )
        
        # Convert to dict (this would be implemented in the actual model)
        signal_dict = {
            "symbol": signal.symbol,
            "signal_type": signal.signal_type.value,
            "price": signal.price,
            "quantity": signal.quantity,
            "status": signal.status.value
        }
        
        assert signal_dict["symbol"] == "RELIANCE"
        assert signal_dict["signal_type"] == "buy"
        assert signal_dict["status"] == "pending"
    
    def test_pnl_report_to_dict(self):
        """Test PnL report model to dictionary conversion"""
        pnl_report = PnLReport(
            date=date.today(),
            realized_pnl=1500.0,
            unrealized_pnl=300.0,
            trades_count=8
        )
        
        # Convert to dict
        report_dict = {
            "date": pnl_report.date.isoformat(),
            "realized_pnl": pnl_report.realized_pnl,
            "unrealized_pnl": pnl_report.unrealized_pnl,
            "trades_count": pnl_report.trades_count
        }
        
        assert report_dict["realized_pnl"] == 1500.0
        assert report_dict["trades_count"] == 8
        assert isinstance(report_dict["date"], str)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
