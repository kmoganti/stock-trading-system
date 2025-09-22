import os
import pytest


@pytest.fixture(autouse=True, scope="session")
def test_env():
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("DRY_RUN", "true")
    os.environ.setdefault("ENABLE_TELEGRAM", "false")
    os.environ.setdefault("IIFL_CLIENT_ID", "dummy")
    os.environ.setdefault("IIFL_AUTH_CODE", "dummy")
    os.environ.setdefault("IIFL_APP_SECRET", "dummy")
    os.environ.setdefault("SECRET_KEY", "dummy")
    yield

