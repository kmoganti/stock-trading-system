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
            
            # Calculate date range
            from datetime import datetime, timedelta
            to_date = datetime.now().strftime("%Y-%m-%d")
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # Fetch from IIFL API
            result = await self.iifl.get_historical_data(symbol, interval, from_date, to_date)
            
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
    

    def _process_holdings_data(self, holdings_raw: List[Dict]) -> List[Dict]:
        """Process raw IIFL holdings data into standardized format"""
        processed_holdings = []
        
        for holding in holdings_raw:
            try:
                symbol = holding.get("nseTradingSymbol", "").replace("-EQ", "")
                quantity = holding.get("totalQuantity", 0)
                avg_price = holding.get("averageTradedPrice", 0)
                ltp = holding.get("previousDayClose", 0)  # Using previous close as current price
                
                if quantity > 0 and avg_price > 0:
                    current_value = quantity * ltp
                    invested_value = quantity * avg_price
                    pnl = current_value - invested_value
                    pnl_percent = (pnl / invested_value * 100) if invested_value > 0 else 0
                    
                    processed_holdings.append({
                        "symbol": symbol,
                        "company_name": holding.get("formattedInstrumentName", ""),
                        "isin": holding.get("isin", ""),
                        "quantity": quantity,
                        "avg_price": avg_price,
                        "ltp": ltp,
                        "current_value": current_value,
                        "invested_value": invested_value,
                        "pnl": pnl,
                        "pnl_percent": pnl_percent,
                        "product": holding.get("product", "")
                    })
            except Exception as e:
                logger.error(f"Error processing holding {holding}: {str(e)}")
                continue
        
        return processed_holdings
    
    def _process_positions_data(self, positions_raw: Dict) -> List[Dict]:
        """Process raw IIFL positions data into standardized format"""
        # Handle case where positions result contains error message
        if isinstance(positions_raw, dict) and "result" in positions_raw:
            result = positions_raw["result"]
            if isinstance(result, dict) and result.get("status") == "EC920":
                # No positions found
                logger.info("No positions found for user")
                return []
            elif isinstance(result, list):
                # Process positions list
                processed_positions = []
                for position in result:
                    try:
                        symbol = position.get("symbol", "")
                        quantity = position.get("quantity", 0)
                        avg_price = position.get("avgPrice", 0)
                        ltp = position.get("ltp", 0)
                        pnl = position.get("pnl", 0)
                        
                        processed_positions.append({
                            "symbol": symbol,
                            "quantity": quantity,
                            "avg_price": avg_price,
                            "ltp": ltp,
                            "pnl": pnl,
                            "pnl_percent": (pnl / (quantity * avg_price) * 100) if quantity > 0 and avg_price > 0 else 0
                        })
                    except Exception as e:
                        logger.error(f"Error processing position {position}: {str(e)}")
                        continue
                return processed_positions
        
        return []

    async def get_portfolio_data(self) -> Dict[str, Any]:
        """Get complete portfolio data (holdings + positions)"""
        try:
            cache_key = "portfolio_data"
            
            if self._is_cache_valid(cache_key, 30):  # 30 sec cache
                return self.cache[cache_key]
            
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
                "total_invested": 0.0,
                "total_pnl": 0.0,
                "total_pnl_percent": 0.0
            }
            
            # Process holdings
            if isinstance(holdings_result, dict) and holdings_result.get("status") == "Ok":
                raw_holdings = holdings_result.get("result", [])
                processed_holdings = self._process_holdings_data(raw_holdings)
                portfolio_data["holdings"] = processed_holdings
                
                # Calculate totals from holdings
                for holding in processed_holdings:
                    portfolio_data["total_value"] += holding.get("current_value", 0)
                    portfolio_data["total_invested"] += holding.get("invested_value", 0)
                    portfolio_data["total_pnl"] += holding.get("pnl", 0)
                    
            elif isinstance(holdings_result, dict):
                error_msg = holdings_result.get("emsg", holdings_result.get("message", "Unknown error"))
                logger.warning(f"Could not fetch holdings from IIFL API: {error_msg}")
            
            # Process positions
            if isinstance(positions_result, dict) and positions_result.get("status") == "Ok":
                processed_positions = self._process_positions_data(positions_result)
                portfolio_data["positions"] = processed_positions
                
                # Add positions PnL to total
                for position in processed_positions:
                    portfolio_data["total_pnl"] += position.get("pnl", 0)
                    
            elif isinstance(positions_result, dict):
                error_msg = positions_result.get("emsg", positions_result.get("message", "Unknown error"))
                logger.info(f"Positions API response: {error_msg}")
            
            # Calculate total PnL percentage
            if portfolio_data["total_invested"] > 0:
                portfolio_data["total_pnl_percent"] = (portfolio_data["total_pnl"] / portfolio_data["total_invested"]) * 100
            
            self._set_cache(cache_key, portfolio_data, 30)
            return portfolio_data
            
        except Exception as e:
            logger.error(f"Error fetching portfolio data: {str(e)}")
            return {
                "holdings": [],
                "positions": [],
                "total_value": 0.0,
                "total_invested": 0.0,
                "total_pnl": 0.0,
                "total_pnl_percent": 0.0
            }
    

    async def get_margin_info(self) -> Optional[Dict]:
        """Get margin and limit information"""
        try:
            cache_key = "margin_info"
            
            if self._is_cache_valid(cache_key, 60):  # 1 min cache
                return self.cache[cache_key]
            
            # Derive available margin via pre-order margin endpoint with minimal dummy order
            try:
                fallback = await self.calculate_required_margin(
                    symbol="RELIANCE", quantity=1, transaction_type="BUY", price=None, product="NORMAL", exchange="NSEEQ"
                )
                if fallback:
                    # Normalize to expected keys so UI can read availableMargin/usedMargin
                    derived = {
                        "availableMargin": fallback.get("total_cash_available", 0.0),
                        "usedMargin": fallback.get("current_order_margin", 0.0),
                        "preOrderMargin": fallback.get("pre_order_margin", 0.0),
                        "postOrderMargin": fallback.get("post_order_margin", 0.0),
                        "fundShort": fallback.get("fund_short", 0.0),
                    }
                    self._set_cache(cache_key, derived, 30)
                    return derived
            except Exception as e:
                logger.warning(f"Fallback preordermargin failed: {str(e)}")
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching margin info: {str(e)}")
            return None
    
    async def calculate_required_margin(self, symbol: str, quantity: int, 
                                      transaction_type: str, price: Optional[float] = None,
                                      product: str = "NORMAL", exchange: str = "NSEEQ") -> Optional[Dict]:
        """Calculate required margin for a trade using IIFL preordermargin API"""
        try:
            order_data = self.iifl.format_order_data(
                symbol=symbol,
                transaction_type=transaction_type,
                quantity=quantity,
                order_type="LIMIT" if price else "MARKET",
                price=price,
                product=product,
                exchange=exchange
            )
            
            result = await self.iifl.calculate_pre_order_margin(order_data)
            
            if result and result.get("status") == "Ok":
                margin_data = result.get("result")
                if margin_data:
                    return {
                        "total_cash_available": float(margin_data.get("totalCashAvailable", 0)),
                        "pre_order_margin": float(margin_data.get("preOrderMargin", 0)),
                        "post_order_margin": float(margin_data.get("postOrderMargin", 0)),
                        "current_order_margin": float(margin_data.get("currentOrderMargin", 0)),
                        "rms_validation": margin_data.get("rmsValidationCheck", ""),
                        "fund_short": float(margin_data.get("fundShort", 0))
                    }
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
