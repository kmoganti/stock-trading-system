from __future__ import annotations
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import httpx
from .iifl_api import IIFLAPIService
try:
    from .watchlist import WatchlistService  # type: ignore
except Exception:
    WatchlistService = None  # type: ignore

# Optional pandas import
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)

class DataFetcher:
    """Service for fetching and processing market data"""
    
    def __init__(self, iifl_service: IIFLAPIService, db_session=None):
        self.iifl = iifl_service
        self._db = db_session
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

    async def _get_contract_id_map(self) -> Dict[str, Any]:
        """Download and cache NSEEQ contract map tradingSymbol -> instrumentId.

        Cached for 12 hours to minimize network calls. Returns empty dict on failure.
        """
        cache_key = "contracts_map_nseeq"
        if self._is_cache_valid(cache_key, ttl_seconds=12 * 60 * 60):
            cached = self._get_cache(cache_key)
            if isinstance(cached, dict):
                return cached

        url = "https://api.iiflcapital.com/v1/contractfiles/NSEEQ.json"
        id_map: Dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                contracts: List[Dict[str, Any]]
                if isinstance(data, dict) and isinstance(data.get("result"), list):
                    contracts = data.get("result", [])  # type: ignore
                elif isinstance(data, list):
                    contracts = data
                else:
                    contracts = []

                for c in contracts:
                    try:
                        tsym = c.get("tradingSymbol")
                        exch = c.get("exchange")
                        inst = c.get("instrumentId")
                        if tsym and inst and (exch == "NSEEQ" or exch == "NSE"):
                            id_map[str(tsym).upper()] = str(inst)
                    except Exception:
                        continue

                if id_map:
                    self._set_cache(cache_key, id_map, ttl_seconds=12 * 60 * 60)
                return id_map
        except Exception as e:
            logger.warning(f"Failed to download NSEEQ contracts: {str(e)}")
            return {}

    async def _resolve_instrument_id(self, symbol: str) -> Optional[str]:
        """Resolve a trading symbol to an instrumentId using the contracts map.

        Returns the numeric instrumentId as a string, or None if not found.
        """
        if not symbol:
            return None
        # If already numeric, return as-is
        try:
            int(str(symbol).strip())
            return str(symbol)
        except ValueError:
            pass

        base_symbol = str(symbol).upper().strip()
        # Remove common suffixes for base lookup
        base_part = base_symbol.split("-", 1)[0] if "-" in base_symbol else base_symbol

        id_map = await self._get_contract_id_map()
        if not id_map:
            return None

        # Priority: exact base, explicit -EQ, then contains match
        for key in [base_part, f"{base_part}-EQ", base_symbol]:
            if key in id_map and id_map[key]:
                return str(id_map[key])

        # Last resort: any key containing base_part
        for k, v in id_map.items():
            try:
                if base_part in str(k).upper() and v:
                    return str(v)
            except Exception:
                continue
        return None

    async def get_historical_data_df(self, symbol: str, interval: str, from_date: str, to_date: str) -> Optional[pd.DataFrame]:
        """
        Get historical OHLCV data as a pandas DataFrame.
        This is a convenience wrapper around get_historical_data.
        """
        if not HAS_PANDAS:
            logger.error("Pandas is not installed. Cannot return a DataFrame.")
            return None

        try:
            # Pass the specific date range to the underlying fetcher
            raw_data = await self.get_historical_data(symbol, interval, from_date=from_date, to_date=to_date)

            if not raw_data:
                return pd.DataFrame()

            df = pd.DataFrame(raw_data)

            # Ensure there is a datetime column named 'date'
            if 'date' not in df.columns:
                for candidate in ['time', 'timestamp', 'datetime']:
                    if candidate in df.columns:
                        df['date'] = df[candidate]
                        break
            if 'date' not in df.columns:
                logger.error("Historical data missing 'date'/'time' field after normalization")
                return pd.DataFrame()

            # Standardize and clean the DataFrame
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df.dropna()
        except Exception as e:
            logger.error(f"Error creating DataFrame for {symbol}: {str(e)}", exc_info=True)
            return None
    
    async def get_historical_data(self, symbol: str, interval: str = "1D", 
                                days: int = 100, from_date: Optional[str] = None, 
                                to_date: Optional[str] = None) -> Optional[List[Dict]]:
        """Get historical OHLCV data"""
        try:
            # Calculate date range if not provided
            if not from_date or not to_date:
                to_date = datetime.now().strftime("%Y-%m-%d")
                from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # Use a consistent cache key based on the date range
            cache_key = f"hist_{symbol}_{interval}_{from_date}_{to_date}"
            
            # Check cache first
            cached_data = self._get_cache(cache_key)
            if cached_data is not None:
                return cached_data
            
            # First attempt: use symbol as provided (fast path, no extra network for contracts)
            result = await self.iifl.get_historical_data(symbol, interval, from_date, to_date)
            
            # Accept both 'status' and legacy 'stat' fields, but also tolerate
            # providers returning non-"Ok" even when data exists
            has_ok_flag = bool(result) and isinstance(result, dict) and (
                result.get("status") == "Ok" or result.get("stat") == "Ok"
            )
            # Data may still be present even when status is not Ok
            payload_list = []
            if isinstance(result, dict):
                # Prefer common containers in order
                for key in ["result", "data", "resultData", "candles", "history"]:
                    candidate = result.get(key)
                    if isinstance(candidate, list):
                        payload_list = candidate
                        break

            if has_ok_flag or (isinstance(payload_list, list) and len(payload_list) > 0):
                if payload_list:
                    # Standardize data format
                    standardized_data: List[Dict] = []
                    for item in payload_list:
                        item = item or {}
                        standardized_item = {k.lower(): v for k, v in item.items()}
                        # Normalize date field
                        if 'date' not in standardized_item:
                            for candidate in ['time', 'timestamp', 'datetime']:
                                if candidate in standardized_item:
                                    standardized_item['date'] = standardized_item[candidate]
                                    break
                        standardized_data.append(standardized_item)

                    # Cache for 30 minutes to limit repeated IIFL calls
                    self._set_cache(cache_key, standardized_data, 1800)
                    return standardized_data
            elif result:
                error_message = result.get('message') or result.get('emsg', 'Unknown API error') if isinstance(result, dict) else 'Unknown API error'
                logger.info(f"Primary fetch for {symbol} returned no data: {error_message}")

            # Fallback: resolve instrumentId via contracts and retry once
            try:
                resolved_id = await self._resolve_instrument_id(symbol)
            except Exception as e:
                resolved_id = None
                logger.debug(f"InstrumentId resolution skipped/failed for {symbol}: {str(e)}")

            if resolved_id and str(resolved_id) != str(symbol):
                result2 = await self.iifl.get_historical_data(str(resolved_id), interval, from_date, to_date)
                has_ok_flag2 = bool(result2) and isinstance(result2, dict) and (
                    result2.get("status") == "Ok" or result2.get("stat") == "Ok"
                )
                payload_list2 = []
                if isinstance(result2, dict):
                    for key in ["result", "data", "resultData", "candles", "history"]:
                        candidate = result2.get(key)
                        if isinstance(candidate, list):
                            payload_list2 = candidate
                            break
                if has_ok_flag2 or (isinstance(payload_list2, list) and len(payload_list2) > 0):
                    if payload_list2:
                        standardized_data: List[Dict] = []
                        for item in payload_list2:
                            item = item or {}
                            standardized_item = {k.lower(): v for k, v in item.items()}
                            if 'date' not in standardized_item:
                                for candidate in ['time', 'timestamp', 'datetime']:
                                    if candidate in standardized_item:
                                        standardized_item['date'] = standardized_item[candidate]
                                        break
                            standardized_data.append(standardized_item)
                        # Cache for 30 minutes to limit repeated IIFL calls
                        self._set_cache(cache_key, standardized_data, 1800)
                        return standardized_data
                elif result2:
                    error_message2 = result2.get('message') or result2.get('emsg', 'Unknown API error') if isinstance(result2, dict) else 'Unknown API error'
                    logger.warning(f"Fallback instrumentId fetch failed for {symbol} (id={resolved_id}): {error_message2}")
            
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
                    
                # Mark all holding symbols as 'hold' in watchlist if DB is available
                try:
                    if self._db and processed_holdings and WatchlistService is not None:
                        symbols = [h.get("symbol") for h in processed_holdings if h.get("symbol")]
                        if symbols:
                            service = WatchlistService(self._db)
                            affected = await service.mark_holdings_as_hold(symbols)
                            logger.info(f"Marked {affected} holding symbols as 'hold' in watchlist")
                except Exception as e:
                    logger.warning(f"Failed to mark holdings as 'hold' in watchlist: {str(e)}")

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
                    symbol="1594", quantity=1, transaction_type="BUY", price=None, product="NORMAL", exchange="NSEEQ"
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
