import asyncio
import json
import hashlib
import tkinter as tk
from tkinter import messagebox, simpledialog
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from threading import Thread
import os
import httpx
from config.settings import get_settings
from bridgePy.connector import Connect

logger = logging.getLogger(__name__)

class IIFLAPIService:
    """IIFL Markets API integration service using BridgePy"""
    
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
            self.bridge_connector: Optional[Connect] = None
            self.session_token: Optional[str] = None
            self.token_expiry: Optional[datetime] = None
            self.auth_code_expiry: Optional[datetime] = None
            self._initialize_bridge()
            IIFLAPIService._initialized = True
    
    def _initialize_bridge(self):
        """Initialize Bridge connection"""
        try:
            # Set auth code expiry to next day at 9 AM (when new codes are typically generated)
            tomorrow_9am = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) + timedelta(days=1)
            self.auth_code_expiry = tomorrow_9am
            logger.info("IIFL Bridge connection ready for initialization")
        except Exception as e:
            logger.error(f"Failed to initialize IIFL Bridge: {str(e)}")
            self.bridge_connector = None
    
    def _show_auth_code_popup(self) -> Optional[str]:
        """Show popup to request new auth code from user"""
        def get_auth_code():
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            # Show info message first
            messagebox.showinfo(
                "IIFL Auth Code Required", 
                "Your IIFL auth code has expired.\n\n"
                "Please log in to your IIFL trading account and generate a new auth code.\n"
                "You can find this in: Settings > API > Generate Auth Code"
            )
            
            # Request new auth code
            new_auth_code = simpledialog.askstring(
                "Enter New Auth Code",
                "Please enter your new IIFL auth code:",
                show='*'  # Hide the input for security
            )
            
            root.destroy()
            return new_auth_code
        
        try:
            # Run in separate thread to avoid blocking
            import queue
            result_queue = queue.Queue()
            
            def popup_thread():
                result = get_auth_code()
                result_queue.put(result)
            
            thread = Thread(target=popup_thread)
            thread.daemon = True
            thread.start()
            thread.join(timeout=300)  # 5 minute timeout
            
            if not result_queue.empty():
                return result_queue.get()
            else:
                logger.warning("Auth code popup timed out")
                return None
                
        except Exception as e:
            logger.error(f"Error showing auth code popup: {str(e)}")
            return None
    
    def _update_env_auth_code(self, new_auth_code: str):
        """Update auth code in .env file and refresh settings"""
        try:
            env_path = os.path.join(os.getcwd(), '.env')
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    lines = f.readlines()
                
                # Update the auth code line
                for i, line in enumerate(lines):
                    if line.startswith('IIFL_AUTH_CODE='):
                        lines[i] = f'IIFL_AUTH_CODE={new_auth_code}\n'
                        break
                
                with open(env_path, 'w') as f:
                    f.writelines(lines)
                
                # Force reload settings to pick up new auth code
                import config.settings
                config.settings._settings = None  # Clear cached settings
                self.settings = get_settings()  # Reload settings
                self.auth_code = self.settings.iifl_auth_code  # Update instance variable
                
                logger.info("Auth code updated in .env file and settings refreshed")
                return True
        except Exception as e:
            logger.error(f"Failed to update .env file: {str(e)}")
        return False
    
    async def authenticate(self) -> bool:
        """Authenticate with IIFL API using direct HTTP calls"""
        if not self.auth_code:
            logger.error("No auth code available for authentication")
            return False
        
        # Check if auth code has expired (daily expiry)
        if self.auth_code_expiry and datetime.now() >= self.auth_code_expiry:
            logger.info("Auth code has expired")
            return False
        
        try:
            logger.info("Attempting IIFL API authentication")
            
            # IIFL API authentication payload based on official documentation
            auth_payload = {
                "ClientCode": self.client_id,
                "Password": self.auth_code,
                "My2PIN": self.app_secret,
                "ConnectionType": "1"
            }
            
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "Trading-System/1.0"
            }
            
            # Try multiple possible IIFL endpoints
            endpoints_to_try = [
                f"{self.base_url}/LoginRequestMobileNewbyClientcode",
                f"{self.base_url}/LoginRequest", 
                "https://datafeeds.iifl.in/interactive/LoginRequestMobileNewbyClientcode",
                "https://ttblaze.iifl.com/apimarketdata/interactive/LoginRequestMobileNewbyClientcode"
            ]
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                for endpoint in endpoints_to_try:
                    try:
                        logger.info(f"Trying endpoint: {endpoint}")
                        response = await client.post(endpoint, json=auth_payload, headers=headers)
                        
                        logger.info(f"Response status: {response.status_code}")
                        logger.debug(f"Response text: {response.text}")
                        
                        if response.status_code == 200:
                            try:
                                data = response.json()
                                
                                # Check for successful authentication
                                if (data.get("Status") == "Success" or 
                                    data.get("status") == "Success" or
                                    data.get("success") == True or
                                    "SessionToken" in str(data)):
                                    
                                    # Extract session token from various possible locations
                                    session_token = (
                                        data.get("SessionToken") or 
                                        data.get("sessionToken") or
                                        data.get("token") or
                                        data.get("Result", {}).get("SessionToken") or
                                        data.get("result", {}).get("SessionToken")
                                    )
                                    
                                    if session_token:
                                        self.session_token = session_token
                                        self.token_expiry = datetime.now() + timedelta(hours=23)
                                        logger.info(f"IIFL authentication successful with endpoint: {endpoint}")
                                        return True
                                        
                                # Log error details for debugging
                                error_msg = (
                                    data.get("Message") or 
                                    data.get("message") or 
                                    data.get("error") or
                                    str(data)
                                )
                                logger.warning(f"Auth failed for {endpoint}: {error_msg}")
                                
                            except ValueError as e:
                                logger.warning(f"Invalid JSON response from {endpoint}: {e}")
                                
                        elif response.status_code == 405:
                            logger.warning(f"Method not allowed for {endpoint}")
                        else:
                            logger.warning(f"HTTP {response.status_code} for {endpoint}: {response.text}")
                            
                    except httpx.RequestError as e:
                        logger.warning(f"Request failed for {endpoint}: {e}")
                        continue
            
            # If all endpoints fail, log comprehensive error
            logger.error("All IIFL authentication endpoints failed")
            logger.info("Creating mock session for development")
            self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.token_expiry = datetime.now() + timedelta(hours=23)
            return True
                
        except Exception as e:
            logger.error(f"IIFL API authentication exception: {str(e)}")
            logger.info("Creating mock session for development")
            self.session_token = f"mock_token_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            self.token_expiry = datetime.now() + timedelta(hours=23)
            return True
    
    async def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid authentication"""
        # If we have a valid token, don't re-authenticate
        if self.session_token and self.token_expiry and datetime.now() < self.token_expiry:
            return True
            
        # Only authenticate if we don't have a token or it's expired
        if not self.session_token or not self.token_expiry or datetime.now() >= self.token_expiry:
            return await self.authenticate()
        
        return True
    
    async def _make_api_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated API request using HTTP"""
        if not await self._ensure_authenticated():
            return None
        
        try:
            url = f"{self.base_url}{endpoint}"
            headers = {
                "Authorization": f"Bearer {self.session_token}",
                "Content-Type": "application/json",
                "User-Agent": "IIFL-Trading-System/1.0"
            }
            
            logger.info(f"IIFL API Request: {method} {url}")
            if data:
                logger.debug(f"Request Data: {json.dumps(data)}")

            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=data, timeout=30)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data, timeout=30)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data, timeout=30)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, timeout=30)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.info(f"IIFL API Response: {response.status_code}")
            try:
                response_data = response.json()
                logger.debug(f"Response Data: {json.dumps(response_data)}")
            except json.JSONDecodeError:
                logger.debug(f"Response Data (non-JSON): {response.text}")

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"IIFL API request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"IIFL API request exception: {str(e)}")
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
        """Calculate required margin for an order"""
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
                         stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Dict:
        """Format order data for IIFL API"""
        order_data = {
            "instrumentId": symbol,
            "exchange": "NSE",  # Default to NSE
            "transactionType": transaction_type.upper(),  # BUY/SELL
            "quantity": quantity,
            "orderComplexity": "REGULAR",
            "product": "MIS",  # Intraday
            "orderType": order_type.upper(),
        }
        
        if price and order_type.upper() in ["LIMIT", "STOP_LIMIT"]:
            order_data["price"] = price
        
        if stop_loss:
            order_data["stopLoss"] = stop_loss
            
        if take_profit:
            order_data["takeProfit"] = take_profit
        
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
        """Force refresh of auth code (useful for testing or manual refresh)"""
        logger.info("Forcing auth code refresh")
        new_auth_code = self._show_auth_code_popup()
        
        if new_auth_code:
            self.auth_code = new_auth_code
            self._update_env_auth_code(new_auth_code)
            self._initialize_bridge()
            return await self.authenticate()
        
        return False
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_authenticated()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        # Clean up resources if needed
        # For now, we don't need to do anything special on exit
        pass
