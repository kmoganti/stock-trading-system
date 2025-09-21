from __future__ import annotations
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import httpx
import json
import os
from pathlib import Path
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
    
    _instance: Optional['DataFetcher'] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Mark as uninitialized so __init__ runs on first creation
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, iifl_service: IIFLAPIService, db_session=None):
        if not getattr(self, '_initialized', False):
            self.iifl = iifl_service
            self._db = db_session
            # Short-term cache for frequently changing data like live prices
            self.cache: Dict[str, Any] = {}
            self.cache_expiry: Dict[str, datetime] = {}
            # Long-term cache for portfolio/margin, invalidated by order events
            self._portfolio_cache: Optional[Dict[str, Any]] = None
            self._margin_cache: Optional[Dict[str, Any]] = None
            self._initialized = True
    
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

    def clear_portfolio_cache(self):
        """
        Invalidates the portfolio and margin cache.
        This should be called after any order placement, modification, or cancellation.
        """
        logger.info("Clearing portfolio and margin cache due to order activity.")
        self._portfolio_cache = None
        self._margin_cache = None

    def _get_file_cache_path(self, symbol: str, interval: str) -> str:
        """Get the path for the file-based cache, ensuring the directory exists."""
        cache_dir = Path("data/hist_cache")
        cache_dir.mkdir(exist_ok=True)
        # Sanitize symbol for a safe filename
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in ('-', '_')).rstrip() or "default"
        return str(cache_dir / f"{safe_symbol}_{interval}.parquet")

    def _get_file_cache_meta_path(self, symbol: str, interval: str) -> str:
        """Get the path for the JSON sidecar cache (robust fallback without pandas)."""
        cache_dir = Path("data/hist_cache")
        cache_dir.mkdir(exist_ok=True)
        safe_symbol = "".join(c for c in symbol if c.isalnum() or c in ('-', '_')).rstrip() or "default"
        return str(cache_dir / f"{safe_symbol}_{interval}.json")

    def _read_from_file_cache(self, path: str) -> Optional[Dict[str, Any]]:
        """Read data and metadata from the file cache.

        Tries JSON sidecar first for robustness (works without pandas/pyarrow),
        falling back to parquet if available.
        """
        try:
            # Try JSON sidecar first
            json_path = os.path.splitext(path)[0] + ".json"
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        obj = json.load(f)
                        if isinstance(obj, dict) and "data" in obj and isinstance(obj.get("data"), list):
                            return {
                                "last_updated": obj.get("last_updated") or obj.get("lastUpdated") or "1970-01-01T00:00:00",
                                "data": obj.get("data")
                            }
                except Exception as e:
                    logger.warning(f"Could not read JSON cache at {json_path}: {e}")

            # Fallback to parquet if pandas is available
            if HAS_PANDAS and os.path.exists(path):
                try:
                    df = pd.read_parquet(path)
                    if df.empty or 'last_updated' not in df.attrs:
                        return None
                    df_reset = df.reset_index()
                    if pd.api.types.is_datetime64_any_dtype(df_reset['date']):
                        df_reset['date'] = df_reset['date'].dt.strftime('%Y-%m-%dT%H:%M:%S')
                    return {
                        "last_updated": df.attrs['last_updated'],
                        "data": df_reset.to_dict('records')
                    }
                except Exception as e:
                    logger.warning(f"Could not read or parse parquet cache at {path}: {e}")
        except Exception as e:
            logger.warning(f"Error accessing file cache: {e}")
        return None

    def _write_to_file_cache(self, path: str, data: List[Dict]):
        """Write data to the file cache with a timestamp.

        Always writes a JSON sidecar for robustness; writes parquet if supported.
        """
        try:
            if not data:
                return
            timestamp = datetime.now().isoformat()

            # Write JSON sidecar
            json_path = os.path.splitext(path)[0] + ".json"
            try:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({"last_updated": timestamp, "data": data}, f)
            except Exception as e:
                logger.error(f"Could not write JSON cache at {json_path}: {e}")

            # Best-effort parquet write
            if HAS_PANDAS:
                try:
                    df = pd.DataFrame(data)
                    if 'date' in df.columns:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.set_index('date')
                    df.attrs['last_updated'] = timestamp
                    df.to_parquet(path)
                except Exception as e:
                    logger.warning(f"Could not write parquet cache at {path}: {e}")
        except Exception as e:
            logger.error(f"Could not write to file cache at {path}: {e}")

    def _standardize_historical_payload(self, payload_list: List[Any]) -> List[Dict]:
        """Standardize historical data from various formats (list of dicts, list of lists)"""
        standardized_data: List[Dict] = []
        if not payload_list:
            return standardized_data

        # Handle nested structure like {"result": [{"candles": [...]}]}
        if payload_list and isinstance(payload_list[0], dict) and "candles" in payload_list[0]:
            if isinstance(payload_list[0]["candles"], list):
                payload_list = payload_list[0]["candles"]

        for item in payload_list:
            if isinstance(item, dict):
                # Existing logic for list of dicts
                item = item or {}
                standardized_item = {k.lower(): v for k, v in item.items()}
                if 'date' not in standardized_item:
                    for candidate in ['time', 'timestamp', 'datetime']:
                        if candidate in standardized_item:
                            standardized_item['date'] = standardized_item[candidate]
                            break
                standardized_data.append(standardized_item)
            elif isinstance(item, list) and len(item) >= 6:
                # Handle array format [timestamp, open, high, low, close, volume]
                try:
                    standardized_item = {
                        "date": item[0],
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": int(item[5])
                    }
                    standardized_data.append(standardized_item)
                except (ValueError, IndexError) as e:
                    logger.warning(f"Skipping malformed candle data (list format): {item} - {e}")
        return standardized_data

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
    
    async def _fetch_and_standardize(self, symbol: str, interval: str, from_date: str, to_date: str) -> Optional[List[Dict]]:
        """Internal helper to fetch data from IIFL, handle fallbacks, and standardize the output."""
        # First attempt: use symbol as provided
        result = await self.iifl.get_historical_data(symbol, interval, from_date, to_date)
        
        is_successful_response = isinstance(result, dict) and \
                                 (result.get("status", "").lower() == "ok" or result.get("stat", "").lower() == "ok")

        if is_successful_response and result:
            standardized_data = self._standardize_historical_payload(result.get("result", []))
            if standardized_data:
                return standardized_data
        
        if result:
            error_message = result.get('message') or result.get('emsg', 'Unknown API error') if isinstance(result, dict) else 'Unknown API error'
            logger.info(f"Primary fetch for {symbol} returned no data: {error_message}")

        # Fallback: resolve instrumentId via contracts and retry once
        resolved_id = await self._resolve_instrument_id(symbol)
        if resolved_id and str(resolved_id) != str(symbol):
            logger.info(f"Primary fetch failed for '{symbol}', retrying with resolved instrumentId '{resolved_id}'")
            result2 = await self.iifl.get_historical_data(str(resolved_id), interval, from_date, to_date)
            is_successful_response2 = isinstance(result2, dict) and \
                                      (result2.get("status", "").lower() == "ok" or result2.get("stat", "").lower() == "ok")

            if is_successful_response2 and result2:
                standardized_data = self._standardize_historical_payload(result2.get("result", []))
                if standardized_data:
                    return standardized_data
            elif result2:
                error_message2 = result2.get('message') or result2.get('emsg', 'Unknown API error') if isinstance(result2, dict) else 'Unknown API error'
                logger.warning(f"Fallback instrumentId fetch for {symbol} (id={resolved_id}) also failed: {error_message2}")
        
        return None

    async def get_historical_data(self, symbol: str, interval: str = "1D", 
                                days: int = 120, from_date: Optional[str] = None, 
                                to_date: Optional[str] = None) -> Optional[List[Dict]]:
        """Get historical OHLCV data"""
        try:
            if not from_date or not to_date:
                to_date = datetime.now().strftime("%Y-%m-%d")
                from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

            file_cache_path = self._get_file_cache_path(symbol, interval)
            cached_file_content = self._read_from_file_cache(file_cache_path)

            if cached_file_content:
                last_updated = datetime.fromisoformat(cached_file_content.get("last_updated", "1970-01-01T00:00:00"))
                cached_data = cached_file_content.get("data", [])

                # If cache is from today and has data, fetch only the delta
                if last_updated.date() == datetime.now().date() and cached_data:
                    last_candle_date_str = cached_data[-1].get("date", "1970-01-01")
                    last_candle_dt = datetime.fromisoformat(last_candle_date_str.split("T")[0])
                    
                    delta_from_date = (last_candle_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                    
                    if to_date > delta_from_date:
                        logger.info(f"Cache hit for {symbol}. Fetching delta from {delta_from_date} to {to_date}.")
                        delta_data = await self._fetch_and_standardize(symbol, interval, delta_from_date, to_date)
                        
                        if delta_data:
                            # Combine, update file cache, and return
                            combined_data = cached_data + delta_data
                            self._write_to_file_cache(file_cache_path, combined_data)
                            return combined_data
                    
                    # If no delta is needed, just return the cached data
                    return cached_data

            # Perform a full fetch if cache is missing, stale, or delta fetch failed
            logger.info(f"Performing full historical data fetch for {symbol} from {from_date} to {to_date}.")
            full_data = await self._fetch_and_standardize(symbol, interval, from_date, to_date)

            if full_data:
                self._write_to_file_cache(file_cache_path, full_data)
                return full_data
            
            # If fetch fails, return stale data from cache if available
            if cached_file_content and cached_file_content.get("data"):
                logger.warning(f"Full fetch failed for {symbol}, returning stale data from file cache.")
                return cached_file_content.get("data")

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
            if self._portfolio_cache is not None:
                return self._portfolio_cache

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
            
            self._portfolio_cache = portfolio_data
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
            if self._margin_cache is not None:
                return self._margin_cache

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
                    self._margin_cache = derived
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
