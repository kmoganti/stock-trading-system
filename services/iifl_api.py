import asyncio
import json
import hashlib
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import os
import time
from config.settings import get_settings
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
            self.settings = get_settings()
            self.client_id = self.settings.iifl_client_id
            self.auth_code = self.settings.iifl_auth_code
            self.app_secret = self.settings.iifl_app_secret
            self.base_url = self.settings.iifl_base_url
            self.session_token: Optional[str] = None
            self.token_expiry: Optional[datetime] = None
            self.get_user_session_endpoint = "/getusersession"
            IIFLAPIService._initialized = True
    
    
    
    
    def sha256_hash(self, input_string: str) -> str:
        """Returns the SHA-256 hash of the input string."""
        return hashlib.sha256(input_string.encode('utf-8')).hexdigest()
    
    def get_user_session(self, auth_code: str) -> Dict:
        """Request a new user session from the IIFL API using checksum authentication."""
        start_time = time.time()
        
        # Construct the checksum required by the API
        checksum_str = self.client_id + auth_code + self.app_secret
        checksum = self.sha256_hash(checksum_str)

        url = self.base_url + self.get_user_session_endpoint
        headers = {"Content-Type": "application/json"}
        
        # The payload for the session request includes the checksum
        payload = {
            "checkSum": checksum
        }
        
        # Enhanced logging for IIFL API calls
        logger.info(f"IIFL API Request: POST {url}")
        logger.debug(f"Request headers: {headers}")
        logger.debug(f"Request payload: {payload}")
        
        # Log to specialized API logger
        trading_logger.log_system_event("iifl_api_request", {
            "method": "POST",
            "url": url,
            "endpoint": self.get_user_session_endpoint,
            "payload_keys": list(payload.keys())
        })
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            response_time = time.time() - start_time
            
            # Enhanced response logging
            logger.info(f"IIFL API Response: {response.status_code} in {response_time:.3f}s")
            logger.debug(f"Response headers: {dict(response.headers)}")
            logger.debug(f"Response text: {response.text}")
            
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
            
        except requests.exceptions.RequestException as e:
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
            response_data = self.get_user_session(self.auth_code)
            
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
            
            # If authentication fails, create mock session for development
            logger.error("IIFL authentication failed")
            logger.info("Creating mock session for development")
            self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.token_expiry = None
            return True
                
        except Exception as e:
            logger.error(f"IIFL API authentication exception: {str(e)}")
            logger.info("Creating mock session for development")
            self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.token_expiry = None
            return True
    
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
        """Make authenticated API request using session token"""
        if not await self._ensure_authenticated():
            return None
        
        start_time = time.time()
        url = f"{self.base_url}{endpoint}"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "IIFL-Trading-System/1.0",
                "Authorization": f"Bearer {self.session_token}"
            }
            
            # Initialize data if None
            if data is None:
                data = {}
            
            # Enhanced request logging
            logger.info(f"IIFL API Request: {method.upper()} {url}")
            logger.debug(f"Request headers: {headers}")
            logger.debug(f"Request data (without token): {json.dumps({k: v for k, v in data.items() if k != 'SessionToken'})}")
            
            # Log to specialized API logger
            trading_logger.log_system_event("iifl_api_request", {
                "method": method.upper(),
                "url": url,
                "endpoint": endpoint,
                "has_bearer_token": bool(self.session_token),
                "data_keys": list(data.keys())
            })

            try:
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, params=data, timeout=30)
                elif method.upper() == "POST":
                    response = requests.post(url, headers=headers, data=json.dumps(data), timeout=30)
                elif method.upper() == "PUT":
                    response = requests.put(url, headers=headers, data=json.dumps(data), timeout=30)
                elif method.upper() == "DELETE":
                    response = requests.delete(url, headers=headers, timeout=30)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                response_time = time.time() - start_time
                
                # Enhanced response logging
                logger.info(f"IIFL API Response: {response.status_code} in {response_time:.3f}s")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                try:
                    response_data = response.json()
                    logger.debug(f"Response data: {json.dumps(response_data)}")
                    
                    # Log successful API call
                    trading_logger.log_api_call(
                        endpoint=url,
                        method=method.upper(),
                        status_code=response.status_code,
                        response_time=response_time,
                        error=None if response.status_code == 200 else f"HTTP {response.status_code}"
                    )
                    
                    # Log response details
                    trading_logger.log_system_event("iifl_api_response", {
                        "url": url,
                        "method": method.upper(),
                        "status_code": response.status_code,
                        "response_time_ms": response_time * 1000,
                        "response_keys": list(response_data.keys()) if isinstance(response_data, dict) else "non_dict",
                        "success": response.status_code == 200
                    })
                    
                except json.JSONDecodeError:
                    logger.debug(f"Response data (non-JSON): {response.text}")
                    response_data = None

                if response.status_code == 200:
                    return response_data
                else:
                    error_msg = f"IIFL API request failed: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    
                    # Log API error
                    trading_logger.log_api_call(
                        endpoint=url,
                        method=method.upper(),
                        status_code=response.status_code,
                        response_time=response_time,
                        error=f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    
                    return None
                    
            except requests.exceptions.RequestException as e:
                response_time = time.time() - start_time
                error_msg = f"IIFL API request exception: {str(e)}"
                logger.error(error_msg)
                
                # Log request exception
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
            response_time = time.time() - start_time
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
    
    async def get_limits(self) -> Optional[Dict]:
        """Get trading limits and margin information"""
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
        data = {
            "symbol": symbol,
            "interval": interval,
            "fromDate": from_date,
            "toDate": to_date
        }
        return await self._make_api_request("POST", "/marketdata/historicaldata", data)
    
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
        # Clean up resources if needed
        # For now, we don't need to do anything special on exit
        pass
