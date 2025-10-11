import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, date
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
from services.backtest import BacktestService
from services.logging_service import TradingLogger

class TestIIFLAPIService:
    """Test IIFL API service"""
    
    @pytest.fixture
    def api_service(self):
        return IIFLAPIService()
    
    @pytest.mark.asyncio
    async def test_authenticate(self, api_service):
        """Test authentication"""
        with patch('httpx.AsyncClient.post') as mock_post:
            # Create a proper mock response
            mock_response = Mock()
            mock_response.json.return_value = {
                "stat": "Ok", 
                "sessionToken": "test_token"
            }
            mock_response.status_code = 200
            mock_response.text = '{"stat": "Ok", "sessionToken": "test_token"}'
            mock_response.headers = {}
            mock_response.raise_for_status.return_value = None
            
            # Make the post method return the mock response
            mock_post.return_value = mock_response

            result = await api_service.authenticate("client_id", "auth_code", "secret")
            assert result["access_token"] == "test_token"

    @pytest.mark.asyncio
    async def test_get_market_data(self, api_service):
        """Test market data retrieval"""
        api_service.session_token = "test_token"
        
        # Mock the get_market_quotes method that get_market_data calls
        with patch.object(api_service, 'get_market_quotes') as mock_quotes:
            mock_quotes.return_value = {
                "status": "Ok",
                "resultData": [{
                    "symbol": "RELIANCE",
                    "ltp": 2500.0,
                    "change": 25.0,
                    "volume": 1000000
                }]
            }
            
            result = await api_service.get_market_data("RELIANCE")
            assert result["Symbol"] == "RELIANCE"
            assert result["LastTradedPrice"] == 2500.0
    
    @pytest.mark.asyncio
    async def test_place_order(self, api_service):
        """Test order placement"""
        api_service.session_token = "test_token"
        
        # Mock the _make_api_request method that place_order calls
        with patch.object(api_service, '_make_api_request') as mock_request:
            mock_request.return_value = {
                "Status": "Ok",
                "OrderId": "ORD123"
            }
            
            order_data = {
                "symbol": "RELIANCE",
                "quantity": 10,
                "price": 2500.0,
                "order_type": "BUY"
            }
            
            result = await api_service.place_order(order_data)
            assert result["OrderId"] == "ORD123"

class TestDataFetcher:
    """Test data fetcher service"""
    
    @pytest.fixture
    def mock_iifl_service(self):
        service = Mock(spec=IIFLAPIService)
        service.get_market_data = AsyncMock()
        service.get_historical_data = AsyncMock()
        return service
    
    @pytest.fixture
    def data_fetcher(self, mock_iifl_service):
        return DataFetcher(mock_iifl_service, test_mode=True)
    
    @pytest.mark.asyncio
    async def test_get_live_price(self, data_fetcher, mock_iifl_service):
        """Test live price fetching"""
        mock_iifl_service.get_market_data.return_value = {
            "Symbol": "RELIANCE",
            "LastTradedPrice": 2500.0,
            "Change": 25.0
        }
        
        result = await data_fetcher.get_live_price("RELIANCE")
        assert result == 2500.0
        mock_iifl_service.get_market_data.assert_called_once_with("RELIANCE")
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self, data_fetcher, mock_iifl_service):
        """Test historical data fetching"""
        # Mock the IIFL API response format
        mock_iifl_service.get_historical_data.return_value = {
            "status": "ok",
            "result": [
                {"date": "2023-01-01", "close": 2400.0, "volume": 1000000},
                {"date": "2023-01-02", "close": 2450.0, "volume": 1100000},
                {"date": "2023-01-03", "close": 2500.0, "volume": 1200000}
            ]
        }
        
        result = await data_fetcher.get_historical_data("RELIANCE", "1D", 30)
        assert len(result) == 3
        assert result[0]["close"] == 2400.0
        mock_iifl_service.get_historical_data.assert_called_once()

