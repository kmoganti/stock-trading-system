"""
Unit tests for API Endpoints
Tests FastAPI routes, authentication, and response handling
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json
from fastapi.testclient import TestClient
from httpx import AsyncClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app
from api.auth import get_api_key
from services.iifl_api import IIFLAPIService


class TestAuthAPI:
    """Test suite for Authentication API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_auth_status(self, client):
        """Test authentication status endpoint"""
        response = client.get("/api/auth/status")

        assert response.status_code == 200
        data = response.json()
        assert "authenticated" in data

    def test_update_auth_code_invalid(self, client):
        """Test auth code update with invalid code"""
        response = client.post("/api/auth/update-auth-code", json={
            "auth_code": "short"  # Too short
        })

        assert response.status_code == 400

    def test_update_auth_code_missing(self, client):
        """Test auth code update with missing data"""
        response = client.post("/api/auth/update-auth-code", json={})

        assert response.status_code == 422

    def test_refresh_token(self, client):
        """Test token refresh endpoint"""
        response = client.post("/api/auth/refresh-token")

        # Should return success or failure, not authentication error
        assert response.status_code in [200, 400, 500]

    def test_test_connection(self, client):
        """Test connection endpoint"""
        response = client.post("/api/auth/test-connection")

        assert response.status_code in [200, 500]

    def test_validate_auth_code(self, client):
        """Test auth code validation"""
        response = client.post("/api/auth/validate-auth-code", json={
            "auth_code": "test_code_1234567890"
        })

        assert response.status_code in [200, 500]


