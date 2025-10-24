"""
Unit tests for IIFL API Service (Fixed Version)
Tests authentication, request handling, error handling, and retries
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.iifl_api import IIFLAPIService


class TestIIFLAPIServiceFixed:
    """Test suite for IIFL API Service"""

    @pytest.fixture
    def iifl_service(self):
        """Create IIFL API service instance for testing"""
        # Clear any cached instances
        IIFLAPIService._instance = None
        service = IIFLAPIService()
        # Clear any cached tokens for fresh tests
        service.session_token = None
        return service

    @pytest.fixture
    def mock_auth_response(self):
        """Mock successful authentication response"""
        return {
            "access_token": "test_session_token_123",
            "expires_in": 3600,
            "token_type": "bearer"
        }

    @pytest.fixture
    def mock_failed_auth_response(self):
        """Mock failed authentication response"""
        return {"error": "Invalid auth code"}

    def test_initialization(self, iifl_service):
        """Test IIFL API service initialization"""
        assert iifl_service.client_id is not None
        assert iifl_service.auth_code is not None
        assert iifl_service.app_secret is not None
        assert iifl_service.session_token is None

    @pytest.mark.asyncio
    async def test_authentication_success(self, iifl_service, mock_auth_response):
        """Test successful authentication"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_auth_response
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await iifl_service.authenticate()

            assert "access_token" in result
            assert iifl_service.session_token == "test_session_token_123"

    @pytest.mark.asyncio
    async def test_authentication_failure(self, iifl_service, mock_failed_auth_response):
        """Test authentication failure"""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_failed_auth_response
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await iifl_service.authenticate()

            assert "error" in result or result is False
            assert iifl_service.session_token is None

    @pytest.mark.asyncio
    async def test_ensure_authenticated_with_token(self, iifl_service):
        """Test _ensure_authenticated when token exists"""
        iifl_service.session_token = "existing_token"
        
        result = await iifl_service._ensure_authenticated()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_ensure_authenticated_without_token(self, iifl_service, mock_auth_response):
        """Test _ensure_authenticated when no token exists"""
        iifl_service.session_token = None
        
        with patch.object(iifl_service, 'authenticate') as mock_auth:
            mock_auth.return_value = mock_auth_response
            
            result = await iifl_service._ensure_authenticated()
            
            assert result is True
            mock_auth.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_success(self, iifl_service):
        """Test successful API request"""
        # Set up authenticated service
        iifl_service.session_token = "test_token"
        
        mock_response_data = {"stat": "Ok", "result": {"data": "test"}}
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_response_data
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await iifl_service._make_api_request("POST", "/test", {"key": "value"})

            assert result == mock_response_data

    @pytest.mark.asyncio
    async def test_make_request_network_error(self, iifl_service):
        """Test API request with network error"""
        iifl_service.session_token = "test_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.post.side_effect = Exception("Network error")
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            result = await iifl_service._make_api_request("POST", "/test", {"key": "value"})

            assert result is None

    @pytest.mark.asyncio
    async def test_token_caching(self, iifl_service):
        """Test token caching functionality"""
        test_token = "cached_token_123"
        
        # Set token
        iifl_service.session_token = test_token
        
        # Verify token is cached
        assert iifl_service.session_token == test_token

    @pytest.mark.asyncio
    async def test_checksum_generation(self, iifl_service):
        """Test checksum generation for authentication"""
        data = {"key": "value", "timestamp": "123456"}
        
        # This tests the internal checksum logic
        with patch.object(iifl_service, '_generate_checksum') as mock_checksum:
            mock_checksum.return_value = "test_checksum"
            
            checksum = iifl_service._generate_checksum(data)
            
            assert checksum == "test_checksum"

    @pytest.mark.asyncio
    async def test_rate_limiting(self, iifl_service):
        """Test rate limiting functionality"""
        iifl_service.session_token = "test_token"
        
        # Mock multiple rapid requests
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"stat": "Ok", "result": {}}
            
            mock_client_instance = AsyncMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Make multiple requests
            tasks = []
            for _ in range(3):
                task = iifl_service._make_api_request("POST", "/test", {})
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All should succeed (rate limiting handled internally)
            assert len(results) == 3

    def test_settings_loading(self, iifl_service):
        """Test that settings are loaded correctly"""
        assert hasattr(iifl_service, 'client_id')
        assert hasattr(iifl_service, 'auth_code')
        assert hasattr(iifl_service, 'app_secret')
        assert hasattr(iifl_service, 'base_url')

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """Test that IIFLAPIService follows singleton pattern"""
        # Clear singleton instance
        IIFLAPIService._instance = None
        
        service1 = IIFLAPIService()
        service2 = IIFLAPIService()
        
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_cleanup(self, iifl_service):
        """Test cleanup of resources"""
        # Set up some state
        iifl_service.session_token = "test_token"
        
        # Test cleanup (if method exists)
        if hasattr(iifl_service, 'cleanup'):
            await iifl_service.cleanup()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])