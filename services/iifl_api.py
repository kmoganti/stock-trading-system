import asyncio
import json
import hashlib
import httpx
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import logging
import os
import time
from collections import deque
from services.logging_service import trading_logger

logger = logging.getLogger(__name__)

# --- Global Token Cache ---
# This simple dictionary acts as a process-level cache for the session token.
# It survives re-instantiation of the IIFLAPIService during hot-reloads.
_global_token_cache: Dict[str, Any] = {"token": None, "expiry": None}
# Lock to prevent race conditions during authentication
_auth_lock = asyncio.Lock()

class IIFLAPIService:
    """IIFL Markets API integration service using checksum-based authentication"""
    
    _instance: Optional['IIFLAPIService'] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # The __init__ will only be called the first time.
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized: # type: ignore
            # Lazy-load settings with fallback to env to avoid hard dependency on pydantic
            self._load_settings()
            # Track auth code expiry for UI; IIFL auth codes are day-bound
            self.auth_code_expiry: Optional[datetime] = None
            self.http_client: Optional[httpx.AsyncClient] = None
            self.get_user_session_endpoint = "/getusersession"
            # Simple global rate limiter (per-process) to limit IIFL calls
            self._req_timestamps_second = deque()
            self._req_timestamps_minute = deque()
            try:
                self.max_requests_per_second = int(os.getenv("IIFL_MAX_RPS", "3") or "3")
            except Exception:
                self.max_requests_per_second = 3
            try:
                self.max_requests_per_minute = int(os.getenv("IIFL_MAX_RPM", "60") or "60")
            except Exception:
                self.max_requests_per_minute = 60
            # Initialize an auth-code expiry hint
            try:
                self._initialize_auth_expiry()
            except Exception as e:
                logger.debug(f"Could not initialize auth expiry on init: {e}")
            self._initialized = True

    def _load_settings(self) -> None:
        """Load settings using config.settings if available, else fallback to os.environ."""
        try:
            from config.settings import get_settings  # type: ignore
            settings = get_settings()
            self.client_id = settings.iifl_client_id
            self.auth_code = settings.iifl_auth_code
            self.app_secret = settings.iifl_app_secret
            # Backward compatibility: single base_url
            self.token_cache_file = os.path.join(os.path.dirname(__file__), '..', '.iifl_session_token')
            self.base_url = settings.iifl_base_url
            self.settings = settings
        except Exception:
            # Minimal fallback using environment variables directly
            self.client_id = os.getenv("IIFL_CLIENT_ID", "")
            self.auth_code = os.getenv("IIFL_AUTH_CODE", "")
            self.app_secret = os.getenv("IIFL_APP_SECRET", "")
            # Backward compatibility: single base_url
            self.token_cache_file = os.path.join(os.path.dirname(__file__), '..', '.iifl_session_token')
            self.base_url = os.getenv("IIFL_BASE_URL", "https://api.iiflcapital.com/v1")
            self.settings = type("_FallbackSettings", (), {
                "iifl_client_id": self.client_id,
                "iifl_auth_code": self.auth_code,
                "iifl_app_secret": self.app_secret,
                "iifl_base_url": self.base_url,
            })()

    @property
    def session_token(self) -> Optional[str]:
        """Get the session token from the global cache."""
        return _global_token_cache.get("token")

    @session_token.setter
    def session_token(self, value: Optional[str]):
        """Set the session token in the global cache."""
        _global_token_cache["token"] = value

    @property
    def token_expiry(self) -> Optional[datetime]:
        return _global_token_cache.get("expiry")

    @token_expiry.setter
    def token_expiry(self, value: Optional[datetime]):
        _global_token_cache["expiry"] = value
    
    def _load_token_from_cache(self) -> Optional[str]:
        """Load session token from a file cache."""
        try:
            if os.path.exists(self.token_cache_file):
                with open(self.token_cache_file, 'r') as f:
                    token = f.read().strip()
                    if token:
                        logger.info("Loaded session token from cache file.")
                        return token
        except Exception as e:
            logger.warning(f"Could not load token from cache: {e}")
        return None

    def _save_token_to_cache(self, token: str) -> None:
        """Save session token to a file cache."""
        try:
            with open(self.token_cache_file, 'w') as f:
                f.write(token)
        except Exception as e:
            logger.error(f"Could not save token to cache: {e}")
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create an httpx.AsyncClient instance."""
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient()
        return self.http_client

    async def close_http_client(self):
        """Close the httpx.AsyncClient instance if it exists."""
        if self.http_client and not self.http_client.is_closed:
            await self.http_client.aclose()
            self.http_client = None

    def sha256_hash(self, input_string: str) -> str:
        """Returns the SHA-256 hash of the input string."""
        return hashlib.sha256(input_string.encode('utf-8')).hexdigest()

    # --- Auth helpers for UI integration ---
    def _initialize_auth_expiry(self) -> None:
        """Initialize or refresh the expected auth-code expiry timestamp.

        IIFL auth codes typically expire daily. As an approximation, set expiry to
        24 hours from now if not already set, or refresh to the next 24h window
        after an update. This value is informational for the UI.
        """
        now = datetime.now()
        if self.auth_code:
            # Set to 24 hours ahead to indicate the next refresh time window
            self.auth_code_expiry = now + timedelta(hours=24)
        else:
            self.auth_code_expiry = None

    def _get_env_file_path(self) -> str:
        """Resolve the project .env file path (project root)."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        return os.path.join(project_root, ".env")

    def _update_env_auth_code(self, new_auth_code: str) -> None:
        """Persist the updated auth code to the .env file, preserving other entries."""
        env_path = self._get_env_file_path()
        lines: List[str] = []
        try:
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
        except Exception:
            lines = []

        key = "IIFL_AUTH_CODE"
        replaced = False
        updated_lines: List[str] = []
        for line in lines:
            if line.strip().startswith(f"{key}="):
                updated_lines.append(f"{key}={new_auth_code}")
                replaced = True
            else:
                updated_lines.append(line)
        if not replaced:
            updated_lines.append(f"{key}={new_auth_code}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(env_path), exist_ok=True)
        tmp_path = env_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write("\n".join(updated_lines) + "\n")
        os.replace(tmp_path, env_path)
        # Also update in-memory settings so subsequent loads see the change
        try:
            import config.settings as cfg
            cfg._settings = None  # type: ignore
        except Exception:
            pass
    
    async def get_user_session(self, auth_code: str) -> Dict:
        """Request a new user session from the IIFL API using checksum authentication."""
        start_time = time.time()
        
        # Construct the checksum required by the API
        checksum_str = self.client_id + auth_code + self.app_secret
        checksum = self.sha256_hash(checksum_str)

        url = f"{self.base_url.rstrip('/')}{self.get_user_session_endpoint}"
        headers = {"Content-Type": "application/json"}
        
        # The payload for the session request includes the checksum
        payload = {
            "checkSum": checksum
        }
        
        # Enhanced logging for IIFL API calls
        logger.info(f"IIFL API Request: POST {url}")
        logger.info(f"Request Headers: {json.dumps(headers)}")
        logger.info(f"Request Body: {json.dumps(payload)}")
        
        # Log to specialized API logger
        trading_logger.log_system_event("iifl_api_request", {
            "method": "POST",
            "url": url,
            "endpoint": self.get_user_session_endpoint,
            "payload_keys": list(payload.keys())
        })
        
        try:
            client = await self.get_http_client()
            # Make HTTP request without additional timeout wrapper
            response = await client.post(url, headers=headers, data=json.dumps(payload))
            response_time = time.time() - start_time
            
            # Enhanced response logging
            logger.info(f"IIFL API Response: {response.status_code} in {response_time:.3f}s")
            logger.info(f"Response Headers: {json.dumps(dict(response.headers))}")
            logger.info(f"Response Body: {response.text}")
            
            # Log API call details
            trading_logger.log_api_call(
                endpoint=url,
                method="POST",
                status_code=response.status_code,
                response_time=response_time,
                error=None if response.status_code == 200 else f"HTTP {response.status_code}"
            )
            
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            response_data = response.json()
            
            # Log successful response
            trading_logger.log_system_event("iifl_api_response", {
                "url": url,
                "status_code": response.status_code,
                "response_time_ms": response_time * 1000,
                "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else "non_dict"
            })
            
            return response_data
            
        except httpx.RequestError as e:
            response_time = time.time() - start_time
            error_msg = f"Error during API request for user session: {e}"
            
            logger.error(error_msg)
            
            # Log API error
            trading_logger.log_api_call(
                endpoint=url,
                method="POST",
                status_code=0,
                response_time=response_time,
                error=str(e)
            )
            
            trading_logger.log_error("iifl_api", e, {
                "url": url,
                "method": "POST",
                "response_time": response_time
            })
            
            return {"error": f"Network error: {str(e)}"}
    
    async def authenticate(self, client_id: Optional[str] = None, auth_code: Optional[str] = None, app_secret: Optional[str] = None) -> dict:
        """Authenticate with IIFL API, protected by a lock to prevent race conditions."""
        async with _auth_lock:
            # Double-check if a token was acquired while waiting for the lock
            if self.session_token:
                return {"access_token": self.session_token, "expires_in": 3600}

            # Allow overrides for tests
            if client_id:
                self.client_id = client_id
            if auth_code:
                self.auth_code = auth_code
            if app_secret:
                self.app_secret = app_secret

            if not self.auth_code:
                print("❌ No auth code available for authentication")
                return {"error": "No auth code available for authentication"}
            
            # Immediately check for known expired auth codes to prevent hanging HTTP calls
            known_expired_codes = ["N49IQQZCRVCQQ6HL9VEX", "123456", "999999"]  
            if self.auth_code in known_expired_codes:
                # Use print instead of logger to avoid hanging
                print(f"🔒 KNOWN EXPIRED AUTH CODE DETECTED: {self.auth_code}")
                print("💡 Please update IIFL_AUTH_CODE in .env file with a fresh code")
                print("❌ Skipping HTTP call to prevent hanging")
                return {"error": "Known expired auth code", "auth_code_expired": True}
            
            try:
                logger.info("Attempting IIFL API authentication with checksum method")
                response_data = await self.get_user_session(self.auth_code)
                
                if response_data:
                    logger.info(f"Authentication response received: {json.dumps(response_data)}")
                    
                    if response_data.get("stat") == "Ok" or response_data.get("status") == "Ok":
                        session_token = (response_data.get("SessionToken") or 
                                       response_data.get("sessionToken") or 
                                       response_data.get("session_token") or
                                       response_data.get("userSession") or
                                       response_data.get("token"))
                        
                        if session_token:
                            self.session_token = session_token
                            self._save_token_to_cache(session_token)
                            self.token_expiry = None
                            logger.info(f"IIFL authentication successful. Token: {session_token[:10]}...")
                            trading_logger.log_system_event("iifl_auth_success", {"token_preview": session_token[:10] + "..."})
                            return {"access_token": session_token, "expires_in": 3600}
                        else:
                            logger.error("No session token found in IIFL response")
                            trading_logger.log_error("iifl_auth_no_token", {"response_keys": list(response_data.keys())})
                    else:
                        error_msg = response_data.get("emsg") or response_data.get("message", "Authentication failed")
                        logger.error(f"IIFL authentication failed: {error_msg}")
                        trading_logger.log_error("iifl_auth_failed", {"error_message": error_msg})
                
                # If authentication fails, handle based on environment
                logger.error("IIFL authentication failed - invalid or expired auth code")
                env_name = str(getattr(self.settings, "environment", "development")).lower()
                
                # Check if auth code appears to be expired (common error patterns)
                if response_data and isinstance(response_data, dict):
                    error_msg = response_data.get("emsg") or response_data.get("message", "")
                    if any(keyword in error_msg.lower() for keyword in ["expired", "invalid", "unauthorized", "forbidden", "not_ok"]):
                        logger.error(f"🚨 AUTH CODE EXPIRED OR INVALID: {error_msg}")
                        logger.error("💡 Please update your IIFL_AUTH_CODE in the .env file")
                        # Return immediately for expired codes - don't try fallbacks
                        return {"error": f"Auth failed: {error_msg}", "auth_code_expired": True}
                
                if env_name in ["development", "dev", "test", "testing"]:
                    logger.warning("⚠️  Using mock session for development/testing")
                    self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    return {"access_token": self.session_token, "expires_in": 3600}
                
                logger.error("❌ Authentication failed in production environment")
                return {"error": "Authentication failed - check auth code", "auth_code_expired": True}
                    
            except Exception as e:
                logger.error(f"IIFL API authentication exception: {str(e)}")
                env_name = str(getattr(self.settings, "environment", "development")).lower()
                
                if env_name in ["development", "dev", "test", "testing"]:
                    logger.warning("⚠️  Using mock session for development/testing due to exception")
                    self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    return {"access_token": self.session_token, "expires_in": 3600}
                
                logger.error("❌ Authentication exception in production environment")
                return {"error": f"Authentication exception: {str(e)}", "critical_error": True}
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication"""
        # Fast path: If token already exists, we're good.
        if self.session_token:
            logger.debug(f"Using existing session token: {self.session_token[:10]}...")
            return True
        
        # Slow path: No token. Try loading from file cache first.
        self.session_token = self._load_token_from_cache()
        if self.session_token:
            return True
        
        # If still no token, call the lock-protected authenticate method.
        auth_result = await self.authenticate()
        return "access_token" in auth_result if isinstance(auth_result, dict) else False
    
    async def _make_api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make an authenticated API request using the session token."""
        if not await self._ensure_authenticated():
            return None
        
        start_time = time.perf_counter()
        client = await self.get_http_client()
        # Use single consolidated base URL
        base = self.base_url
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        
        try:
            # Build Authorization header without double-prefixing
            token_value = self.session_token or ""
            auth_header = token_value if str(token_value).lower().startswith("bearer ") else (f"Bearer {token_value}" if token_value else "")

            headers = {
                "Content-Type": "application/json",
                "User-Agent": "IIFL-Trading-System/1.0",
                **({"Authorization": auth_header} if auth_header else {})
            }
            
            # The request body should only contain the data specific to the endpoint.
            # The session token is sent in the header.
            request_body = data if data is not None else {}

            # Helper to extract a compact representation of request body keys for logging
            def _request_body_keys(rb):
                try:
                    if isinstance(rb, dict):
                        return list(rb.keys())
                    if isinstance(rb, list):
                        # represent list payloads as a list marker; don't try to inspect inner objs here
                        return ["<list>"]
                    return [str(type(rb))]
                except Exception:
                    return ["<unknown>"]
            
            # Mask Authorization header for logs
            masked_headers = dict(headers)
            if "Authorization" in masked_headers:
                try:
                    token_str = str(masked_headers["Authorization"]) or ""
                    if token_str.lower().startswith("bearer "):
                        token_core = token_str.split(" ", 1)[1]
                    else:
                        token_core = token_str
                    preview = (token_core[:4] + "***") if token_core else "***"
                    masked_headers["Authorization"] = f"Bearer {preview}"
                except Exception:
                    masked_headers["Authorization"] = "Bearer ***"

            # Enhanced request logging
            logger.info(f"IIFL API Request: {method.upper()} {url}")
            logger.info(f"Request Headers: {json.dumps(masked_headers)}")
            logger.info(f"Request Body: {json.dumps(request_body)}")
            
            # Log to specialized API logger
            trading_logger.log_system_event("iifl_api_request", {
                "method": method.upper(),
                "url": url,
                "endpoint": endpoint,
                "has_bearer_token": bool(self.session_token),
                "data_keys": _request_body_keys(request_body)
            })

            try:
                attempted_reauth = False
                while True:
                    attempt_start = time.perf_counter()
                    # Throttle globally to avoid exceeding provider rate limits
                    await self._throttle_before_request()
                    # Recompute headers in case token changed after re-auth
                    token_value = self.session_token or ""
                    auth_header = token_value if str(token_value).lower().startswith("bearer ") else (f"Bearer {token_value}" if token_value else "")
                    headers = {
                        "Content-Type": "application/json",
                        "User-Agent": "IIFL-Trading-System/1.0",
                        **({"Authorization": auth_header} if auth_header else {})
                    }
                    masked_headers_loop = dict(headers)
                    if "Authorization" in masked_headers_loop:
                        try:
                            token_str = str(masked_headers_loop["Authorization"]) or ""
                            if token_str.lower().startswith("bearer "):
                                token_core = token_str.split(" ", 1)[1]
                            else:
                                token_core = token_str
                            preview = (token_core[:4] + "***") if token_core else "***"
                            masked_headers_loop["Authorization"] = f"Bearer {preview}"
                        except Exception:
                            masked_headers_loop["Authorization"] = "Bearer ***"
                    logger.info(f"IIFL API Attempt Headers: {json.dumps(masked_headers_loop)}")

                    # Implement small transient retry loop for network-level errors
                    max_attempts = 3
                    attempt = 0
                    last_exc = None
                    while attempt < max_attempts:
                        attempt += 1
                        try:
                            if method.upper() == "GET":
                                response = await client.get(url, headers=headers, params=request_body)
                            elif method.upper() == "POST":
                                response = await client.post(url, headers=headers, data=json.dumps(request_body))
                            elif method.upper() == "PUT":
                                response = await client.put(url, headers=headers, data=json.dumps(request_body))
                            elif method.upper() == "DELETE":
                                response = await client.delete(url, headers=headers)
                            else:
                                raise ValueError(f"Unsupported HTTP method: {method}")
                            # If we have a response, break out of retry loop
                            break
                        except httpx.RequestError as re:
                            last_exc = re
                            # On transient network issues, backoff and retry a couple of times
                            backoff = 0.5 * (2 ** (attempt - 1))
                            logger.warning(f"Transient network error on attempt {attempt}/{max_attempts} for {endpoint}, retrying after {backoff}s: {re}")
                            try:
                                await asyncio.sleep(backoff)
                            except Exception:
                                pass
                            continue
                    # If loop exited normally without break and last_exc is set, raise it
                    if attempt >= max_attempts and last_exc:
                        raise last_exc

                    response_time = time.perf_counter() - attempt_start

                    # Enhanced response logging
                    logger.info(f"IIFL API Response: {response.status_code} in {response_time:.3f}s")
                    logger.info(f"Response Headers: {json.dumps(dict(response.headers))}")

                    try:
                        response_data = response.json()
                        logger.info(f"Response Body: {json.dumps(response_data)}")

                        # Log API call
                        trading_logger.log_api_call(
                            endpoint=url,
                            method=method.upper(),
                            status_code=response.status_code,
                            response_time=response_time,
                            error=None if response.status_code == 200 else f"HTTP {response.status_code}",
                            request_body=request_body
                        )

                        # Log response details
                        status_field = None
                        message_field = None
                        result_count = None
                        if isinstance(response_data, dict):
                            status_field = response_data.get("status") or response_data.get("stat")
                            message_field = response_data.get("message") or response_data.get("emsg")
                            for key in ["result", "data", "resultData"]:
                                value = response_data.get(key)
                                if isinstance(value, list):
                                    result_count = len(value)
                                    break
                        trading_logger.log_system_event("iifl_api_response", {
                            "url": url,
                            "method": method.upper(),
                            "status_code": response.status_code,
                            "response_time_ms": response_time * 1000,
                            "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else "non_dict",
                            "success": response.status_code == 200,
                            "status": status_field,
                            "message_preview": (str(message_field)[:120] + ("..." if message_field and len(str(message_field)) > 120 else "")) if message_field else None,
                            "result_count": result_count
                        })

                    except json.JSONDecodeError:
                        logger.info(f"Response Body (non-JSON): {response.text}")
                        response_data = None

                    if response.status_code == 200:
                        return response_data

                    if response.status_code == 401 and not attempted_reauth:
                        logger.warning("Received 401 Unauthorized from IIFL API. Re-authenticating and retrying once.")
                        trading_logger.log_system_event("iifl_api_unauthorized", {"url": url, "endpoint": endpoint})
                        # Clear token and re-authenticate
                        self.session_token = None
                        self._save_token_to_cache("") # Clear cached token
                        reauth_result = await self.authenticate()
                        attempted_reauth = True
                        reauth_ok = "access_token" in reauth_result if isinstance(reauth_result, dict) else False
                        if reauth_ok and self.session_token and not str(self.session_token).startswith("mock_"):
                            continue  # Retry once with new token
                        else:
                            logger.error("Re-authentication failed or mock token obtained; aborting retry for production flow.")
                            break

                    # Other non-200 statuses: capture full response body (JSON or text) for debugging
                    try:
                        # Try to get JSON body if present
                        response_body = response.json()
                        body_preview = json.dumps(response_body)[:800]
                    except Exception:
                        response_body = response.text
                        body_preview = str(response.text)[:800]

                    error_msg = f"IIFL API request failed: {response.status_code} - body_preview={body_preview}"
                    logger.error(error_msg)

                    # Log API call with a snippet of the response body to help debug 4xx/5xx cases
                    trading_logger.log_api_call(
                        endpoint=url,
                        method=method.upper(),
                        status_code=response.status_code,
                        response_time=response_time,
                        error=f"HTTP {response.status_code}: {body_preview}",
                        request_body=request_body
                    )

                    # Also log an error event with full response body (non-sensitive) for later inspection
                    try:
                        trading_logger.log_system_event("iifl_api_error_response", {
                            "url": url,
                            "status_code": response.status_code,
                            "response_headers": dict(response.headers),
                            "response_body": response_body,
                            "request_body": request_body
                        })
                    except Exception:
                        # best-effort logging: don't fail the flow if complex object can't be serialized
                        trading_logger.log_system_event("iifl_api_error_response", {
                            "url": url,
                            "status_code": response.status_code,
                            "response_text_preview": body_preview,
                            "request_body": request_body
                        })

                    return None

            except httpx.RequestError as e:
                response_time = time.perf_counter() - start_time
                error_msg = f"IIFL API request exception: {str(e)}"
                logger.error(error_msg)
                trading_logger.log_api_call(
                    endpoint=url,
                    method=method.upper(),
                    status_code=0,
                    response_time=response_time,
                    error=str(e),
                    request_body=request_body
                )
                trading_logger.log_error("iifl_api", e, {
                    "url": url,
                    "method": method.upper(),
                    "endpoint": endpoint,
                    "response_time": response_time
                })
                return None
                
        except Exception as e:
            response_time = time.perf_counter() - start_time
            error_msg = f"IIFL API request exception: {str(e)}"
            logger.error(error_msg)
            
            # Log general exception
            trading_logger.log_error("iifl_api", e, {
                "url": url,
                "method": method.upper(),
                "endpoint": endpoint,
                "response_time": response_time
            })
            
            return None

    async def _throttle_before_request(self) -> None:
        """Naive async rate limiter: caps requests per second and per minute.

        Uses in-memory deques; safe within a single process. Sleeps just enough
        to honor both limits. Limits are configurable via env IIFL_MAX_RPS and IIFL_MAX_RPM.
        """
        try:
            now = time.monotonic()
            # Prune old timestamps
            one_sec_ago = now - 1.0
            one_min_ago = now - 60.0
            while self._req_timestamps_second and self._req_timestamps_second[0] < one_sec_ago:
                self._req_timestamps_second.popleft()
            while self._req_timestamps_minute and self._req_timestamps_minute[0] < one_min_ago:
                self._req_timestamps_minute.popleft()

            # If under limits, record and return fast
            if (len(self._req_timestamps_second) < self.max_requests_per_second and
                len(self._req_timestamps_minute) < self.max_requests_per_minute):
                self._req_timestamps_second.append(now)
                self._req_timestamps_minute.append(now)
                return

            # Compute minimal sleep needed to drop under both limits
            sleep_until = 0.0
            if len(self._req_timestamps_second) >= self.max_requests_per_second:
                sleep_until = max(sleep_until, self._req_timestamps_second[0] + 1.0)
            if len(self._req_timestamps_minute) >= self.max_requests_per_minute:
                sleep_until = max(sleep_until, self._req_timestamps_minute[0] + 60.0)
            delay = max(0.0, sleep_until - now)
            if delay > 0:
                await asyncio.sleep(min(delay, 1.0))  # cap individual sleeps to keep responsive
            # After sleeping, record this request time
            now2 = time.monotonic()
            self._req_timestamps_second.append(now2)
            self._req_timestamps_minute.append(now2)
        except Exception:
            # Best-effort limiter; never block requests on limiter errors
            return
    
    # User Profile & Limits
    async def get_profile(self) -> Optional[Dict]:
        """Get user profile information"""
        return await self._make_api_request("GET", "/profile")
    
    async def get_limits(self) -> Optional[Dict]:
        """Get current account limits/margins.

        Returns provider response as-is. Callers should normalize fields
        as needed to a stable interface for UI/consumers.
        """
        return await self._make_api_request("GET", "/limits")
    
    # Order Management
    async def place_order(self, order_data: Dict) -> Optional[Dict]:
        """Place a new order"""
        return await self._make_api_request("POST", "/orders", order_data)
    
    async def modify_order(self, broker_order_id: str, order_data: Dict) -> Optional[Dict]:
        """Modify an existing order"""
        return await self._make_api_request("PUT", f"/orders/{broker_order_id}", order_data)
    
    async def cancel_order(self, broker_order_id: str) -> Optional[Dict]:
        """Cancel an existing order"""
        return await self._make_api_request("DELETE", f"/orders/{broker_order_id}")
    
    async def get_orders(self) -> Optional[Dict]:
        """Get all orders for today"""
        return await self._make_api_request("GET", "/orders")
    
    async def get_order_details(self, broker_order_id: str) -> Optional[Dict]:
        """Get specific order details"""
        return await self._make_api_request("GET", f"/orders/{broker_order_id}")
    
    async def get_trades(self) -> Optional[Dict]:
        """Get all executed trades for today"""
        return await self._make_api_request("GET", "/trades")

    # Compat methods used in tests
    async def get_market_data(self, symbol: str) -> Optional[Dict]:
        data = await self.get_market_quotes([symbol])
        if data and data.get("status") == "Ok":
            items = data.get("resultData") or []
            if items:
                item = items[0]
                # Normalize to legacy shape expected by tests
                return {
                    "Symbol": item.get("symbol", symbol),
                    "LastTradedPrice": item.get("ltp"),
                    "Change": item.get("change", 0),
                    "Volume": item.get("volume", 0)
                }
        return None
    
    # Margin Calculations
    async def calculate_pre_order_margin(self, order_data: Dict) -> Optional[Dict]:
        """Calculate pre-order margin requirement using IIFL preordermargin endpoint"""
        return await self._make_api_request("POST", "/preordermargin", order_data)
    
    async def calculate_span_exposure(self, instruments: List[Dict]) -> Optional[Dict]:
        """Calculate SPAN and exposure margins"""
        return await self._make_api_request("POST", "/spanexposure", {"instruments": instruments})
    
    # Portfolio
    async def get_holdings(self) -> Optional[Dict]:
        """Get long-term equity holdings"""
        holdings_data = await self._make_api_request("GET", "/holdings")
        if holdings_data:
            logger.info(f"Holdings data received: {json.dumps(holdings_data, indent=2)}")
        else:
            logger.warning("No holdings data received from API.")
        return holdings_data

    async def get_positions(self) -> Optional[Dict]:
        """Get current open positions"""
        return await self._make_api_request("GET", "/positions")
    
    # Market Data
    async def get_historical_data(self, symbol: str, interval: str, from_date: str, to_date: str) -> Optional[Dict]:
        """Get historical OHLCV data with a single request (no fallbacks)."""

        # --- Date and Interval Preparation ---
        try:
            from_dt_parsed = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt_parsed = datetime.strptime(to_date, "%Y-%m-%d")
            # Keep month abbreviation capitalization as provider may expect e.g. '29-Jun-2025'
            dd_mon_yyyy_from = from_dt_parsed.strftime("%d-%b-%Y")
            dd_mon_yyyy_to = to_dt_parsed.strftime("%d-%b-%Y")
        except Exception:
            dd_mon_yyyy_from = from_date
            dd_mon_yyyy_to = to_date

        def _normalize_interval_value(user_interval: str) -> str:
            s = str(user_interval).strip().lower()
            mapping = {
                "1d": "1 day", "d": "1 day", "day": "1 day",
                "1m": "1 minute", "5m": "5 minutes", "15m": "15 minutes", "30m": "30 minutes",
                "60m": "60 minutes", "1h": "60 minutes",
                "1w": "weekly", "1mo": "monthly",
            }
            if s in {"1 day", "1 minute", "5 minutes", "10 minutes", "15 minutes", "30 minutes", "60 minutes", "weekly", "monthly"}:
                return s
            return mapping.get(s, "1 day")

        interval_norm = _normalize_interval_value(interval)

        # --- Payload Preparation (instrumentId only) ---
        payload = {
            "exchange": "NSEEQ",
            "interval": interval_norm,
            "fromDate": dd_mon_yyyy_from,
            "toDate": dd_mon_yyyy_to,
        }

        if str(symbol).isdigit():
            # Provider accepts InstrumentId (camel-case I) based on observed contract file & logs
            payload["instrumentId"] = str(symbol)
        else:
            # Resolve symbol to instrumentId - no symbol fallback
            local_map = self._load_normalized_contract_map()
            mapped = self._resolve_instrument_id_with_variants(symbol, local_map)
            if mapped:
                payload["instrumentId"] = str(mapped)
            else:
                logger.warning(f"Could not resolve symbol {symbol} to instrumentId - instrumentId-only mode")
                return None

        trading_logger.log_system_event("iifl_hist_attempt", {
            "attempt": 1,
            "variant": "single_request",
            "payload_keys": list(payload.keys())
        })

        return await self._make_api_request("POST", "/marketdata/historicaldata", payload)
    
    async def get_market_quotes(self, instruments: List[str]) -> Optional[Dict]:
        """Get real-time market quotes (instrumentId only)"""
        # Ensure all instruments are strings
        instrument_strs = [str(instr) for instr in instruments]

        # Load normalized contract map with variant matching
        local_map = self._load_normalized_contract_map()

        try:
            raw_obj_list = []
            skipped = []
            for s in instrument_strs:
                obj = {"exchange": "NSEEQ"}
                if str(s).isdigit():
                    obj["instrumentId"] = str(int(s))
                else:
                    mapped = self._resolve_instrument_id_with_variants(s, local_map)
                    if mapped:
                        obj["instrumentId"] = str(mapped)
                    else:
                        skipped.append(s)
                        continue
                raw_obj_list.append(obj)

            if not raw_obj_list:
                logger.warning(f"No valid instrumentId resolved for marketquotes; skipped={skipped}")
                return None

            logger.debug(f"Trying instrumentId-only marketquotes payload: {raw_obj_list}")
            resp = await self._make_api_request("POST", "/marketdata/marketquotes", raw_obj_list)
            return resp

        except Exception as e:
            logger.error(f"InstrumentId-only marketquotes failed: {e}")
            return None
    
    async def get_market_depth(self, instrument: str) -> Optional[Dict]:
        """Get market depth for an instrument (instrumentId only)"""
        try:
            payload: Dict[str, str] = {"exchange": "NSEEQ"}
            
            if str(instrument).isdigit():
                payload["instrumentId"] = str(int(instrument))
            else:
                # Resolve symbol to instrumentId using variant matching
                local_map = self._load_normalized_contract_map()
                mapped = self._resolve_instrument_id_with_variants(instrument, local_map)
                if mapped:
                    payload["instrumentId"] = str(mapped)
                else:
                    logger.warning(f"Could not resolve {instrument} to instrumentId for market depth")
                    return None

            return await self._make_api_request("POST", "/marketdata/marketdepth", payload)
        except Exception as e:
            logger.error(f"Failed to build or send market depth request for {instrument}: {e}")
            return None
    
    async def get_open_interest(self, instruments: List[str]) -> Optional[Dict]:
        """Get open interest data"""
        data = {"instruments": instruments}
        return await self._make_api_request("POST", "/marketdata/openinterest", data)
    
    # Utility methods
    def format_order_data(self, symbol: str, transaction_type: str, quantity: int, 
                         order_type: str = "MARKET", price: Optional[float] = None,
                         product: str = "NORMAL", exchange: str = "NSEEQ",
                         stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Dict:
        """Format order data for IIFL API margin calculation"""
        order_data = {
            "instrumentId": symbol,
            "exchange": exchange,  # NSEEQ, NSEFO, BSEEQ, etc.
            "transactionType": transaction_type.upper(),  # BUY/SELL
            "quantity": str(quantity),  # String format as per API spec
            "orderComplexity": "REGULAR",  # REGULAR, AMO, BO, CO
            "product": product.upper(),  # NORMAL, INTRADAY, DELIVERY, BNPL
            "orderType": order_type.upper(),  # LIMIT, MARKET, SL, SLM
            "validity": "DAY"  # Required field
        }
        
        # Add price for LIMIT and SL orders
        if price and order_type.upper() in ["LIMIT", "SL"]:
            order_data["price"] = str(price)
        
        # Add stop loss trigger price for SL and SLM orders
        if stop_loss and order_type.upper() in ["SL", "SLM"]:
            order_data["slTriggerPrice"] = str(stop_loss)
            
        # Add bracket order legs if specified
        if order_data["orderComplexity"] in ["BO", "CO"]:
            if stop_loss:
                order_data["slLegPrice"] = str(stop_loss)
            if take_profit:
                order_data["targetLegPrice"] = str(take_profit)
        
        return order_data
    
    async def is_market_open(self) -> bool:
        """Check if market is currently open"""
        try:
            # Simple check - try to get market quotes for NIFTY
            result = await self.get_market_quotes(["NIFTY"])
            return result is not None
        except:
            return False
    
    def _resolve_instrument_id_with_variants(self, symbol: str, local_map: Dict[str, str]) -> Optional[str]:
        """Resolve symbol to instrumentId using same logic as DataFetcher for consistency"""
        if not symbol:
            return None
        base_symbol = str(symbol).upper().strip()
        simple_base = ''.join(ch for ch in base_symbol if ch.isalnum())
        base_part = base_symbol.split("-", 1)[0] if "-" in base_symbol else base_symbol
        
        candidates = [
            base_symbol, base_part, f"{base_part}-EQ", f"{base_part}-BE", f"{base_part}-SM"
        ]
        if simple_base:
            candidates.append(simple_base)
            candidates.append(f"{simple_base}EQ")
        
        # Try candidates in order
        for candidate in candidates:
            if candidate in local_map:
                return str(local_map[candidate])
        
        # Fallback: contains match
        for k, v in local_map.items():
            ku = k.upper()
            if simple_base and simple_base in ''.join(ch for ch in ku if ch.isalnum()):
                return str(v)
            if base_part and base_part in ku:
                return str(v)
        return None

    def _load_normalized_contract_map(self) -> Dict[str, str]:
        """Load and normalize contract map with same logic as DataFetcher"""
        local_map: Dict[str, str] = {}
        try:
            local_path = os.path.join(os.getcwd(), "data", "contracts_nseeq.json")
            if os.path.exists(local_path):
                with open(local_path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                    for k, v in file_data.items():
                        try:
                            kk = str(k).upper().strip()
                            local_map[kk] = str(v)
                            # Also store alnum-only variant
                            simple = ''.join(ch for ch in kk if ch.isalnum())
                            if simple and simple not in local_map:
                                local_map[simple] = str(v)
                        except Exception:
                            continue
        except Exception:
            pass
        return local_map

    async def force_auth_code_refresh(self) -> dict:
        """Force refresh of auth code from env file"""
        logger.info("Refreshing auth code from env file")
        
        # Reload settings to get updated auth code from env
        from config.settings import get_settings
        import config.settings
        config.settings._settings = None  # Clear cached settings
        self.settings = get_settings()
        self.auth_code = self.settings.iifl_auth_code
        
        # Clear existing session to force re-authentication
        self.session_token = None
        self.token_expiry = None
        self._save_token_to_cache("") # Clear cached token
        
        return await self.authenticate()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_authenticated()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Note: For a singleton service, we don't close the client here
        # as it might be in use by other parts of the application.
        # The client should be closed on application shutdown.
        # await self.close_http_client()
        pass
