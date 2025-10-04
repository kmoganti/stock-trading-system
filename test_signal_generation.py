#!/usr/bin/env python3
"""
Test signal generation for today's trading
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
import argparse
from typing import Optional, Dict
import logging

# Optional deps
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False
try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from models.database import init_db, get_db
from config import get_settings

logger = logging.getLogger(__name__)

#!/usr/bin/env python3
"""
Test signal generation for today's trading
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta
import argparse
from typing import Optional, Dict
import logging

# Optional deps
try:
    import pandas as pd  # type: ignore
    HAS_PANDAS = True
except Exception:
    HAS_PANDAS = False
try:
    import requests  # type: ignore
    HAS_REQUESTS = True
except Exception:
    HAS_REQUESTS = False

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from models.database import init_db, get_db
from config import get_settings

logger = logging.getLogger(__name__)

def _read_auth_token(auth_token_path: str) -> Optional[str]:
    try:
        with open(auth_token_path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            return raw if raw.lower().startswith("bearer ") else f"Bearer {raw}"
    except Exception:
        return None

def _load_holdings_symbol_to_instrument(files_dir: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    try:
        holding_path = os.path.join(files_dir, "holding.json")
        if not os.path.exists(holding_path):
            return mapping
        with open(holding_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        holdings = obj.get("result") if isinstance(obj, dict) else obj
        if isinstance(holdings, list):
            for h in holdings:
                try:
                    symbol = (h.get("nseTradingSymbol") or "").upper()
                    instrument_id = h.get("nseInstrumentId")
                    if symbol and instrument_id:
                        mapping[symbol] = str(instrument_id)
                except Exception:
                    continue
    except Exception:
        pass
    return mapping

def _normalize_hist_to_df(hist_list) -> Optional["pd.DataFrame"]:
    if not HAS_PANDAS:
        return None
    try:
        if not hist_list:
            return pd.DataFrame()
        df = pd.DataFrame(hist_list)
        # Standardize keys
        df.columns = [str(c).lower() for c in df.columns]
        if "date" not in df.columns:
            for c in ["time", "timestamp", "datetime"]:
                if c in df.columns:
                    df["date"] = df[c]
                    break
        if "date" not in df.columns:
            return pd.DataFrame()
        df["date"] = pd.to_datetime(df["date"])  # type: ignore
        df.set_index("date", inplace=True)
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df.dropna()
    except Exception:
        return None

def _direct_fetch_to_df(auth_token: str, instrument_id: str, from_dt: datetime, to_dt: datetime) -> Optional["pd.DataFrame"]:
    if not (HAS_PANDAS and HAS_REQUESTS):
        return None
    try:
        # Match scripts/fetch_holdings_candles.py direct payload format
        url = "https://api.iiflcapital.com/v1/marketdata/historicaldata"
        headers = {"Content-Type": "application/json", "Authorization": auth_token}
        payload = {
            "exchange": "NSEEQ",
            "instrumentId": str(instrument_id),
            "interval": "1 day",
            # dd-Mon-YYYY lower per the script
            "fromDate": from_dt.strftime("%d-%b-%Y"),
            "toDate": to_dt.strftime("%d-%b-%Y"),
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=60)  # type: ignore
        resp.raise_for_status()
        data = resp.json()
        # Accept both {status/result} and raw lists
        if isinstance(data, dict):
            hist = data.get("result") or data.get("data") or []
        else:
            hist = data
        # Standardize list of dicts to lower keys
        normalized = []
        for item in hist or []:
            item = item or {}
            normalized.append({str(k).lower(): v for k, v in item.items()})
        return _normalize_hist_to_df(normalized)
    except Exception as e:
        logger.warning(f"Direct historical fetch failed for instrumentId={instrument_id}: {e}")
        return None

async def _resilient_fetch_hist_df(data_fetcher: DataFetcher, symbol: str, from_dt: datetime, to_dt: datetime,
                                   holdings_map: Optional[Dict[str, str]], auth_token: Optional[str]) -> Optional["pd.DataFrame"]:
    # 1) Primary: DataFetcher by symbol (IIFL service already tries symbol variants and date key variants)
    df = await data_fetcher.get_historical_data_df(
        symbol, "1D", from_dt.strftime("%Y-%m-%d"), to_dt.strftime("%Y-%m-%d")
    )
    if df is not None and not df.empty:
        return df

    # 2) If we have instrumentId from holdings, try via DataFetcher using numeric id
    instrument_id = None
    if holdings_map:
        instrument_id = holdings_map.get(symbol.upper())
        # Also try a suffix-free lookup (e.g., RELIANCE-EQ -> RELIANCE)
        if not instrument_id and "-" in symbol:
            base = symbol.split("-", 1)[0]
            instrument_id = holdings_map.get(base.upper())

    if instrument_id:
        df_id = await data_fetcher.get_historical_data_df(
            str(instrument_id), "1D", from_dt.strftime("%Y-%m-%d"), to_dt.strftime("%Y-%m-%d")
        )
        if df_id is not None and not df_id.empty:
            return df_id

        # 3) Fallback to direct REST call if token available
        if auth_token:
            direct_df = _direct_fetch_to_df(auth_token, str(instrument_id), from_dt, to_dt)
            if direct_df is not None and not direct_df.empty:
                return direct_df

    # 2b) If we didn't have holdings_map or instrument id from it, try resolving via DataFetcher contract map
    try:
        if not instrument_id:
            resolved = await data_fetcher._resolve_instrument_id(symbol)
            if resolved:
                df_resolved = await data_fetcher.get_historical_data_df(
                    str(resolved), "1D", from_dt.strftime("%Y-%m-%d"), to_date.strftime("%Y-%m-%d")
                )
                if df_resolved is not None and not df_resolved.empty:
                    return df_resolved
                if auth_token:
                    direct_df = _direct_fetch_to_df(auth_token, str(resolved), from_dt, to_dt)
                    if direct_df is not None and not direct_df.empty:
                        return direct_df
    except Exception:
        pass

    # 4) As a last fallback, try low-level list and convert if pandas exists
    try:
        raw = await data_fetcher.get_historical_data(
            symbol, "1D", from_date=from_dt.strftime("%Y-%m-%d"), to_date=to_dt.strftime("%Y-%m-%d")
        )
        if raw:
            return _normalize_hist_to_df(raw)
    except Exception:
        pass
    return None

async def test_signal_generation(symbols_to_test: list = None):
    """
    Backtest and debug signal generation logic for today's trading.
    This script fetches the latest market data, displays it, and then runs the
    signal generation logic to help diagnose why signals may not be generating.
    """
    print("=== Signal Generation Diagnostic Test ===")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize database
    await init_db()
    
    # Load settings to check filters
    settings = get_settings()
    print("--- System Settings ---")
    print(f"Min Price Filter: {settings.min_price}")
    print(f"Min Liquidity Filter: {settings.min_liquidity}")
    print("-" * 23)

    # Get DB session and run tests
    async for db in get_db():
        # Initialize services
        iifl_service = IIFLAPIService()
        data_fetcher = DataFetcher(iifl_service, db_session=db)
        strategy_service = StrategyService(data_fetcher, db)
        
        # Test authentication
        auth_result = await iifl_service.authenticate()
        print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
        
        if not iifl_service.session_token.startswith('mock_'):
            print("Using real IIFL data\n")

            if symbols_to_test:
                watchlist = [s.upper() for s in symbols_to_test]
                print(f"Testing specified symbols: {', '.join(watchlist)}")
            else:
                # Test signal generation for watchlist stocks
                watchlist = await strategy_service.get_watchlist(category="day_trading")
                if not watchlist:
                    watchlist = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"] # Fallback
                print(f"Testing {len(watchlist)} stocks from 'day_trading' watchlist...")

            print("=" * 50)
            
            total_signals = 0

            # Prepare optional fallbacks (holdings map and auth token)
            files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "files")
            holdings_map = _load_holdings_symbol_to_instrument(files_dir)
            auth_token = _read_auth_token(os.path.join(files_dir, "auth_token.txt")) if holdings_map else None
            
            for symbol in watchlist:
                print(f"\nAnalyzing {symbol}:")
                try:
                    # 1. Fetch recent data to show what the strategy service will be using
                    print("  Fetching latest data for analysis...")
                    to_date = datetime.now()
                    from_date = to_date - timedelta(days=90) # Fetch 90 days for indicator calculation
                    
                    # Resilient fetch mirroring scripts/fetch_holdings_candles.py fallbacks
                    hist_data_df = await _resilient_fetch_hist_df(
                        data_fetcher,
                        symbol,
                        from_date,
                        to_date,
                        holdings_map,
                        auth_token,
                    )

                    if hist_data_df is None or hist_data_df.empty:
                        print(f"  [FAIL] Could not fetch historical data for {symbol}. Skipping.")
                        continue
                    
                    last_record = hist_data_df.iloc[-1]
                    print(f"  - Latest Close: {last_record['close']:.2f} on {last_record.name.strftime('%Y-%m-%d')}")

                    print(f"  - Latest Volume: {last_record['volume']:,.0f}")

                    # Check against system filters
                    if last_record['close'] < settings.min_price:
                        print(f"  - [FILTERED] Price {last_record['close']:.2f} is below min_price of {settings.min_price}")
                    
                    # 2. Generate signals for this symbol
                    print("  Running signal generation logic...")

                    signals = await strategy_service.generate_signals(symbol)



                    if signals:
                        total_signals += len(signals)
                        print(f"  [SUCCESS] Found {len(signals)} signal(s) for {symbol}!")
                        
                        for i, signal in enumerate(signals, 1):
                            signal_type = signal.signal_type.value if hasattr(signal.signal_type, 'value') else signal.signal_type
                            print(f"    -> Signal {i}: {signal_type.upper()}")
                            print(f"       Strategy: {signal.strategy}")
                            print(f"       Entry: Rs.{signal.entry_price:.2f}, SL: Rs.{signal.stop_loss:.2f}, TGT: Rs.{signal.target_price:.2f}")
                            print(f"       Confidence: {signal.confidence:.1%}")
                            

                    else:
                        print(f"  [INFO] No signals generated for {symbol}. Conditions not met.")
                        
                except Exception as e:

                    print(f"  [ERROR] An exception occurred while analyzing {symbol}: {str(e)}")
            
            print("\n" + "=" * 50)
            print(f"SUMMARY: Generated {total_signals} total signals across {len(watchlist)} stocks")
            if total_signals == 0:
                print("If no signals are generated, check strategy logic in 'services/strategy.py' against the data shown above.")
            
        else:
            print("Using mock data - update auth code in .env for live testing")
        break # Exit after one loop with the db session

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest and debug signal generation.")
    parser.add_argument(
        '--symbols', 
        nargs='+', 
        help='A list of specific stock symbols to test (e.g., RELIANCE TCS INFY). Overrides watchlist.'
    )
    args = parser.parse_args()
    try:
        asyncio.run(test_signal_generation(symbols_to_test=args.symbols))
    except KeyboardInterrupt:
        print("\n[INFO] Script interrupted by user. Exiting.")
        sys.exit(0)