class TestStrategyService:
    """Test strategy service"""
    
    @pytest.fixture
    def mock_data_fetcher(self):
        fetcher = Mock(spec=DataFetcher)
        fetcher.get_historical_data = AsyncMock()
        fetcher.get_live_price = AsyncMock()
        return fetcher
    
    @pytest.fixture
    def strategy_service(self, mock_data_fetcher):
        return StrategyService(mock_data_fetcher)
    
    @pytest.mark.asyncio
    async def test_generate_signals(self, strategy_service, mock_data_fetcher):
        """Test signal generation"""
        mock_data_fetcher.get_historical_data.return_value = [
            {"date": "2023-01-01", "close": 2400.0, "volume": 1000000},
            {"date": "2023-01-02", "close": 2450.0, "volume": 1100000},
            {"date": "2023-01-03", "close": 2500.0, "volume": 1200000}
        ]
        mock_data_fetcher.get_live_price.return_value = 2520.0
        
        signals = await strategy_service.generate_signals("RELIANCE")
        assert isinstance(signals, list)
    
    @pytest.mark.asyncio
    async def test_momentum_strategy(self, strategy_service):
        """Test momentum strategy"""
        historical_data = [
            {"close": 2400.0, "volume": 1000000},
            {"close": 2450.0, "volume": 1100000},
            {"close": 2500.0, "volume": 1200000},
            {"close": 2520.0, "volume": 1300000}
        ]
        
        signal = await strategy_service.momentum_strategy("RELIANCE", historical_data)
        assert signal is None or isinstance(signal, dict)
        if signal:
            assert "signal_type" in signal
            assert signal["signal_type"] in ["buy", "sell"]

class TestRiskService:
    """Test risk management service"""
    
    @pytest.fixture
    def risk_service(self):
        return RiskService()
    
    @pytest.mark.asyncio
    async def test_calculate_position_size(self, risk_service):
        """Test position size calculation"""
        position_size = await risk_service.calculate_position_size(
            symbol="RELIANCE",
            entry_price=2500.0,
            stop_loss=2400.0,
            account_balance=100000.0
        )
        
        assert position_size > 0
        assert position_size <= 100  # Reasonable limit
    
    @pytest.mark.asyncio
    async def test_validate_signal(self, risk_service):
        """Test signal validation"""
        signal = {
            "symbol": "RELIANCE",
            "signal_type": "buy",
            "price": 2500.0,
            "quantity": 10,
            "stop_loss": 2400.0
        }
        
        with patch.object(risk_service, 'get_current_positions') as mock_positions:
            mock_positions.return_value = []
            
            is_valid = await risk_service.validate_signal(signal)
            assert isinstance(is_valid, bool)
    
    @pytest.mark.asyncio
    async def test_calculate_var(self, risk_service):
        """Test VaR calculation"""
        returns = [-0.02, 0.01, -0.01, 0.03, -0.015, 0.02, -0.005]
        var_95 = await risk_service.calculate_var(returns, 0.95)
        
        assert isinstance(var_95, float)
        assert var_95 < 0  # VaR should be negative

class TestOrderManager:
    """Test order manager service"""
    
    @pytest.fixture
    def mock_iifl_service(self):
        service = Mock(spec=IIFLAPIService)
        service.place_order = AsyncMock()
        service.cancel_order = AsyncMock()
        service.get_order_status = AsyncMock()
        return service
    
    @pytest.fixture
    def order_manager(self, mock_iifl_service):
        return OrderManager(mock_iifl_service)
    
    @pytest.mark.asyncio
    async def test_place_order(self, order_manager, mock_iifl_service):
        """Test order placement"""
        mock_iifl_service.place_order.return_value = {
            "OrderId": "ORD123",
            "Status": "COMPLETE",
            "AvgPrice": 2500.0
        }
        
        signal = {
            "symbol": "RELIANCE",
            "signal_type": "buy",
            "price": 2500.0,
            "quantity": 10
        }
        
        result = await order_manager.place_order(signal)
        assert result["OrderId"] == "ORD123"
        assert result["Status"] == "COMPLETE"
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, order_manager, mock_iifl_service):
        """Test order cancellation"""
        mock_iifl_service.cancel_order.return_value = {
            "Success": True,
            "Message": "Order cancelled"
        }
        
        result = await order_manager.cancel_order("ORD123")
        assert result["Success"] is True

class TestPnLService:
    """Test PnL service"""
    
    @pytest.fixture
    def pnl_service(self):
        return PnLService()
    
    @pytest.mark.asyncio
    async def test_initialize_daily_tracking(self, pnl_service):
        """Test daily tracking initialization"""
        await pnl_service.initialize_daily_tracking()
        # Should not raise any exceptions
        assert True
    
    @pytest.mark.asyncio
    async def test_update_daily_pnl(self, pnl_service):
        """Test daily PnL update"""
        await pnl_service.initialize_daily_tracking()
        
        await pnl_service.update_daily_pnl(
            realized_pnl=500.0,
            unrealized_pnl=200.0,
            fees=10.0
        )
        
        report = await pnl_service.get_daily_report()
        assert report["daily_pnl"] == 690.0  # 500 + 200 - 10
    
    @pytest.mark.asyncio
    async def test_calculate_portfolio_pnl(self, pnl_service):
        """Test portfolio PnL calculation"""
        positions = [
            {
                "symbol": "RELIANCE",
                "quantity": 10,
                "avg_price": 2500.0,
                "current_price": 2550.0
            },
            {
                "symbol": "TCS",
                "quantity": 5,
                "avg_price": 3000.0,
                "current_price": 2950.0
            }
        ]
        
        total_pnl = await pnl_service.calculate_portfolio_pnl(positions)
        expected_pnl = (10 * (2550 - 2500)) + (5 * (2950 - 3000))
        assert total_pnl == expected_pnl

class TestReportService:
    """Test report service"""
    
    @pytest.fixture
    def mock_pnl_service(self):
        service = Mock(spec=PnLService)
        service.get_daily_report = AsyncMock()
        return service
    
    @pytest.fixture
    def mock_data_fetcher(self):
        fetcher = Mock(spec=DataFetcher)
        fetcher.get_portfolio_summary = AsyncMock()
        return fetcher
    
    @pytest.fixture
    def report_service(self, mock_pnl_service, mock_data_fetcher):
        return ReportService(mock_pnl_service, mock_data_fetcher)
    
    @pytest.mark.asyncio
    async def test_generate_daily_report(self, report_service, mock_pnl_service):
        """Test daily report generation"""
        mock_pnl_service.get_daily_report.return_value = {
            "date": "2023-01-01",
            "daily_pnl": 1500.0,
            "trades_count": 5,
            "win_rate": 0.8
        }
        
        report = await report_service.generate_daily_report()
        assert report["date"] == "2023-01-01"
        assert report["daily_pnl"] == 1500.0
        assert "generated_at" in report
    
    @pytest.mark.asyncio
    async def test_generate_monthly_report(self, report_service, mock_pnl_service):
        """Test monthly report generation"""
        mock_pnl_service.get_monthly_summary.return_value = {
            "month": "2023-01",
            "monthly_pnl": 15000.0,
            "total_trades": 50,
            "win_rate": 0.75
        }
        
        with patch.object(mock_pnl_service, 'get_monthly_summary'):
            mock_pnl_service.get_monthly_summary.return_value = {
                "month": "2023-01",
                "monthly_pnl": 15000.0,
                "total_trades": 50,
                "win_rate": 0.75
            }
            
            report = await report_service.generate_monthly_report("2023-01")
            assert report["month"] == "2023-01"
            assert report["monthly_pnl"] == 15000.0

