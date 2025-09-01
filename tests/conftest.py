import pytest
import asyncio
import tempfile
import os
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Set environment variable for test database
    os.environ['DATABASE_URL'] = f'sqlite+aiosqlite:///{db_path}'
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def test_env():
    """Set up test environment variables"""
    test_vars = {
        'CLIENT_ID': 'test_client',
        'AUTH_CODE': 'test_auth',
        'APP_SECRET': 'test_secret',
        'BASE_URL': 'https://api.test.com',
        'TELEGRAM_BOT_TOKEN': 'test_bot_token',
        'TELEGRAM_CHAT_ID': '123456789',
        'AUTO_TRADE': 'false',
        'DEBUG': 'true'
    }
    
    # Store original values
    original_values = {}
    for key, value in test_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield test_vars
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value
