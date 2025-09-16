from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from config import get_settings

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Dependency to validate the API key.
    The API key is a simple shared secret stored in the application settings.
    """
    settings = get_settings()
    if settings.api_secret_key and api_key_header == settings.api_secret_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )