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
    # Align with tests and UI expecting 'authenticated' and 'is_authenticated'
    authenticated: bool
    # Backward/forward compatibility for UI templates referring to is_authenticated
    is_authenticated: Optional[bool] = None
    client_id: Optional[str] = None
    token_expiry: Optional[datetime] = None
    auth_code_expiry: Optional[datetime] = None
    last_error: Optional[str] = None
    # Optional details for debug UIs
    details: Optional[dict] = None

@router.get("/status", response_model=AuthStatus)
async def get_auth_status():
    """Get current authentication status"""
    logger.info("Request for authentication status.")
    try:
        service = IIFLAPIService()
        # Consider authenticated if there is a non-mock session token
        token = getattr(service, 'session_token', None)
        is_real_token = bool(token) and not str(token).startswith("mock_")

        # If no in-memory token detected, try light recovery paths to avoid false negatives
        if not is_real_token:
            try:
                # 1) Try file cache (fast, local)
                cached = service._load_token_from_cache()
                if cached:
                    service.session_token = cached
                    token = cached
                    is_real_token = True
            except Exception:
                pass

        if not is_real_token:
            # 2) Try a very short auth ping (guarded by timeout) to avoid confusing UI
            try:
                import asyncio
                auth_result = await asyncio.wait_for(service.authenticate(), timeout=4.0)
                if isinstance(auth_result, dict) and auth_result.get("access_token") and not str(auth_result.get("access_token")).startswith("mock_"):
                    token = auth_result.get("access_token")
                    is_real_token = True
            except Exception:
                # Ignore here; we'll attempt a profile call next
                pass

        if not is_real_token:
            # 3) As a last resort, attempt a very quick profile call which ensures auth inside
            try:
                import asyncio
                prof = await asyncio.wait_for(service.get_profile(), timeout=3.5)
                if isinstance(prof, dict) and str((prof.get("status") or prof.get("stat") or "")).lower() == "ok":
                    is_real_token = True
            except Exception:
                pass
        try:
            from config.settings import get_settings
            client_id_val = getattr(get_settings(), 'iifl_client_id', None)
        except Exception:
            client_id_val = None
        auth_status = AuthStatus(
            authenticated=is_real_token,
            is_authenticated=is_real_token,
            client_id=client_id_val,
            token_expiry=getattr(service, 'token_expiry', None),
            auth_code_expiry=getattr(service, 'auth_code_expiry', None),
            last_error=None
        )
        logger.info(f"Auth status: authenticated={auth_status.authenticated}")
        return auth_status
    except Exception as e:
        logger.error(f"Error getting auth status: {str(e)}")
        return AuthStatus(
            authenticated=False,
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
        auth_result = await service.authenticate()
        
        if auth_result and not isinstance(auth_result, dict) or (isinstance(auth_result, dict) and auth_result.get("access_token")):
            logger.info("Auth code updated and authentication successful.")
            return {"message": "Auth code updated successfully", "success": True}
        else:
            # Provide specific error message based on auth result
            if isinstance(auth_result, dict):
                if auth_result.get("auth_code_expired"):
                    error_msg = "❌ The provided auth code has already expired"
                    logger.warning(f"New auth code expired: {auth_code[:8]}...")
                    raise HTTPException(status_code=400, detail=error_msg)
                elif auth_result.get("error"):
                    error_msg = f"❌ Authentication failed: {auth_result['error']}"
                    logger.warning(f"Auth failed for code: {auth_code[:8]}...")
                    raise HTTPException(status_code=400, detail=error_msg)
            
            # Generic error message
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
        # Clear any existing in-memory and cached token to force a real re-auth
        try:
            service.session_token = None
            service.token_expiry = None
            # Clear file cache too
            try:
                service._save_token_to_cache("")  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            pass

        auth_result = await service.authenticate()
        
        if auth_result and not isinstance(auth_result, dict) or (isinstance(auth_result, dict) and auth_result.get("access_token")):
            logger.info("Token refreshed successfully.")
            return {"message": "Token refreshed successfully", "success": True}
        else:
            # Provide specific error message based on auth result
            if isinstance(auth_result, dict):
                if auth_result.get("auth_code_expired"):
                    error_msg = "🔒 Auth code has expired. Please update IIFL_AUTH_CODE in .env file"
                    logger.warning("Token refresh failed: auth code expired")
                    raise HTTPException(status_code=401, detail=error_msg)
                elif auth_result.get("error"):
                    error_msg = f"❌ Token refresh failed: {auth_result['error']}"
                    logger.warning("Token refresh failed")
                    raise HTTPException(status_code=400, detail=error_msg)
            
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

@router.get("/debug")
async def auth_debug():
    """Return detailed auth debug info: token presence, quick profile probe, and settings preview."""
    try:
        service = IIFLAPIService()
        token = getattr(service, 'session_token', None)
        token_preview = None
        if token:
            t = str(token)
            token_preview = (t[:6] + "***" + t[-4:]) if len(t) > 12 else (t[:3] + "***")
        profile_status = None
        profile_message = None
        try:
            prof = await service.get_profile()
            if isinstance(prof, dict):
                profile_status = prof.get("status") or prof.get("stat")
                profile_message = prof.get("message") or prof.get("emsg")
        except Exception as e:
            profile_message = f"profile_error: {e}"

        try:
            from config.settings import get_settings
            st = get_settings()
            client_id = getattr(st, 'iifl_client_id', None)
            env = getattr(st, 'environment', None)
        except Exception:
            client_id = None
            env = None

        return {
            "authenticated": bool(token) and not str(token).startswith("mock_"),
            "token_present": bool(token),
            "token_preview": token_preview,
            "token_expiry": getattr(service, 'token_expiry', None),
            "auth_code_expiry": getattr(service, 'auth_code_expiry', None),
            "profile_status": profile_status,
            "profile_message": profile_message,
            "client_id": client_id,
            "environment": env,
            "safe_mode": getattr(service, 'safe_mode', False),
        }
    except Exception as e:
        logger.error(f"Error in auth debug: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
