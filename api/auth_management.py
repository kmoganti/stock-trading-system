from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging
from services.iifl_api import IIFLAPIService
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class AuthCodeUpdate(BaseModel):
    auth_code: str

class AuthStatus(BaseModel):
    is_authenticated: bool
    token_expiry: Optional[datetime]
    auth_code_expiry: Optional[datetime]
    last_error: Optional[str]

@router.get("/status", response_model=AuthStatus)
async def get_auth_status():
    """Get current authentication status"""
    logger.info("Request for authentication status.")
    try:
        service = IIFLAPIService()
        status = AuthStatus(
            is_authenticated=service.session_token is not None and service.token_expiry is not None,
            token_expiry=service.token_expiry,
            auth_code_expiry=getattr(service, 'auth_code_expiry', None),
            last_error=None
        )
        logger.info(f"Auth status: authenticated={status.is_authenticated}")
        return status
    except Exception as e:
        logger.error(f"Error getting auth status: {str(e)}")
        return AuthStatus(
            is_authenticated=False,
            token_expiry=None,
            auth_code_expiry=None,
            last_error=str(e)
        )

@router.post("/update-auth-code")
async def update_auth_code(auth_data: AuthCodeUpdate):
    """Update IIFL auth code manually"""
    logger.info("Request to update IIFL auth code.")
    try:
        service = IIFLAPIService()
        
        # Validate auth code format (basic validation)
        auth_code = auth_data.auth_code.strip()
        if len(auth_code) < 10:
            raise HTTPException(status_code=400, detail="Auth code appears to be too short. Please check the code.")
        
        # Update auth code and env file
        service.auth_code = auth_code
        service._initialize_auth_expiry()
        service._update_env_auth_code(auth_code)
        
        # Clear existing session to force re-authentication
        service.session_token = None
        service.token_expiry = None
        
        # Reinitialize auth expiry
        service._initialize_auth_expiry()
        
        # Test authentication with detailed error reporting
        success = await service.authenticate()
        
        if success:
            logger.info("Auth code updated and authentication successful.")
            return {"message": "Auth code updated successfully", "success": True}
        else:
            # Provide more specific error message
            error_msg = "Authentication failed. This could be due to:"
            error_details = [
                "• Invalid or expired auth code",
                "• Incorrect client ID or app secret",
                "• IIFL API service temporarily unavailable",
                "• Network connectivity issues"
            ]
            full_error = f"{error_msg}\n" + "\n".join(error_details)
            logger.warning(f"Authentication failed with new auth code: {auth_code[:8]}...")
            raise HTTPException(status_code=400, detail=full_error)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating auth code: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update auth code: {str(e)}")

@router.post("/refresh-token")
async def refresh_token():
    """Force refresh authentication token"""
    logger.info("Request to refresh authentication token.")
    try:
        service = IIFLAPIService()
        success = await service.authenticate()
        
        if success:
            logger.info("Token refreshed successfully.")
            return {"message": "Token refreshed successfully", "success": True}
        else:
            logger.warning("Token refresh failed.")
            raise HTTPException(status_code=400, detail="Token refresh failed")
                
    except Exception as e:
        logger.error(f"Error refreshing token: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to refresh token: {str(e)}")

@router.post("/test-connection")
async def test_connection():
    """Test IIFL API connection"""
    logger.info("Request to test IIFL API connection.")
    try:
        service = IIFLAPIService()
        # Try to get profile as a connection test
        profile = await service.get_profile()
        
        if profile:
            logger.info("IIFL API connection test successful.")
            return {"message": "Connection test successful", "success": True, "data": profile}
        else:
            logger.warning("IIFL API connection test failed, no profile data.")
            return {"message": "Connection test failed", "success": False}
                
    except Exception as e:
        logger.error(f"Error testing connection: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")

@router.post("/validate-auth-code")
async def validate_auth_code(auth_data: AuthCodeUpdate):
    """Validate auth code without updating system settings"""
    logger.info("Request to validate IIFL auth code.")
    try:
        # Create a temporary service instance for testing
        service = IIFLAPIService()
        original_auth_code = service.auth_code
        
        # Temporarily set the new auth code for testing
        service.auth_code = auth_data.auth_code.strip()
        service.session_token = None
        service.token_expiry = None
        
        # Test authentication
        success = await service.authenticate()
        
        # Restore original auth code
        service.auth_code = original_auth_code
        service.session_token = None
        service.token_expiry = None
        
        if success:
            logger.info("Auth code validation successful.")
            return {"message": "Auth code is valid", "success": True}
        else:
            logger.warning("Auth code validation failed.")
            return {"message": "Auth code validation failed", "success": False}
                
    except Exception as e:
        logger.error(f"Error validating auth code: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to validate auth code: {str(e)}")