class TestBacktestService:
    """Test backtest service"""
    
    @pytest.fixture
    def mock_data_fetcher(self):
        fetcher = Mock(spec=DataFetcher)
        fetcher.get_historical_data = AsyncMock()
        fetcher.get_historical_data_df = AsyncMock()
        
        # Setup mock to return proper DataFrame with enough data for backtesting
        import pandas as pd
        from datetime import datetime, timedelta
        
        # Generate 60 days of mock data to satisfy backtest requirements
        base_date = datetime.strptime("2023-01-01", "%Y-%m-%d")
        mock_df_data = []
        base_price = 2400.0
        
        for i in range(60):
            date_str = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            price_change = (i * 2) + (10 if i % 7 == 0 else 5)  # Add some variation
            close_price = base_price + price_change
            
            mock_df_data.append({
                "date": date_str,
                "close": close_price,
                "volume": 1000000 + (i * 10000),
                "high": close_price + 20,
                "low": close_price - 20,
                "open": close_price - 10
            })
        
        mock_df = pd.DataFrame(mock_df_data)
        mock_df['date'] = pd.to_datetime(mock_df['date'])
        mock_df.set_index('date', inplace=True)
        
        fetcher.get_historical_data_df.return_value = mock_df
        return fetcher
    
    @pytest.fixture
    def mock_strategy_service(self):
        strategy = Mock(spec=StrategyService)
        strategy.generate_signals = AsyncMock()
        return strategy
    
    @pytest.fixture
    def backtest_service(self, mock_data_fetcher, mock_strategy_service):
        return BacktestService(mock_data_fetcher, mock_strategy_service)
    
    @pytest.mark.asyncio
    async def test_run_backtest(self, backtest_service, mock_data_fetcher, mock_strategy_service):
        """Test backtest execution"""
        mock_data_fetcher.get_historical_data.return_value = [
            {"date": "2023-01-01", "close": 2400.0, "volume": 1000000},
            {"date": "2023-01-02", "close": 2450.0, "volume": 1100000},
            {"date": "2023-01-03", "close": 2500.0, "volume": 1200000}
        ]
        
        # Mock calculate_indicators to return the DataFrame unchanged
        mock_strategy_service.calculate_indicators.return_value = mock_data_fetcher.get_historical_data_df.return_value
        
        mock_strategy_service.generate_signals.return_value = [
            {
                "signal_type": "buy",
                "symbol": "RELIANCE", 
                "price": 2450.0,
                "quantity": 10
            }
        ]
        
        config = {
            "start_date": "2023-01-01",
            "end_date": "2023-02-28",  # Longer range to get enough data
            "initial_capital": 100000.0,
            "symbols": ["RELIANCE"]
        }
        
        result = await backtest_service.run_backtest(config)
        assert "metrics" in result
        assert "total_return" in result["metrics"]
        assert "sharpe_ratio" in result["metrics"]
        assert "max_drawdown" in result["metrics"]

class TestTradingLogger:
    """Test trading logger service"""
    
    @pytest.fixture
    def trading_logger(self):
        return TradingLogger()
    
    def test_log_trade(self, trading_logger):
        """Test trade logging"""
        # Should not raise any exceptions
        trading_logger.log_trade(
            signal_id="SIG_001",
            action="BUY",
            symbol="RELIANCE",
            quantity=10,
            price=2500.0
        )
        assert True
    
    def test_log_error(self, trading_logger):
        """Test error logging"""
        try:
            raise ValueError("Test error")
        except Exception as e:
            # Should not raise any exceptions
            trading_logger.log_error("test_component", e)
            assert True
    
    def test_log_risk_event(self, trading_logger):
        """Test risk event logging"""
        # Should not raise any exceptions
        trading_logger.log_risk_event(
            event_type="POSITION_LIMIT_EXCEEDED",
            severity="HIGH",
            description="Position limit exceeded for RELIANCE",
            details={"current_positions": 15, "limit": 10}
        )
        assert True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
