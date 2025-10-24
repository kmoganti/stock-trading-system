import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from api import (
    system_router, signals_router, portfolio_router, 
    risk_router, reports_router, backtest_router, settings_router
)
from api.auth_management import router as auth_router
from api.watchlist import router as watchlist_router

# Create test app
app = FastAPI()
app.include_router(system_router)
app.include_router(signals_router)
app.include_router(portfolio_router)
app.include_router(risk_router)
app.include_router(reports_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(auth_router)
app.include_router(watchlist_router)

client = TestClient(app)

class TestSystemAPI:
    """Test system API endpoints"""
    
    def test_system_status(self):
        """Test system status endpoint"""
        response = client.get("/api/system/status")
        assert response.status_code == 200
        data = response.json()
        assert "auto_trade" in data
        assert "environment" in data
        assert "timestamp" in data
    
    def test_system_halt(self):
        """Test system halt endpoint"""
        response = client.post("/api/system/halt")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Trading halted successfully"
        assert data["status"] == "halted"
    
    def test_system_resume(self):
        """Test system resume endpoint"""
        response = client.post("/api/system/resume")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Trading resumed successfully"
        assert data["status"] == "active"

class TestSignalsAPI:
    """Test signals API endpoints"""
    
    def test_get_signals(self):
        """Test get signals endpoint"""
        with patch('api.signals.get_signals') as mock_get:
            mock_get.return_value = [
                {
                    "id": 1,
                    "symbol": "RELIANCE",
                    "signal_type": "buy",
                    "price": 2500.0,
                    "quantity": 10,
                    "status": "pending"
                }
            ]
            
            response = client.get("/api/signals")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["symbol"] == "RELIANCE"
    
    def test_create_signal(self):
        """Test create signal endpoint"""
        signal_data = {
            "symbol": "RELIANCE",
            "signal_type": "buy",
            "price": 2500.0,
            "quantity": 10,
            "stop_loss": 2400.0,
            "take_profit": 2600.0,
            "reason": "Technical breakout"
        }
        
        with patch('api.signals.create_signal') as mock_create:
            mock_create.return_value = {"id": 1, **signal_data, "status": "pending"}
            
            response = client.post("/api/signals", json=signal_data)
            assert response.status_code == 200
            data = response.json()
            assert data["symbol"] == "RELIANCE"
            assert data["status"] == "pending"
    
    def test_approve_signal(self):
        """Test approve signal endpoint"""
        with patch('api.signals.approve_signal') as mock_approve:
            mock_approve.return_value = {"success": True, "message": "Signal approved"}
            
            response = client.post("/api/signals/1/approve")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    def test_reject_signal(self):
        """Test reject signal endpoint"""
        with patch('api.signals.reject_signal') as mock_reject:
            mock_reject.return_value = {"success": True, "message": "Signal rejected"}
            
            response = client.post("/api/signals/1/reject")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

class TestPortfolioAPI:
    """Test portfolio API endpoints"""
    
    def test_get_portfolio_summary(self):
        """Test portfolio summary endpoint"""
        with patch('api.portfolio.get_portfolio_summary') as mock_summary:
            mock_summary.return_value = {
                "total_equity": 150000.0,
                "available_margin": 75000.0,
                "used_margin": 25000.0,
                "total_pnl": 5000.0
            }
            
            response = client.get("/api/portfolio/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["total_equity"] == 150000.0
            assert "available_margin" in data
    
    def test_get_positions(self):
        """Test get positions endpoint"""
        with patch('api.portfolio.get_positions') as mock_positions:
            mock_positions.return_value = {
                "positions": [
                    {
                        "symbol": "RELIANCE",
                        "quantity": 10,
                        "avg_price": 2500.0,
                        "ltp": 2550.0,
                        "pnl": 500.0
                    }
                ],
                "total_pnl": 500.0
            }
            
            response = client.get("/api/portfolio/positions")
            assert response.status_code == 200
            data = response.json()
            assert len(data["positions"]) == 1
            assert data["total_pnl"] == 500.0
    
    def test_get_holdings(self):
        """Test get holdings endpoint"""
        with patch('api.portfolio.get_holdings') as mock_holdings:
            mock_holdings.return_value = {
                "holdings": [
                    {
                        "symbol": "TCS",
                        "quantity": 5,
                        "avg_price": 3000.0,
                        "ltp": 3100.0,
                        "market_value": 15500.0,
                        "pnl": 500.0
                    }
                ]
            }
            
            response = client.get("/api/portfolio/holdings")
            assert response.status_code == 200
            data = response.json()
            assert len(data["holdings"]) == 1
            assert data["holdings"][0]["symbol"] == "TCS"

class TestRiskAPI:
    """Test risk management API endpoints"""
    
    def test_get_risk_metrics(self):
        """Test risk metrics endpoint"""
        with patch('api.risk.get_risk_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "daily_pnl": 1000.0,
                "max_drawdown": -2000.0,
                "var_95": -1500.0,
                "position_count": 5,
                "margin_utilization": 0.6
            }
            
            response = client.get("/api/risk/metrics")
            assert response.status_code == 200
            data = response.json()
            assert data["daily_pnl"] == 1000.0
            assert "max_drawdown" in data
    
    def test_validate_signal(self):
        """Test signal validation endpoint"""
        signal_data = {
            "symbol": "RELIANCE",
            "signal_type": "buy",
            "price": 2500.0,
            "quantity": 10,
            "stop_loss": 2400.0
        }
        
        with patch('api.risk.validate_signal') as mock_validate:
            mock_validate.return_value = {
                "valid": True,
                "risk_score": 0.3,
                "position_size": 10,
                "margin_required": 25000.0
            }
            
            response = client.post("/api/risk/validate", json=signal_data)
            assert response.status_code == 200
            data = response.json()
            assert data["valid"] is True
            assert "risk_score" in data

class TestReportsAPI:
    """Test reports API endpoints"""
    
    def test_get_daily_report(self):
        """Test daily report endpoint"""
        with patch('api.reports.get_daily_report') as mock_report:
            mock_report.return_value = {
                "date": "2023-01-01",
                "daily_pnl": 1500.0,
                "trades_count": 5,
                "win_rate": 0.8,
                "total_fees": 50.0
            }
            
            response = client.get("/api/reports/daily/2023-01-01")
            assert response.status_code == 200
            data = response.json()
            assert data["date"] == "2023-01-01"
            assert data["daily_pnl"] == 1500.0
    
    def test_generate_eod_report(self):
        """Test EOD report generation endpoint"""
        with patch('api.reports.generate_eod_report') as mock_generate:
            mock_generate.return_value = {"success": True, "report_id": "EOD_20230101"}
            
            response = client.post("/api/reports/eod/generate")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "report_id" in data

class TestBacktestAPI:
    """Test backtest API endpoints"""
    
    def test_run_backtest(self):
        """Test backtest execution endpoint"""
        backtest_config = {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 100000.0,
            "strategy": "momentum",
            "symbols": ["RELIANCE", "TCS"]
        }
        
        with patch('api.backtest.run_backtest') as mock_backtest:
            mock_backtest.return_value = {
                "backtest_id": "BT_001",
                "status": "running",
                "message": "Backtest started successfully"
            }
            
            response = client.post("/api/backtest/run", json=backtest_config)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert "backtest_id" in data
    
    def test_get_backtest_results(self):
        """Test backtest results endpoint"""
        with patch('api.backtest.get_backtest_results') as mock_results:
            mock_results.return_value = {
                "backtest_id": "BT_001",
                "status": "completed",
                "total_return": 0.15,
                "sharpe_ratio": 1.2,
                "max_drawdown": -0.08,
                "trades_count": 25
            }
            
            response = client.get("/api/backtest/BT_001/results")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"
            assert data["total_return"] == 0.15

class TestSettingsAPI:
    """Test settings API endpoints"""
    
    def test_get_settings(self):
        """Test get settings endpoint"""
        with patch('api.settings.get_settings') as mock_get:
            mock_get.return_value = {
                "auto_trade": False,
                "risk_per_trade": 0.02,
                "max_positions": 10,
                "signal_timeout": 300
            }
            
            response = client.get("/api/settings")
            assert response.status_code == 200
            data = response.json()
            assert "auto_trade" in data
            assert data["risk_per_trade"] == 0.02
    
    def test_update_settings(self):
        """Test update settings endpoint"""
        settings_data = {
            "auto_trade": True,
            "risk_per_trade": 0.025,
            "max_positions": 15
        }
        
        with patch('api.settings.update_settings') as mock_update:
            mock_update.return_value = {"success": True, "message": "Settings updated"}
            
            response = client.put("/api/settings", json=settings_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True

class TestAuthAPI:
    """Test authentication API endpoints"""
    
    def test_get_auth_status(self):
        """Test authentication status endpoint"""
        with patch('api.auth_management.get_auth_status') as mock_status:
            mock_status.return_value = {
                "authenticated": True,
                "client_id": "test_client",
                "expires_at": "2023-12-31T23:59:59"
            }
            
            response = client.get("/api/auth/status")
            assert response.status_code == 200
            data = response.json()
            assert data["authenticated"] is True
    
    def test_authenticate(self):
        """Test authentication endpoint"""
        auth_data = {
            "client_id": "test_client",
            "auth_code": "test_auth",
            "app_secret": "test_secret"
        }
        
        with patch('api.auth_management.authenticate') as mock_auth:
            mock_auth.return_value = {
                "success": True,
                "token": "test_token",
                "expires_at": "2023-12-31T23:59:59"
            }
            
            response = client.post("/api/auth/authenticate", json=auth_data)
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "token" in data

class TestWatchlistAPI:
    """Test watchlist API endpoints with categories"""

    def test_get_watchlist_default(self):
        """Test get watchlist without category (should work)"""
        with patch('services.watchlist.WatchlistService.get_watchlist') as mock_get:
            mock_get.return_value = ["RELIANCE", "TCS"]
            response = client.get("/api/watchlist")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_watchlist_by_category(self):
        """Test get watchlist filtered by category"""
        with patch('services.watchlist.WatchlistService.get_watchlist') as mock_get:
            mock_get.return_value = ["RELIANCE", "TCS"]
            response = client.get("/api/watchlist?category=long_term")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_add_symbols_with_category(self):
        """Test adding symbols with a category"""
        with patch('services.watchlist.WatchlistService.add_symbols') as mock_add:
            mock_add.return_value = None
            payload = {"symbols": ["RELIANCE", "TCS"], "category": "day_trading"}
            response = client.post("/api/watchlist", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "day_trading"

    def test_remove_symbols_with_category(self):
        """Test removing symbols with a category"""
        with patch('services.watchlist.WatchlistService.remove_symbols') as mock_remove:
            mock_remove.return_value = None
            payload = {"symbols": ["RELIANCE"], "category": "short_term"}
            response = client.delete("/api/watchlist", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["category"] == "short_term"

    def test_change_symbol_category(self):
        """Test changing symbol category"""
        with patch('services.watchlist.WatchlistService.set_category') as mock_set:
            mock_set.return_value = None
            response = client.put("/api/watchlist/category", params={"symbol": "RELIANCE", "category": "long_term"})
            assert response.status_code == 200
            data = response.json()
            assert "Updated RELIANCE to category long_term" in data["message"]

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
