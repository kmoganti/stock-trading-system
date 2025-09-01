import pytest
import asyncio
from datetime import date, datetime
from unittest.mock import Mock, AsyncMock, patch
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.risk import RiskService
from services.order_manager import OrderManager
from services.pnl import PnLService
from services.report import ReportService
from config.settings import get_settings

@pytest.fixture
def mock_settings():
    """Mock settings for testing"""
    settings = Mock()
    settings.client_id = "test_client"
    settings.auth_code = "test_auth"
    settings.app_secret = "test_secret"
    settings.base_url = "https://api.test.com"
    settings.auto_trade = False
    settings.risk_per_trade = 0.02
    settings.max_positions = 10
    settings.max_daily_loss = 5000
    return settings

@pytest.fixture
def mock_iifl_service(mock_settings):
    """Mock IIFL API service"""
    service = Mock(spec=IIFLAPIService)
    service.authenticate = AsyncMock(return_value={"status": "success", "token": "test_token"})
    service.get_market_data = AsyncMock(return_value={
        "symbol": "RELIANCE",
        "ltp": 2500.0,
        "change": 25.0,
        "volume": 1000000
    })
    service.place_order = AsyncMock(return_value={
        "order_id": "TEST123",
        "status": "COMPLETE",
        "avg_price": 2500.0
    })
    service.get_positions = AsyncMock(return_value=[])
    service.get_margin_info = AsyncMock(return_value={
        "available_margin": 100000,
        "used_margin": 50000
    })
    return service

@pytest.fixture
def data_fetcher(mock_iifl_service):
    """Data fetcher with mocked IIFL service"""
    return DataFetcher(mock_iifl_service)

@pytest.fixture
def strategy_service(data_fetcher):
    """Strategy service with mocked data fetcher"""
    return StrategyService(data_fetcher)

@pytest.fixture
def risk_service():
    """Risk service instance"""
    return RiskService()

@pytest.fixture
def pnl_service():
    """PnL service instance"""
    return PnLService()

class TestSystemIntegration:
    """Integration tests for the complete trading system"""
    
    @pytest.mark.asyncio
    async def test_data_flow_integration(self, data_fetcher, strategy_service):
        """Test data flow from API to strategy generation"""
        # Mock historical data
        with patch.object(data_fetcher, 'get_historical_data') as mock_hist:
            mock_hist.return_value = [
                {"date": "2023-01-01", "close": 2400, "volume": 1000000},
                {"date": "2023-01-02", "close": 2450, "volume": 1100000},
                {"date": "2023-01-03", "close": 2500, "volume": 1200000},
            ]
            
            # Generate signals
            signals = await strategy_service.generate_signals("RELIANCE")
            
            # Verify signals were generated
            assert isinstance(signals, list)
            mock_hist.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_risk_management_integration(self, risk_service):
        """Test risk management validation"""
        # Test position size calculation
        position_size = await risk_service.calculate_position_size(
            symbol="RELIANCE",
            entry_price=2500.0,
            stop_loss=2400.0,
            account_balance=100000.0
        )
        
        assert position_size > 0
        assert position_size <= 100  # Should not exceed reasonable limits
    
    @pytest.mark.asyncio
    async def test_pnl_calculation(self, pnl_service):
        """Test PnL calculation and tracking"""
        # Initialize daily tracking
        await pnl_service.initialize_daily_tracking()
        
        # Simulate a trade
        await pnl_service.update_daily_pnl(
            realized_pnl=500.0,
            unrealized_pnl=200.0,
            fees=10.0
        )
        
        # Get daily report
        report = await pnl_service.get_daily_report()
        
        assert report["daily_pnl"] == 690.0  # 500 + 200 - 10
    
    @pytest.mark.asyncio
    async def test_report_generation(self, pnl_service, data_fetcher):
        """Test report generation integration"""
        report_service = ReportService(pnl_service, data_fetcher)
        
        # Generate daily report
        report = await report_service.generate_daily_report()
        
        assert "date" in report
        assert "daily_pnl" in report
        assert "generated_at" in report
    
    @pytest.mark.asyncio
    async def test_error_handling(self, mock_iifl_service, data_fetcher):
        """Test error handling across services"""
        # Simulate API failure
        mock_iifl_service.get_market_data.side_effect = Exception("API Error")
        
        # Should handle error gracefully
        with pytest.raises(Exception):
            await data_fetcher.get_live_price("RELIANCE")
    
    @pytest.mark.asyncio
    async def test_signal_lifecycle(self, strategy_service, risk_service):
        """Test complete signal lifecycle"""
        # Generate signal
        with patch.object(strategy_service.data_fetcher, 'get_historical_data') as mock_hist:
            mock_hist.return_value = [
                {"date": "2023-01-01", "close": 2400, "volume": 1000000},
                {"date": "2023-01-02", "close": 2500, "volume": 1100000},
            ]
            
            signals = await strategy_service.generate_signals("RELIANCE")
            
            if signals:
                signal = signals[0]
                
                # Validate signal with risk management
                is_valid = await risk_service.validate_signal(signal)
                
                # Should return boolean
                assert isinstance(is_valid, bool)

class TestAPIEndpoints:
    """Test API endpoint functionality"""
    
    def test_system_status_endpoint(self):
        """Test system status endpoint structure"""
        # This would test the actual API endpoints
        # For now, just verify the structure exists
        from api.system import router
        assert router is not None
    
    def test_signals_endpoint(self):
        """Test signals endpoint structure"""
        from api.signals import router
        assert router is not None
    
    def test_portfolio_endpoint(self):
        """Test portfolio endpoint structure"""
        from api.portfolio import router
        assert router is not None
    
    def test_reports_endpoint(self):
        """Test reports endpoint structure"""
        from api.reports import router
        assert router is not None

class TestDatabaseIntegration:
    """Test database operations"""
    
    @pytest.mark.asyncio
    async def test_database_connection(self):
        """Test database connection and basic operations"""
        from models.database import get_db, init_db
        
        # Initialize database
        await init_db()
        
        # Test connection
        async for db in get_db():
            assert db is not None
            break

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
