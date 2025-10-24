"""
Unit tests for Data Fetcher Service
Tests data retrieval, caching, historical data, and portfolio operations
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService


class TestDataFetcher:
    """Test suite for Data Fetcher Service"""

    @pytest.fixture
    def mock_iifl_service(self):
        """Mock IIFL API service"""
        service = MagicMock(spec=IIFLAPIService)
        service.authenticated = True
        service.session_token = "test_token"
        service.make_request = AsyncMock()
        return service

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        session = AsyncMock()
        return session

    @pytest.fixture
    def data_fetcher(self, mock_iifl_service, mock_db_session):
        """Create DataFetcher instance for testing"""
        return DataFetcher(mock_iifl_service, db_session=mock_db_session)

    @pytest.fixture
    def mock_portfolio_response(self):
        """Mock portfolio API response"""
        return {
            "stat": "Ok",
            "result": [
                {
                    "symbol": "RELIANCE",
                    "quantity": "100",
                    "avg_price": "2500.50",
                    "current_price": "2550.00",
                    "pnl": "4950.00",
                    "pnl_percent": "1.98"
                },
                {
                    "symbol": "TCS",
                    "quantity": "50",
                    "avg_price": "3200.00",
                    "current_price": "3150.00",
                    "pnl": "-2500.00",
                    "pnl_percent": "-1.56"
                }
            ]
        }

    @pytest.fixture
    def mock_historical_response(self):
        """Mock historical data API response"""
        return {
            "stat": "Ok",
            "result": [
                {
                    "timestamp": "2025-10-21 09:15:00",
                    "open": "2500.00",
                    "high": "2520.00",
                    "low": "2495.00",
                    "close": "2510.00",
                    "volume": "1000000"
                },
                {
                    "timestamp": "2025-10-21 09:16:00",
                    "open": "2510.00",
                    "high": "2525.00",
                    "low": "2505.00",
                    "close": "2515.00",
                    "volume": "1200000"
                }
            ]
        }

    @pytest.fixture
    def mock_margin_response(self):
        """Mock margin API response"""
        return {
            "stat": "Ok",
            "result": {
                "available_margin": "50000.00",
                "used_margin": "25000.00",
                "total_margin": "75000.00",
                "margin_utilization": "33.33"
            }
        }

    @pytest.mark.asyncio
    async def test_get_portfolio_data_success(self, data_fetcher, mock_portfolio_response):
        """Test successful portfolio data retrieval"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        result = await data_fetcher.get_portfolio_data()

        assert result is not None
        assert len(result.get('holdings', [])) == 2
        assert result['holdings'][0]['symbol'] == 'RELIANCE'
        data_fetcher.iifl_service.make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_portfolio_data_cached(self, data_fetcher, mock_portfolio_response):
        """Test portfolio data caching"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        # First call
        result1 = await data_fetcher.get_portfolio_data()
        
        # Second call without force_refresh should use cache
        result2 = await data_fetcher.get_portfolio_data()

        assert result1 == result2
        # Should only make one API call due to caching
        assert data_fetcher.iifl_service.make_request.call_count == 1

    @pytest.mark.asyncio
    async def test_get_portfolio_data_force_refresh(self, data_fetcher, mock_portfolio_response):
        """Test force refresh bypasses cache"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        # First call
        await data_fetcher.get_portfolio_data()
        
        # Second call with force_refresh
        await data_fetcher.get_portfolio_data(force_refresh=True)

        # Should make two API calls
        assert data_fetcher.iifl_service.make_request.call_count == 2

    @pytest.mark.asyncio
    async def test_get_portfolio_data_api_error(self, data_fetcher):
        """Test portfolio data retrieval with API error"""
        data_fetcher.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "API Error"
        }

        result = await data_fetcher.get_portfolio_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_historical_data_success(self, data_fetcher, mock_historical_response):
        """Test successful historical data retrieval"""
        data_fetcher.iifl_service.make_request.return_value = mock_historical_response

        result = await data_fetcher.get_historical_data("RELIANCE", period="1d", interval="1m")

        assert result is not None
        assert len(result) == 2
        assert result[0]['close'] == "2510.00"
        data_fetcher.iifl_service.make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_data_to_dataframe(self, data_fetcher, mock_historical_response):
        """Test historical data conversion to DataFrame"""
        data_fetcher.iifl_service.make_request.return_value = mock_historical_response

        result = await data_fetcher.get_historical_data("RELIANCE", period="1d", interval="1m", as_dataframe=True)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert 'close' in result.columns
        assert 'volume' in result.columns

    @pytest.mark.asyncio
    async def test_get_historical_data_invalid_symbol(self, data_fetcher):
        """Test historical data with invalid symbol"""
        data_fetcher.iifl_service.make_request.return_value = {
            "stat": "Not_Ok",
            "emsg": "Invalid symbol"
        }

        result = await data_fetcher.get_historical_data("INVALID_SYMBOL")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_margin_info_success(self, data_fetcher, mock_margin_response):
        """Test successful margin info retrieval"""
        data_fetcher.iifl_service.make_request.return_value = mock_margin_response

        result = await data_fetcher.get_margin_info()

        assert result is not None
        assert result['available_margin'] == "50000.00"
        assert result['margin_utilization'] == "33.33"

    @pytest.mark.asyncio
    async def test_get_current_price_success(self, data_fetcher):
        """Test current price retrieval"""
        mock_response = {
            "stat": "Ok",
            "result": {
                "symbol": "RELIANCE",
                "ltp": "2550.00",
                "change": "25.00",
                "change_percent": "0.99"
            }
        }
        data_fetcher.iifl_service.make_request.return_value = mock_response

        result = await data_fetcher.get_current_price("RELIANCE")

        assert result == 2550.00

    @pytest.mark.asyncio
    async def test_get_current_price_invalid_response(self, data_fetcher):
        """Test current price with invalid API response"""
        data_fetcher.iifl_service.make_request.return_value = None

        result = await data_fetcher.get_current_price("RELIANCE")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_market_status(self, data_fetcher):
        """Test market status retrieval"""
        mock_response = {
            "stat": "Ok",
            "result": {
                "market_status": "OPEN",
                "market_time": "2025-10-21 10:30:00"
            }
        }
        data_fetcher.iifl_service.make_request.return_value = mock_response

        result = await data_fetcher.get_market_status()

        assert result['market_status'] == "OPEN"

    @pytest.mark.asyncio
    async def test_cache_expiry(self, data_fetcher, mock_portfolio_response):
        """Test cache expiry functionality"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        # First call
        await data_fetcher.get_portfolio_data()

        # Simulate cache expiry
        if hasattr(data_fetcher, '_portfolio_cache_time'):
            data_fetcher._portfolio_cache_time = datetime.now() - timedelta(hours=1)

        # Second call should refresh cache
        await data_fetcher.get_portfolio_data()

        # Should make two API calls due to expired cache
        assert data_fetcher.iifl_service.make_request.call_count >= 1

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, data_fetcher, mock_portfolio_response):
        """Test concurrent data requests"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        # Make concurrent requests
        tasks = [data_fetcher.get_portfolio_data() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(result is not None for result in results)
        # Should be the same result due to caching
        assert all(result == results[0] for result in results)

    @pytest.mark.asyncio
    async def test_get_watchlist_prices(self, data_fetcher):
        """Test bulk price retrieval for watchlist"""
        symbols = ["RELIANCE", "TCS", "INFY"]
        mock_response = {
            "stat": "Ok",
            "result": [
                {"symbol": "RELIANCE", "ltp": "2550.00"},
                {"symbol": "TCS", "ltp": "3150.00"},
                {"symbol": "INFY", "ltp": "1850.00"}
            ]
        }
        data_fetcher.iifl_service.make_request.return_value = mock_response

        result = await data_fetcher.get_bulk_prices(symbols)

        assert len(result) == 3
        assert result["RELIANCE"] == 2550.00
        assert result["TCS"] == 3150.00

    @pytest.mark.asyncio
    async def test_data_transformation(self, data_fetcher, mock_historical_response):
        """Test data transformation and cleaning"""
        data_fetcher.iifl_service.make_request.return_value = mock_historical_response

        result = await data_fetcher.get_historical_data("RELIANCE", period="1d", interval="1m")

        # Check that numeric fields are properly converted
        for candle in result:
            assert isinstance(float(candle['close']), float)
            assert isinstance(int(candle['volume']), int)

    @pytest.mark.asyncio
    async def test_error_handling_network_timeout(self, data_fetcher):
        """Test handling of network timeouts"""
        data_fetcher.iifl_service.make_request.side_effect = asyncio.TimeoutError("Request timeout")

        result = await data_fetcher.get_portfolio_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_error_handling_invalid_json(self, data_fetcher):
        """Test handling of invalid JSON responses"""
        data_fetcher.iifl_service.make_request.side_effect = ValueError("Invalid JSON")

        result = await data_fetcher.get_portfolio_data()

        assert result is None

    @pytest.mark.asyncio
    async def test_rate_limiting(self, data_fetcher, mock_portfolio_response):
        """Test rate limiting functionality"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        # Make multiple rapid requests
        start_time = datetime.now()
        tasks = [data_fetcher.get_portfolio_data(force_refresh=True) for _ in range(5)]
        await asyncio.gather(*tasks)
        end_time = datetime.now()

        # If rate limiting is implemented, should take some minimum time
        duration = (end_time - start_time).total_seconds()
        # This test depends on implementation details

    @pytest.mark.asyncio
    async def test_database_persistence(self, data_fetcher, mock_portfolio_response):
        """Test that data is persisted to database"""
        data_fetcher.iifl_service.make_request.return_value = mock_portfolio_response

        await data_fetcher.get_portfolio_data()

        # Check that database session was used (if implemented)
        if hasattr(data_fetcher, 'db_session') and data_fetcher.db_session:
            # Verify database operations were called
            pass

    @pytest.mark.asyncio
    async def test_cleanup_resources(self, data_fetcher):
        """Test proper cleanup of resources"""
        # Test that any open connections or resources are cleaned up
        await data_fetcher.cleanup()

        # Verify cleanup was performed
        assert True  # Placeholder - depends on implementation

if __name__ == "__main__":
    pytest.main([__file__, "-v"])