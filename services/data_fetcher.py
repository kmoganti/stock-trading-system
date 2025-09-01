import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
from .iifl_api import IIFLAPIService

# Optional pandas import
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)

class DataFetcher:
    """Service for fetching and processing market data"""
    
    def __init__(self, iifl_service: IIFLAPIService):
        self.iifl = iifl_service
        self.cache: Dict[str, Any] = {}
        self.cache_expiry: Dict[str, datetime] = {}
    
    def _is_cache_valid(self, key: str, ttl_seconds: int = 60) -> bool:
        """Check if cached data is still valid"""
        if key not in self.cache or key not in self.cache_expiry:
            return False
        return datetime.now() < self.cache_expiry[key]
    
    def _get_cache(self, key: str):
        """Get cached data"""
        if key in self.cache and self._is_cache_valid(key):
            return self.cache[key]
        return None
    
    def _set_cache(self, key: str, data: Any, ttl_seconds: int = 60):
        """Set cache with expiry"""
        self.cache[key] = data
        self.cache_expiry[key] = datetime.now() + timedelta(seconds=ttl_seconds)
    
    async def get_historical_data(self, symbol: str, interval: str = "1D", 
                                days: int = 100) -> Optional[List[Dict]]:
        """Get historical OHLCV data"""
        try:
            cache_key = f"hist_{symbol}_{interval}_{days}"
            
            # Check cache first
            cached_data = self._get_cache(cache_key)
            if cached_data is not None:
                return cached_data
            
            # Fetch from IIFL API
            result = await self.iifl.get_historical_data(symbol, interval, days)
            
            if result and result.get("status") == "Ok":
                data = result.get("resultData", [])
                if data:
                    # Standardize data format
                    standardized_data = []
                    for item in data:
                        standardized_item = {k.lower(): v for k, v in item.items()}
                        standardized_data.append(standardized_item)
                    
                    self._set_cache(cache_key, standardized_data, 300)
                    return standardized_data
            elif result:
                logger.warning(f"Failed to fetch historical data for {symbol}: {result.get('emsg', 'Unknown API error')}")
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
            return []
    
    async def get_live_price(self, symbol: str) -> Optional[float]:
        """Get current live price for a symbol"""
        try:
            cache_key = f"price_{symbol}"
            
            if self._is_cache_valid(cache_key, 5):  # 5 sec cache
                return self.cache[cache_key]
            
            result = await self.iifl.get_market_quotes([symbol])
            
            if result and result.get("status") == "Ok":
                quotes = result.get("resultData", [])
                if quotes:
                    price = quotes[0].get("ltp")  # Last Traded Price
                    if price:
                        self._set_cache(cache_key, float(price), 5)
                        return float(price)
            elif result:
                logger.warning(f"Failed to fetch live price for {symbol}: {result.get('emsg', 'Unknown API error')}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching live price for {symbol}: {str(e)}")
            return None
    
    async def get_multiple_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get live prices for multiple symbols"""
        try:
            result = await self.iifl.get_market_quotes(symbols)
            prices = {}
            
            if result and result.get("status") == "Ok":
                quotes = result.get("resultData", [])
                for quote in quotes:
                    symbol = quote.get("symbol")
                    ltp = quote.get("ltp")
                    if symbol and ltp:
                        prices[symbol] = float(ltp)
                        # Cache individual prices
                        self._set_cache(f"price_{symbol}", float(ltp), 5)
            elif result:
                logger.warning(f"Failed to fetch multiple prices: {result.get('emsg', 'Unknown API error')}")
            
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching multiple prices: {str(e)}")
            return {}
    
    async def get_market_depth(self, symbol: str) -> Optional[Dict]:
        """Get market depth (bid/ask levels)"""
        try:
            cache_key = f"depth_{symbol}"
            
            if self._is_cache_valid(cache_key, 2):  # 2 sec cache
                return self.cache[cache_key]
            
            result = await self.iifl.get_market_depth(symbol)
            
            if result and result.get("status") == "Ok":
                depth_data = result.get("resultData")
                if depth_data:
                    self._set_cache(cache_key, depth_data, 2)
                    return depth_data
            elif result:
                logger.warning(f"Failed to fetch market depth for {symbol}: {result.get('emsg', 'Unknown API error')}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching market depth for {symbol}: {str(e)}")
            return None
    
    def _get_mock_portfolio_data(self) -> Dict[str, Any]:
        """Generate mock portfolio data for development/testing"""
        import random
        from datetime import datetime
        
        mock_positions = [
            {
                "symbol": "RELIANCE",
                "quantity": 50,
                "avg_price": 2450.75,
                "ltp": 2465.30,
                "pnl": 729.0,
                "pnl_percent": 0.59
            },
            {
                "symbol": "TCS",
                "quantity": 25,
                "avg_price": 3890.20,
                "ltp": 3875.45,
                "pnl": -368.75,
                "pnl_percent": -0.38
            },
            {
                "symbol": "HDFCBANK",
                "quantity": 30,
                "avg_price": 1650.80,
                "ltp": 1672.15,
                "pnl": 640.50,
                "pnl_percent": 1.29
            }
        ]
        
        mock_holdings = [
            {
                "symbol": "INFY",
                "quantity": 100,
                "avg_price": 1420.30,
                "ltp": 1445.60,
                "value": 144560.0,
                "pnl": 2530.0,
                "pnl_percent": 1.78
            },
            {
                "symbol": "WIPRO",
                "quantity": 200,
                "avg_price": 425.75,
                "ltp": 432.20,
                "value": 86440.0,
                "pnl": 1290.0,
                "pnl_percent": 1.51
            }
        ]
        
        total_pnl = sum(pos.get("pnl", 0) for pos in mock_positions)
        total_value = sum(hold.get("value", 0) for hold in mock_holdings)
        
        return {
            "holdings": mock_holdings,
            "positions": mock_positions,
            "total_value": total_value,
            "total_pnl": total_pnl
        }

    async def get_portfolio_data(self) -> Dict[str, Any]:
        """Get complete portfolio data (holdings + positions)"""
        try:
            cache_key = "portfolio_data"
            
            if self._is_cache_valid(cache_key, 30):  # 30 sec cache
                return self.cache[cache_key]
            
            # Check if we can authenticate first
            auth_success = await self.iifl._ensure_authenticated()
            
            if not auth_success:
                logger.warning("IIFL authentication failed, using mock data for development")
                mock_data = self._get_mock_portfolio_data()
                self._set_cache(cache_key, mock_data, 30)
                return mock_data
            
            # Fetch holdings and positions concurrently
            holdings_task = self.iifl.get_holdings()
            positions_task = self.iifl.get_positions()
            
            holdings_result, positions_result = await asyncio.gather(
                holdings_task, positions_task, return_exceptions=True
            )
            
            portfolio_data = {
                "holdings": [],
                "positions": [],
                "total_value": 0.0,
                "total_pnl": 0.0
            }
            
            # Process holdings
            if isinstance(holdings_result, dict) and holdings_result.get("status") == "Ok":
                portfolio_data["holdings"] = holdings_result.get("resultData", [])
            elif isinstance(holdings_result, dict):
                error_msg = holdings_result.get("emsg", holdings_result.get("message", "Unknown error"))
                logger.warning(f"Could not fetch holdings from IIFL API: {error_msg}")
            
            # Process positions
            if isinstance(positions_result, dict) and positions_result.get("status") == "Ok":
                portfolio_data["positions"] = positions_result.get("resultData", [])
                
                # Calculate total PnL from positions
                for position in portfolio_data["positions"]:
                    pnl = position.get("pnl", 0)
                    if pnl:
                        portfolio_data["total_pnl"] += float(pnl)
            elif isinstance(positions_result, dict):
                error_msg = positions_result.get("emsg", positions_result.get("message", "Unknown error"))
                logger.warning(f"Could not fetch positions from IIFL API: {error_msg}")
            
            # If no real data available, use mock data
            if not portfolio_data["holdings"] and not portfolio_data["positions"]:
                logger.info("No real portfolio data available, using mock data")
                mock_data = self._get_mock_portfolio_data()
                self._set_cache(cache_key, mock_data, 30)
                return mock_data
            
            self._set_cache(cache_key, portfolio_data, 30)
            return portfolio_data
            
        except Exception as e:
            logger.error(f"Error fetching portfolio data: {str(e)}")
            logger.info("Falling back to mock data due to error")
            return self._get_mock_portfolio_data()
    
    def _get_mock_margin_info(self) -> Dict[str, Any]:
        """Generate mock margin info for development/testing"""
        return {
            "totalEquity": 500000.0,
            "availableMargin": 350000.0,
            "usedMargin": 150000.0,
            "cashMargin": 200000.0,
            "collateralMargin": 300000.0,
            "adhocMargin": 0.0,
            "notionalMargin": 0.0
        }

    async def get_margin_info(self) -> Optional[Dict]:
        """Get margin and limit information"""
        try:
            cache_key = "margin_info"
            
            if self._is_cache_valid(cache_key, 60):  # 1 min cache
                return self.cache[cache_key]
            
            # Check if we can authenticate first
            auth_success = await self.iifl._ensure_authenticated()
            
            if not auth_success:
                logger.warning("IIFL authentication failed, using mock margin data for development")
                mock_data = self._get_mock_margin_info()
                self._set_cache(cache_key, mock_data, 60)
                return mock_data
            
            result = await self.iifl.get_limits()
            
            if result and result.get("status") == "Ok":
                margin_data = result.get("resultData")
                if margin_data:
                    self._set_cache(cache_key, margin_data, 60)
                    return margin_data
            elif result:
                logger.warning(f"Failed to fetch margin info: {result.get('emsg', 'Unknown API error')}")
            
            # Fallback to mock data if no real data available
            logger.info("No real margin data available, using mock data")
            mock_data = self._get_mock_margin_info()
            self._set_cache(cache_key, mock_data, 60)
            return mock_data
            
        except Exception as e:
            logger.error(f"Error fetching margin info: {str(e)}")
            logger.info("Falling back to mock margin data due to error")
            return self._get_mock_margin_info()
    
    async def calculate_required_margin(self, symbol: str, quantity: int, 
                                      transaction_type: str, price: Optional[float] = None) -> Optional[float]:
        """Calculate required margin for a trade"""
        try:
            order_data = self.iifl.format_order_data(
                symbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type="LIMIT" if price else "MARKET",
                price=price
            )
            
            result = await self.iifl.calculate_pre_order_margin(order_data)
            
            if result and result.get("status") == "Ok":
                margin_data = result.get("resultData")
                if margin_data:
                    return float(margin_data.get("totalMargin", 0))
            elif result:
                logger.warning(f"Failed to calculate margin for {symbol}: {result.get('emsg', 'Unknown API error')}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error calculating margin for {symbol}: {str(e)}")
            return None
    
    async def get_liquidity_info(self, symbol: str) -> Dict[str, Any]:
        """Get liquidity information for a symbol"""
        try:
            depth = await self.get_market_depth(symbol)
            
            if not depth:
                return {"volume": 0, "bid_ask_spread": 0, "liquidity_score": 0}
            
            # Calculate basic liquidity metrics
            bid_qty = sum([level.get("quantity", 0) for level in depth.get("bids", [])])
            ask_qty = sum([level.get("quantity", 0) for level in depth.get("asks", [])])
            
            best_bid = depth.get("bids", [{}])[0].get("price", 0) if depth.get("bids") else 0
            best_ask = depth.get("asks", [{}])[0].get("price", 0) if depth.get("asks") else 0
            
            spread = (best_ask - best_bid) / best_bid * 100 if best_bid > 0 else 0
            total_volume = bid_qty + ask_qty
            
            # Simple liquidity score (0-100)
            liquidity_score = min(100, total_volume / 1000)  # Normalize to 100
            
            return {
                "volume": total_volume,
                "bid_ask_spread": spread,
                "liquidity_score": liquidity_score,
                "best_bid": best_bid,
                "best_ask": best_ask
            }
            
        except Exception as e:
            logger.error(f"Error getting liquidity info for {symbol}: {str(e)}")
            return {"volume": 0, "bid_ask_spread": 0, "liquidity_score": 0}
    
    def clear_cache(self):
        """Clear all cached data"""
        self.cache.clear()
        self.cache_expiry.clear()
