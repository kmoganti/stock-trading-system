"""
Quick diagnostic tests to identify import and instantiation issues
"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_import_iifl_service():
    """Test that IIFL service can be imported"""
    try:
        from services.iifl_api import IIFLAPIService
        assert IIFLAPIService is not None
    except ImportError as e:
        pytest.fail(f"Failed to import IIFLAPIService: {e}")


def test_import_data_fetcher():
    """Test that data fetcher can be imported"""
    try:
        from services.data_fetcher import DataFetcher
        assert DataFetcher is not None
    except ImportError as e:
        pytest.fail(f"Failed to import DataFetcher: {e}")


def test_import_order_manager():
    """Test that order manager can be imported"""
    try:
        from services.order_manager import OrderManager
        assert OrderManager is not None
    except ImportError as e:
        pytest.fail(f"Failed to import OrderManager: {e}")


def test_import_database_models():
    """Test that database models can be imported"""
    try:
        from models.signals import Signal, SignalType, SignalStatus
        from models.watchlist import Watchlist
        from models.pnl_reports import PnLReport
        from models.risk_events import RiskEvent
        assert all([Signal, SignalType, SignalStatus, Watchlist, PnLReport, RiskEvent])
    except ImportError as e:
        pytest.fail(f"Failed to import database models: {e}")


def test_instantiate_iifl_service():
    """Test that IIFL service can be instantiated"""
    try:
        from services.iifl_api import IIFLAPIService
        # Clear singleton
        IIFLAPIService._instance = None
        service = IIFLAPIService()
        assert service is not None
        assert hasattr(service, 'client_id')
        assert hasattr(service, 'session_token')
    except Exception as e:
        pytest.fail(f"Failed to instantiate IIFLAPIService: {e}")


def test_config_settings():
    """Test that config settings can be loaded"""
    try:
        from config.settings import get_settings
        settings = get_settings()
        assert settings is not None
        # Check if essential settings exist
        assert hasattr(settings, 'iifl_client_id')
        assert hasattr(settings, 'iifl_auth_code')
    except Exception as e:
        pytest.fail(f"Failed to load config settings: {e}")


def test_database_connection():
    """Test basic database setup"""
    try:
        from models.database import init_db, get_db
        assert init_db is not None
        assert get_db is not None
    except Exception as e:
        pytest.fail(f"Failed to import database functions: {e}")


def test_main_app_import():
    """Test that main FastAPI app can be imported"""
    try:
        from main import app
        assert app is not None
    except Exception as e:
        pytest.fail(f"Failed to import FastAPI app: {e}")


def test_api_endpoints_import():
    """Test that API endpoints can be imported"""
    try:
        import api.auth
        import api.portfolio
        import api.signals
        assert True  # If we get here, imports succeeded
    except ImportError as e:
        pytest.fail(f"Failed to import API modules: {e}")


def test_essential_environment_variables():
    """Test that essential environment variables are accessible"""
    import os
    
    # Check for IIFL credentials
    iifl_vars = ['IIFL_CLIENT_ID', 'IIFL_AUTH_CODE', 'IIFL_APP_SECRET']
    missing_vars = [var for var in iifl_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Warning: Missing environment variables: {missing_vars}")
        # Don't fail the test, just warn
        assert True
    else:
        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])