class TestPortfolioAPI:
    """Test suite for Portfolio API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"X-API-Key": "test_api_key"}

    @pytest.fixture
    def mock_portfolio_data(self):
        """Mock portfolio data"""
        return {
            "holdings": [
                {
                    "symbol": "RELIANCE",
                    "quantity": 100,
                    "avg_price": 2500.00,
                    "current_price": 2550.00,
                    "pnl": 5000.00,
                    "pnl_percent": 2.0
                }
            ],
            "total_value": 255000.00,
            "total_pnl": 5000.00,
            "cash_balance": 50000.00
        }

    def test_get_portfolio_success(self, client, auth_headers, mock_portfolio_data):
        """Test successful portfolio retrieval"""
        with patch('api.portfolio.get_portfolio_data') as mock_get:
            mock_get.return_value = mock_portfolio_data
            
            response = client.get("/api/portfolio", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert "holdings" in data
            assert len(data["holdings"]) == 1
            assert data["total_value"] == 255000.00

    def test_get_portfolio_unauthorized(self, client):
        """Test portfolio retrieval without authentication"""
        response = client.get("/api/portfolio")

        assert response.status_code == 401

    def test_get_positions(self, client, auth_headers):
        """Test positions endpoint"""
        mock_positions = [
            {
                "symbol": "TCS",
                "quantity": 50,
                "avg_price": 3200.00,
                "side": "LONG",
                "pnl": 2500.00
            }
        ]

        with patch('api.portfolio.get_positions') as mock_get:
            mock_get.return_value = mock_positions
            
            response = client.get("/api/portfolio/positions", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["symbol"] == "TCS"

    def test_get_margin_info(self, client, auth_headers):
        """Test margin info endpoint"""
        mock_margin = {
            "available_margin": 50000.00,
            "used_margin": 25000.00,
            "total_margin": 75000.00
        }

        with patch('api.portfolio.get_margin_info') as mock_get:
            mock_get.return_value = mock_margin
            
            response = client.get("/api/portfolio/margin", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["available_margin"] == 50000.00


class TestOrdersAPI:
    """Test suite for Orders API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"X-API-Key": "test_api_key"}

    def test_place_order_success(self, client, auth_headers):
        """Test successful order placement"""
        order_data = {
            "symbol": "RELIANCE",
            "quantity": 100,
            "price": 2500.00,
            "order_type": "LIMIT",
            "side": "BUY"
        }

        mock_response = {
            "order_id": "ORDER123456",
            "status": "PENDING",
            "message": "Order placed successfully"
        }

        with patch('api.orders.place_order') as mock_place:
            mock_place.return_value = mock_response
            
            response = client.post("/api/orders", json=order_data, headers=auth_headers)

            assert response.status_code == 201
            data = response.json()
            assert data["order_id"] == "ORDER123456"

    def test_place_order_validation_error(self, client, auth_headers):
        """Test order placement with validation errors"""
        invalid_order = {
            "symbol": "RELIANCE",
            "quantity": -100,  # Invalid negative quantity
            "price": 2500.00,
            "order_type": "LIMIT",
            "side": "BUY"
        }

        response = client.post("/api/orders", json=invalid_order, headers=auth_headers)

        assert response.status_code == 422

    def test_cancel_order_success(self, client, auth_headers):
        """Test successful order cancellation"""
        with patch('api.orders.cancel_order') as mock_cancel:
            mock_cancel.return_value = True
            
            response = client.delete("/api/orders/ORDER123456", headers=auth_headers)

            assert response.status_code == 200
            assert response.json()["message"] == "Order cancelled successfully"

    def test_cancel_order_not_found(self, client, auth_headers):
        """Test cancelling non-existent order"""
        with patch('api.orders.cancel_order') as mock_cancel:
            mock_cancel.return_value = False
            
            response = client.delete("/api/orders/INVALID_ORDER", headers=auth_headers)

            assert response.status_code == 404

    def test_get_orders(self, client, auth_headers):
        """Test retrieving all orders"""
        mock_orders = [
            {
                "order_id": "ORDER1",
                "symbol": "RELIANCE",
                "status": "FILLED"
            },
            {
                "order_id": "ORDER2",
                "symbol": "TCS",
                "status": "PENDING"
            }
        ]

        with patch('api.orders.get_all_orders') as mock_get:
            mock_get.return_value = mock_orders
            
            response = client.get("/api/orders", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_order_status(self, client, auth_headers):
        """Test getting specific order status"""
        mock_order = {
            "order_id": "ORDER123456",
            "status": "FILLED",
            "filled_quantity": 100
        }

        with patch('api.orders.get_order_status') as mock_get:
            mock_get.return_value = mock_order
            
            response = client.get("/api/orders/ORDER123456", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "FILLED"


class TestSignalsAPI:
    """Test suite for Signals API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"X-API-Key": "test_api_key"}

    def test_get_signals(self, client, auth_headers):
        """Test retrieving signals"""
        mock_signals = [
            {
                "id": 1,
                "symbol": "RELIANCE",
                "signal_type": "BUY",
                "price": 2500.00,
                "confidence": 0.85,
                "created_at": "2025-10-21T10:30:00"
            }
        ]

        with patch('api.signals.get_signals') as mock_get:
            mock_get.return_value = mock_signals
            
            response = client.get("/api/signals", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["symbol"] == "RELIANCE"

    def test_get_signals_filtered(self, client, auth_headers):
        """Test retrieving signals with filters"""
        response = client.get(
            "/api/signals?symbol=RELIANCE&signal_type=BUY",
            headers=auth_headers
        )

        assert response.status_code == 200

    def test_create_signal(self, client, auth_headers):
        """Test creating a new signal"""
        signal_data = {
            "symbol": "TCS",
            "signal_type": "SELL",
            "price": 3200.00,
            "confidence": 0.75,
            "indicator_values": {"rsi": 75}
        }

        with patch('api.signals.create_signal') as mock_create:
            mock_create.return_value = {"id": 1, **signal_data}
            
            response = client.post("/api/signals", json=signal_data, headers=auth_headers)

            assert response.status_code == 201
            data = response.json()
            assert data["symbol"] == "TCS"


class TestWatchlistAPI:
    """Test suite for Watchlist API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"X-API-Key": "test_api_key"}

    def test_get_watchlists(self, client, auth_headers):
        """Test retrieving all watchlists"""
        mock_watchlists = [
            {
                "id": 1,
                "name": "Tech Stocks",
                "description": "Technology companies",
                "items": [
                    {"symbol": "TCS", "target_price": 3500.00}
                ]
            }
        ]

        with patch('api.watchlist.get_watchlists') as mock_get:
            mock_get.return_value = mock_watchlists
            
            response = client.get("/api/watchlist", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Tech Stocks"

    def test_create_watchlist(self, client, auth_headers):
        """Test creating a new watchlist"""
        watchlist_data = {
            "name": "Banking Stocks",
            "description": "Banking sector stocks"
        }

        with patch('api.watchlist.create_watchlist') as mock_create:
            mock_create.return_value = {"id": 1, **watchlist_data}
            
            response = client.post("/api/watchlist", json=watchlist_data, headers=auth_headers)

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "Banking Stocks"

    def test_add_watchlist_item(self, client, auth_headers):
        """Test adding item to watchlist"""
        item_data = {
            "symbol": "HDFC",
            "target_price": 1600.00,
            "stop_loss": 1400.00
        }

        with patch('api.watchlist.add_watchlist_item') as mock_add:
            mock_add.return_value = {"id": 1, "watchlist_id": 1, **item_data}
            
            response = client.post("/api/watchlist/1/items", json=item_data, headers=auth_headers)

            assert response.status_code == 201

    def test_delete_watchlist_item(self, client, auth_headers):
        """Test removing item from watchlist"""
        with patch('api.watchlist.delete_watchlist_item') as mock_delete:
            mock_delete.return_value = True
            
            response = client.delete("/api/watchlist/1/items/1", headers=auth_headers)

            assert response.status_code == 200


class TestSystemAPI:
    """Test suite for System API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/api/system/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_system_status(self, client):
        """Test system status endpoint"""
        mock_status = {
            "api_status": "online",
            "database_status": "connected",
            "iifl_api_status": "authenticated",
            "uptime": "2h 30m"
        }

        with patch('api.system.get_system_status') as mock_get:
            mock_get.return_value = mock_status
            
            response = client.get("/api/system/status")

            assert response.status_code == 200
            data = response.json()
            assert data["api_status"] == "online"

    def test_get_settings(self, client):
        """Test getting system settings"""
        auth_headers = {"X-API-Key": "test_api_key"}
        
        with patch('api.system.get_settings') as mock_get:
            mock_get.return_value = {"risk_limit": 10.0, "max_positions": 20}
            
            response = client.get("/api/system/settings", headers=auth_headers)

            assert response.status_code == 200

    def test_update_settings(self, client):
        """Test updating system settings"""
        auth_headers = {"X-API-Key": "test_api_key"}
        settings_data = {"risk_limit": 15.0}

        with patch('api.system.update_settings') as mock_update:
            mock_update.return_value = True
            
            response = client.put("/api/system/settings", json=settings_data, headers=auth_headers)

            assert response.status_code == 200


class TestReportsAPI:
    """Test suite for Reports API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers"""
        return {"X-API-Key": "test_api_key"}

    def test_get_pnl_report(self, client, auth_headers):
        """Test PnL report retrieval"""
        mock_report = {
            "date": "2025-10-21",
            "total_pnl": 1500.00,
            "realized_pnl": 1200.00,
            "unrealized_pnl": 300.00,
            "win_rate": 66.67
        }

        with patch('api.reports.get_pnl_report') as mock_get:
            mock_get.return_value = mock_report
            
            response = client.get("/api/reports/pnl", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert data["total_pnl"] == 1500.00

    def test_get_trade_history(self, client, auth_headers):
        """Test trade history retrieval"""
        mock_trades = [
            {
                "id": 1,
                "symbol": "RELIANCE",
                "pnl": 250.00,
                "trade_type": "LONG"
            }
        ]

        with patch('api.reports.get_trade_history') as mock_get:
            mock_get.return_value = mock_trades
            
            response = client.get("/api/reports/trades", headers=auth_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1


class TestErrorHandling:
    """Test suite for API error handling"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_404_not_found(self, client):
        """Test 404 error handling"""
        response = client.get("/api/nonexistent")

        assert response.status_code == 404

    def test_500_internal_error(self, client):
        """Test 500 error handling"""
        with patch('api.portfolio.get_portfolio_data') as mock_get:
            mock_get.side_effect = Exception("Database error")
            
            auth_headers = {"X-API-Key": "test_api_key"}
            response = client.get("/api/portfolio", headers=auth_headers)

            assert response.status_code == 500

    def test_rate_limiting(self, client):
        """Test rate limiting"""
        # Make multiple rapid requests
        responses = []
        for _ in range(10):
            response = client.get("/api/system/health")
            responses.append(response.status_code)

        # Should have some rate limiting (depends on implementation)
        assert all(status in [200, 429] for status in responses)


@pytest.mark.asyncio
class TestAsyncAPI:
    """Test suite for async API operations"""

    @pytest.fixture
    async def async_client(self):
        """Create async test client"""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_async_portfolio_retrieval(self, async_client):
        """Test async portfolio data retrieval"""
        headers = {"X-API-Key": "test_api_key"}
        
        with patch('api.portfolio.get_portfolio_data') as mock_get:
            mock_get.return_value = {"holdings": []}
            
            response = await async_client.get("/api/portfolio", headers=headers)

            assert response.status_code == 200

    async def test_concurrent_requests(self, async_client):
        """Test handling of concurrent requests"""
        headers = {"X-API-Key": "test_api_key"}
        
        # Make concurrent requests
        tasks = [
            async_client.get("/api/system/health"),
            async_client.get("/api/system/health"),
            async_client.get("/api/system/health")
        ]

        responses = await asyncio.gather(*tasks)

        assert all(r.status_code == 200 for r in responses)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])