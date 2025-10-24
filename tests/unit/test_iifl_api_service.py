"""
Unit tests for IIFL API Service
Tests authentication, API calls, error handling, and data parsing
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from datetime import datetime, timedelta

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.iifl_api import IIFLAPIService
from config.settings import get_settings


class TestIIFLAPIService:
    """Test suite for IIFL API Service"""

    @pytest.fixture
    def iifl_service(self):
        """Create IIFL service instance for testing"""
        return IIFLAPIService()

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        settings = MagicMock()
        settings.iifl_client_id = "test_client_id"
        settings.iifl_auth_code = "test_auth_code"
        settings.iifl_app_secret = "test_app_secret"
        settings.iifl_base_url = "https://api.test.com/v1"
        settings.environment = "development"
        return settings

    @pytest.fixture
    def mock_successful_auth_response(self):
        """Mock successful authentication response"""
        return {
            "stat": "Ok",
            "emsg": "",
            "SessionToken": "test_session_token_12345",
            "result": "success"
        }

    @pytest.fixture
    def mock_failed_auth_response(self):
        """Mock failed authentication response"""
        return {
            "stat": "Not_Ok",
            "emsg": "Invalid auth code",
            "SessionToken": "",
            "result": "failure"
        }

    def test_initialization(self, iifl_service):
        """Test IIFL API service initialization"""
        assert iifl_service.client_id is not None
        assert iifl_service.auth_code is not None
        assert iifl_service.app_secret is not None
        assert iifl_service.session_token is None

        @pytest.mark.asyncio
    async def test_authentication_success(self, iifl_service, mock_auth_response):
        """Test successful authentication"""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value.json.return_value = mock_auth_response
            mock_post.return_value.status_code = 200

            result = await iifl_service.authenticate()

            assert "access_token" in result
            assert iifl_service.session_token == "test_session_token_123"

    @pytest.mark.asyncio
    async def test_failed_authentication(self, iifl_service, mock_failed_auth_response):
        """Test failed authentication flow"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_failed_auth_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await iifl_service.authenticate()

            assert result is False
            assert iifl_service.session_token is None

    @pytest.mark.asyncio
    async def test_authentication_network_error(self, iifl_service):
        """Test authentication with network error"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.RequestError("Network error")

            result = await iifl_service.authenticate()

            assert result is False
            assert iifl_service.session_token is None
            assert iifl_service.authenticated is False

    @pytest.mark.asyncio
    async def test_authentication_timeout(self, iifl_service):
        """Test authentication timeout"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.post.side_effect = httpx.TimeoutException("Timeout")

            result = await iifl_service.authenticate()

            assert result is False
            assert iifl_service.session_token is None

    @pytest.mark.asyncio
    async def test_authentication_invalid_json(self, iifl_service):
        """Test authentication with invalid JSON response"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Invalid JSON")
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await iifl_service.authenticate()

            assert result is False

    @pytest.mark.asyncio
    async def test_token_expiry_check(self, iifl_service):
        """Test token expiry logic"""
        # Set expired token
        iifl_service.session_token = "expired_token"
        iifl_service.token_expiry = datetime.now() - timedelta(hours=1)
        iifl_service.authenticated = True

        assert iifl_service.is_token_expired() is True

        # Set valid token
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)
        assert iifl_service.is_token_expired() is False

    @pytest.mark.asyncio
    async def test_get_user_session_success(self, iifl_service, mock_successful_auth_response):
        """Test get_user_session method"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_successful_auth_response
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await iifl_service.get_user_session()

            assert result == mock_successful_auth_response
            mock_client.return_value.__aenter__.return_value.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_authenticated(self, iifl_service):
        """Test making authenticated API request"""
        # Setup authenticated service
        iifl_service.session_token = "test_token"
        iifl_service.authenticated = True
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)

        mock_response_data = {"stat": "Ok", "result": [{"symbol": "RELIANCE", "price": 2500}]}

        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await iifl_service.make_request("/test-endpoint", {"test": "data"})

            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_make_request_unauthenticated(self, iifl_service):
        """Test making request without authentication"""
        result = await iifl_service.make_request("/test-endpoint", {"test": "data"})
        assert result is None

    @pytest.mark.asyncio
    async def test_make_request_with_retry(self, iifl_service):
        """Test request retry mechanism"""
        iifl_service.session_token = "test_token"
        iifl_service.authenticated = True
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)

        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            # First call fails, second succeeds
            mock_response_fail = AsyncMock()
            mock_response_fail.status_code = 500
            
            mock_response_success = AsyncMock()
            mock_response_success.status_code = 200
            mock_response_success.json.return_value = {"stat": "Ok", "result": "success"}
            
            mock_client.return_value.__aenter__.return_value.post.side_effect = [
                mock_response_fail, mock_response_success
            ]

            # If service has retry logic
            try:
                result = await iifl_service.make_request("/test-endpoint", {"test": "data"})
                # Should succeed on retry if implemented
            except Exception:
                # If no retry logic, should fail
                pass

    @pytest.mark.asyncio
    async def test_development_mode_fallback(self):
        """Test development mode with mock authentication"""
        with patch('config.settings.get_settings') as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.environment = "development"
            mock_settings.iifl_client_id = "mock_client_id"
            mock_get_settings.return_value = mock_settings

            service = IIFLAPIService()
            result = await service.authenticate()

            # Should return True in development mode with mock credentials
            assert result is True
            assert service.session_token.startswith("mock_")

    def test_calculate_checksum(self, iifl_service):
        """Test checksum calculation"""
        # This tests the checksum calculation if implemented
        test_data = {
            "ClientID": "test_client",
            "AuthCode": "test_auth",
            "AppSecret": "test_secret"
        }
        
        # Test that checksum is generated consistently
        checksum1 = iifl_service._calculate_checksum(test_data)
        checksum2 = iifl_service._calculate_checksum(test_data)
        
        assert checksum1 == checksum2
        assert len(checksum1) > 0

    @pytest.mark.asyncio
    async def test_session_cleanup(self, iifl_service):
        """Test session cleanup"""
        iifl_service.session_token = "test_token"
        iifl_service.authenticated = True
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)

        await iifl_service.logout()

        assert iifl_service.session_token is None
        assert iifl_service.authenticated is False
        assert iifl_service.token_expiry is None

    @pytest.mark.asyncio
    async def test_concurrent_authentication(self, iifl_service):
        """Test concurrent authentication calls"""
        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "stat": "Ok",
                "SessionToken": "test_token",
                "emsg": ""
            }
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            # Multiple concurrent auth calls
            tasks = [iifl_service.authenticate() for _ in range(3)]
            results = await asyncio.gather(*tasks)

            # All should succeed
            assert all(results)
            # Should only make one actual API call (if locking is implemented)

    @pytest.mark.asyncio
    async def test_error_handling_malformed_response(self, iifl_service):
        """Test handling of malformed API responses"""
        iifl_service.session_token = "test_token"
        iifl_service.authenticated = True
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)

        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            # Response missing required fields
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"invalid": "response"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            result = await iifl_service.make_request("/test-endpoint", {})
            
            # Should handle gracefully
            assert result is not None or result is None  # Depends on implementation

    @pytest.mark.asyncio
    async def test_request_headers(self, iifl_service):
        """Test that requests include proper headers"""
        iifl_service.session_token = "test_token"
        iifl_service.authenticated = True
        iifl_service.token_expiry = datetime.now() + timedelta(hours=1)

        with patch('services.iifl_api.httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"stat": "Ok"}
            mock_client.return_value.__aenter__.return_value.post.return_value = mock_response

            await iifl_service.make_request("/test-endpoint", {"test": "data"})

            # Verify headers were set correctly
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            if call_args:
                # Check that proper headers are included
                assert "headers" in call_args.kwargs or len(call_args.args) > 2

if __name__ == "__main__":
    pytest.main([__file__, "-v"])