import asyncio
import json
import hashlib
import httpx
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import logging
import os
import time
from services.logging_service import trading_logger

logger = logging.getLogger(__name__)

class IIFLAPIService:
    """IIFL Markets API integration service using checksum-based authentication"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IIFLAPIService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # Lazy-load settings with fallback to env to avoid hard dependency on pydantic
            self._load_settings()
            self.session_token: Optional[str] = None
            self.token_expiry: Optional[datetime] = None
            # Track auth code expiry for UI; IIFL auth codes are day-bound
            self.auth_code_expiry: Optional[datetime] = None
            self.http_client: Optional[httpx.AsyncClient] = None
            self.get_user_session_endpoint = "/getusersession"
            # Initialize an auth-code expiry hint
            try:
                self._initialize_auth_expiry()
            except Exception:
                pass
            IIFLAPIService._initialized = True

    def _load_settings(self) -> None:
        """Load settings using config.settings if available, else fallback to os.environ."""
        try:
            from config.settings import get_settings  # type: ignore
            settings = get_settings()
            self.client_id = settings.iifl_client_id
            self.auth_code = settings.iifl_auth_code
            self.app_secret = settings.iifl_app_secret
            # Backward compatibility: single base_url
            self.base_url = settings.iifl_base_url
            self.settings = settings
        except Exception:
            # Minimal fallback using environment variables directly
            self.client_id = os.getenv("IIFL_CLIENT_ID", "")
            self.auth_code = os.getenv("IIFL_AUTH_CODE", "")
            self.app_secret = os.getenv("IIFL_APP_SECRET", "")
            # Backward compatibility: single base_url
            self.base_url = os.getenv("IIFL_BASE_URL", "https://api.iiflcapital.com/v1")
            self.settings = type("_FallbackSettings", (), {
                "iifl_client_id": self.client_id,
                "iifl_auth_code": self.auth_code,
                "iifl_app_secret": self.app_secret,
                "iifl_base_url": self.base_url,
            })()
    
    async def get_http_client(self) -> httpx.AsyncClient:
        """Get or create an httpx.AsyncClient instance."""
        if self.http_client is None or self.http_client.is_closed:
            self.http_client = httpx.AsyncClient(timeout=30.0)
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
            
            return {}
    
    async def authenticate(self) -> bool:
        """Authenticate with IIFL API using checksum-based authentication"""
        if not self.auth_code:
            logger.error("No auth code available for authentication")
            return False
        
        try:
            logger.info("Attempting IIFL API authentication with checksum method")
            
            # Use the working authentication method
            response_data = await self.get_user_session(self.auth_code)
            
            if response_data:
                logger.info(f"Authentication response received: {json.dumps(response_data)}")
                
                # Handle both old and new IIFL API response formats
                if response_data.get("stat") == "Ok" or response_data.get("status") == "Ok":
                    # Extract session token from multiple possible fields
                    session_token = (response_data.get("SessionToken") or 
                                   response_data.get("sessionToken") or 
                                   response_data.get("session_token") or
                                   response_data.get("userSession") or
                                   response_data.get("token"))
                    
                    if session_token:
                        self.session_token = session_token
                        self.token_expiry = None  # No expiry - token valid indefinitely
                        logger.info(f"IIFL authentication successful. Token: {session_token[:10]}...")
                        trading_logger.log_system_event("iifl_auth_success", {
                            "token_preview": session_token[:10] + "...",
                            "token_expiry": None,
                            "response_format": "stat" if "stat" in response_data else "status"
                        })
                        return True
                    else:
                        logger.error("No session token found in IIFL response")
                        trading_logger.log_error("iifl_auth_no_token", {
                            "response_keys": list(response_data.keys()),
                            "response_sample": str(response_data)[:200]
                        })
                elif response_data.get("stat") == "Not_ok" or response_data.get("status") == "Not_ok":
                    error_msg = response_data.get("emsg") or response_data.get("message", "Authentication failed")
                    logger.error(f"IIFL authentication failed: {error_msg}")
                    trading_logger.log_error("iifl_auth_failed", {
                        "error_message": error_msg,
                        "response": response_data
                    })
                else:
                    # Log unknown response structure for debugging
                    logger.warning(f"Unknown IIFL response structure: {json.dumps(response_data)}")
                    trading_logger.log_system_event("iifl_auth_unknown_response", {
                        "response_keys": list(response_data.keys()),
                        "response_sample": str(response_data)[:200]
                    })
            
            # If authentication fails, allow mock token only in non-production
            logger.error("IIFL authentication failed")
            env_name = str(getattr(self.settings, "environment", "development")).lower()
            if env_name in ["development", "dev", "test", "testing"]:
                logger.info("Creating mock session for development/testing")
                self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.token_expiry = None
                return True
            else:
                logger.error("Authentication failed and mock tokens are disabled in this environment")
                return False
                
        except Exception as e:
            logger.error(f"IIFL API authentication exception: {str(e)}")
            env_name = str(getattr(self.settings, "environment", "development")).lower()
            if env_name in ["development", "dev", "test", "testing"]:
                logger.info("Creating mock session for development/testing")
                self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self.token_expiry = None
                return True
            else:
                logger.error("Authentication exception and mock tokens are disabled in this environment")
                return False
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication"""
        # If we have a token, use it (no expiry check)
        if self.session_token:
            logger.debug(f"Using existing session token: {self.session_token[:10]}...")
            return True
            
        # Only authenticate if we don't have a token
        if not self.session_token:
            logger.info("No session token found, attempting authentication")
            return await self.authenticate()
        
        return True
    
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
                "data_keys": list(request_body.keys())
            })

            try:
                attempted_reauth = False
                while True:
                    attempt_start = time.perf_counter()
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
                            error=None if response.status_code == 200 else f"HTTP {response.status_code}"
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
                        reauth_ok = await self.authenticate()
                        attempted_reauth = True
                        if reauth_ok and self.session_token and not str(self.session_token).startswith("mock_"):
                            continue  # Retry once with new token
                        else:
                            logger.error("Re-authentication failed or mock token obtained; aborting retry for production flow.")
                            break

                    # Other non-200 statuses
                    error_msg = f"IIFL API request failed: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    trading_logger.log_api_call(
                        endpoint=url,
                        method=method.upper(),
                        status_code=response.status_code,
                        response_time=response_time,
                        error=f"HTTP {response.status_code}: {response.text[:200]}"
                    )
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
                    error=str(e)
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
    
    # User Profile & Limits
    async def get_profile(self) -> Optional[Dict]:
        """Get user profile information"""
        return await self._make_api_request("GET", "/profile")
    
    # Removed: get_limits (IIFL does not offer /limits). Use calculate_pre_order_margin via DataFetcher.
    
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
        """Get historical OHLCV data"""
        # Preserve numeric instrument IDs; for string symbols normalize case and strip known suffixes
        normalized_symbol = symbol
        try:
            int(str(symbol).strip())
        except ValueError:
            normalized_symbol = str(symbol).upper().strip()
            # Strip common suffixes like -EQ, -BE, -BZ, -SM, etc. for a base variant
            if "-" in normalized_symbol:
                base_part = normalized_symbol.split("-", 1)[0]
            else:
                base_part = normalized_symbol

        def _has_payload(resp: Optional[Dict]) -> bool:
            if not isinstance(resp, dict):
                return False
            # Prefer explicit data containers; verify they are not error lists
            for key in ["result", "data", "resultData", "candles", "history"]:
                value = resp.get(key)
                if isinstance(value, list) and len(value) > 0:
                    first_item = value[0] if len(value) > 0 else {}
                    # Detect error objects like {"status": "EC802", ...}
                    if isinstance(first_item, dict) and str(first_item.get("status", "")).startswith("EC"):
                        return False
                    return True
            # Top-level Ok without data is not a payload
            return False

        # Build a conservative list of attempts to maximize compatibility while limiting API calls
        attempts: list[dict] = []

        # Date variants
        yyyy_mm_dd_from = from_date
        yyyy_mm_dd_to = to_date
        try:
            # Convert to dd-mm-yyyy as a fallback format
            from_dt_parsed = datetime.strptime(from_date, "%Y-%m-%d")
            to_dt_parsed = datetime.strptime(to_date, "%Y-%m-%d")
            dd_mm_yyyy_from = from_dt_parsed.strftime("%d-%m-%Y")
            dd_mm_yyyy_to = to_dt_parsed.strftime("%d-%m-%Y")
        except Exception:
            dd_mm_yyyy_from = from_date
            dd_mm_yyyy_to = to_date

        # dd-Mon-YYYY (e.g., 17-sep-2025) lowercased variant observed to work in direct script
        try:
            if 'from_dt_parsed' in locals() and 'to_dt_parsed' in locals():
                dd_mon_yyyy_from = from_dt_parsed.strftime("%d-%b-%Y").lower()
                dd_mon_yyyy_to = to_dt_parsed.strftime("%d-%b-%Y").lower()
            else:
                # Try parsing dd-mm-yyyy if provided
                _from_tmp = datetime.strptime(from_date, "%d-%m-%Y")
                _to_tmp = datetime.strptime(to_date, "%d-%m-%Y")
                dd_mon_yyyy_from = _from_tmp.strftime("%d-%b-%Y").lower()
                dd_mon_yyyy_to = _to_tmp.strftime("%d-%b-%Y").lower()
        except Exception:
            # Fallback to original strings (may already be in desired format)
            dd_mon_yyyy_from = from_date
            dd_mon_yyyy_to = to_date

        # Normalize interval to accepted IIFL values to avoid EC802
        def _normalize_interval_value(user_interval: str) -> str:
            s = str(user_interval).strip().lower()
            # Directly accepted by IIFL
            accepted = {"1 minute", "5 minutes", "10 minutes", "15 minutes", "30 minutes", "60 minutes", "1 day", "weekly", "monthly"}
            if s in accepted:
                return s
            mapping = {
                # Day variants
                "1d": "1 day", "d": "1 day", "day": "1 day", "1day": "1 day", "1 day": "1 day", "1day": "1 day",
                # Minute variants
                "1m": "1 minute", "1 min": "1 minute", "1minute": "1 minute", "minute": "1 minute",
                "5m": "5 minutes", "5 min": "5 minutes", "5minute": "5 minutes",
                "10m": "10 minutes", "10 min": "10 minutes", "10minute": "10 minutes",
                "15m": "15 minutes", "15 min": "15 minutes", "15minute": "15 minutes",
                "30m": "30 minutes", "30 min": "30 minutes", "30minute": "30 minutes",
                # Hour variants -> 60 minutes
                "60m": "60 minutes", "60 min": "60 minutes", "1h": "60 minutes", "hour": "60 minutes", "h": "60 minutes", "60minutes": "60 minutes",
                # Week/Month variants
                "1w": "weekly", "week": "weekly", "wk": "weekly", "w": "weekly",
                "1mo": "monthly", "1mth": "monthly", "month": "monthly", "mth": "monthly"
            }
            return mapping.get(s, "1 day")

        interval_value = _normalize_interval_value(interval)
        interval_variants = [interval_value]

        # Symbol candidates
        is_numeric_symbol = False
        try:
            int(str(normalized_symbol))
            is_numeric_symbol = True
        except ValueError:
            is_numeric_symbol = False

        symbol_variants: list[str] = []
        # Start with exact normalized symbol
        symbol_variants.append(str(normalized_symbol))
        if not is_numeric_symbol:
            # Add base-part without suffix if available
            if 'base_part' in locals() and base_part and base_part != normalized_symbol:
                symbol_variants.append(base_part)
            # Ensure we try explicit -EQ suffix too
            if not str(normalized_symbol).endswith("-EQ"):
                symbol_variants.append(f"{base_part if 'base_part' in locals() else normalized_symbol}-EQ")
        # Dedupe while preserving order
        seen: set[str] = set()
        symbol_variants = [s for s in symbol_variants if not (s in seen or seen.add(s))]

        # 1) Primary: symbol + fromDate/toDate
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "symbol_fromDate_toDate"
                })

        # 2) Alternative keys: symbol + from/to
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "from": yyyy_mm_dd_from, "to": yyyy_mm_dd_to},
                    "desc": "symbol_from_to"
                })

        # 3) Alternative date format: dd-mm-yyyy with from/to
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "from": dd_mm_yyyy_from, "to": dd_mm_yyyy_to},
                    "desc": "symbol_from_to_ddmmyyyy"
                })

        # 3b) Alternative date format: dd-mm-yyyy with fromDate/toDate
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "fromDate": dd_mm_yyyy_from, "toDate": dd_mm_yyyy_to},
                    "desc": "symbol_fromDate_toDate_ddmmyyyy"
                })

        # 3c) Alternative date format: dd-Mon-YYYY lower with fromDate/toDate
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "fromDate": dd_mon_yyyy_from, "toDate": dd_mon_yyyy_to},
                    "desc": "symbol_fromDate_toDate_ddMonYYYY"
                })

        # 4) Include exchange hints with symbol
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "exchange": "NSEEQ", "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "symbol_exchange_fromDate_toDate"
                })
        # 4a-alt) exchange + dd-Mon-YYYY lower
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "exchange": "NSEEQ", "interval": iv, "fromDate": dd_mon_yyyy_from, "toDate": dd_mon_yyyy_to},
                    "desc": "symbol_exchange_fromDate_toDate_ddMonYYYY"
                })
        # 4a) exchange 'NSE' + series 'EQ'
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "exchange": "NSE", "series": "EQ", "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "symbol_exchange_series_fromDate_toDate"
                })
        # 4b) exchangeSegment flavor
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "exchange": "NSE", "exchangeSegment": "NSECM", "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "symbol_exchange_exchangeSegment_fromDate_toDate"
                })
        # 4c) exch/exchType short keys commonly used in some IIFL specs
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "exch": "N", "exchType": "C", "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "symbol_exch_exchType_fromDate_toDate"
                })
        # 4d) startDate/endDate key variants
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "startDate": yyyy_mm_dd_from, "endDate": yyyy_mm_dd_to},
                    "desc": "symbol_startDate_endDate"
                })
        for sym in symbol_variants:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"symbol": sym, "interval": iv, "startDate": dd_mm_yyyy_from, "endDate": dd_mm_yyyy_to},
                    "desc": "symbol_startDate_endDate_ddmmyyyy"
                })

        # 5) Numeric instrumentId variant if the provided symbol is numeric
        if is_numeric_symbol:
            for iv in interval_variants:
                attempts.append({
                    "payload": {"instrumentId": str(normalized_symbol), "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "instrumentId_fromDate_toDate"
                })
                attempts.append({
                    "payload": {"instrumentId": str(normalized_symbol), "interval": iv, "from": yyyy_mm_dd_from, "to": yyyy_mm_dd_to},
                    "desc": "instrumentId_from_to"
                })
                # instrument key alias
                attempts.append({
                    "payload": {"instrument": str(normalized_symbol), "interval": iv, "fromDate": yyyy_mm_dd_from, "toDate": yyyy_mm_dd_to},
                    "desc": "instrument_fromDate_toDate"
                })
                # instrumentId with dd-Mon-YYYY lower
                attempts.append({
                    "payload": {"instrumentId": str(normalized_symbol), "interval": iv, "fromDate": dd_mon_yyyy_from, "toDate": dd_mon_yyyy_to},
                    "desc": "instrumentId_fromDate_toDate_ddMonYYYY"
                })
                # instrumentId + exchange with dd-Mon-YYYY lower and explicit interval variant
                attempts.append({
                    "payload": {"instrumentId": str(normalized_symbol), "exchange": "NSEEQ", "interval": iv, "fromDate": dd_mon_yyyy_from, "toDate": dd_mon_yyyy_to},
                    "desc": "instrumentId_exchange_fromDate_toDate_ddMonYYYY"
                })

        # Execute attempts sequentially until one yields data
        last_response: Optional[Dict] = None
        for idx, attempt in enumerate(attempts, start=1):
            payload = attempt["payload"]
            desc = attempt["desc"]
            trading_logger.log_system_event("iifl_hist_attempt", {
                "attempt": idx,
                "variant": desc,
                "payload_keys": list(payload.keys())
            })
            response = await self._make_api_request("POST", "/marketdata/historicaldata", payload)
            last_response = response
            if _has_payload(response):
                trading_logger.log_system_event("iifl_hist_success", {
                    "attempt": idx,
                    "variant": desc
                })
                return response

        # If none succeeded, return the last response for visibility
        return last_response
    
    async def get_market_quotes(self, instruments: List[str]) -> Optional[Dict]:
        """Get real-time market quotes"""
        data = {"instruments": instruments}
        return await self._make_api_request("POST", "/marketdata/marketquotes", data)
    
    async def get_market_depth(self, instrument: str) -> Optional[Dict]:
        """Get market depth for an instrument"""
        data = {"instrument": instrument}
        return await self._make_api_request("POST", "/marketdata/marketdepth", data)
    
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
    
    async def force_auth_code_refresh(self) -> bool:
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
