import asyncio
import logging
from typing import List, Set, Dict

import httpx

from .watchlist import WatchlistService
from .data_fetcher import DataFetcher
from .iifl_api import IIFLAPIService

logger = logging.getLogger(__name__)


class ScreenerService:
    """
    Service to build a dynamic intraday watchlist using external screeners.
    """

    def __init__(self, watchlist_service: WatchlistService):
        self.watchlist_service = watchlist_service

    async def _fetch_top_gainers_from_api(self) -> List[str]:
        """
        MOCK: Fetches top gainer symbols from an external API.
        Replace this with a real implementation using a data provider like Finnhub, etc.
        """
        logger.info("Fetching top gainers (mock implementation)...")
        # In a real scenario, you would make an HTTP request here.
        # Example using httpx:
        # async with httpx.AsyncClient() as client:
        #     response = await client.get("https://api.dataprovider.com/screeners/top-gainers?apiKey=...")
        #     data = response.json()
        #     return [item['symbol'] for item in data]
        await asyncio.sleep(0.1)  # Simulate network latency
        return ["ADANIENT", "BAJFINANCE", "INDUSINDBK", "TATAMOTORS", "WIPRO"]

    async def _fetch_high_volume_stocks_from_api(self) -> List[str]:
        """
        MOCK: Fetches stocks with unusual volume from an external API.
        """
        logger.info("Fetching high volume stocks (mock implementation)...")
        await asyncio.sleep(0.1)  # Simulate network latency
        return ["ITC", "SBIN", "RELIANCE", "TATAPOWER", "ZOMATO"]

    async def build_intraday_watchlist(self) -> None:
        """
        Builds and updates the 'day_trading' watchlist by combining results
        from multiple screeners.
        """
        logger.info("Starting to build dynamic intraday watchlist...")
        try:
            # Build the universe: prefer Nifty-100 if present, else fall back to mock seeds
            seed: Set[str] = set()
            # Expand with Nifty-100 CSV symbols if present for a larger universe
            try:
                from pathlib import Path
                import csv
                path = Path("data/ind_nifty100list.csv")
                if path.exists():
                    with path.open("r", encoding="utf-8-sig") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            sym = (row.get("Symbol") or row.get("symbol") or "").strip()
                            if sym:
                                seed.add(sym.upper())
            except Exception:
                pass
            # Fallback to mock lists if CSV missing or empty
            if not seed:
                gainers_task = self._fetch_top_gainers_from_api()
                volume_task = self._fetch_high_volume_stocks_from_api()
                mock_results = await asyncio.gather(gainers_task, volume_task)
                for s in mock_results:
                    seed.update(s)

            # Fetch bulk quotes to compute liquidity and volume
            iifl = IIFLAPIService()
            fetcher = DataFetcher(iifl)
            quotes: Dict[str, Dict] = await fetcher.get_bulk_quotes(list(seed))

            # Basic filters
            try:
                from config.settings import get_settings
                settings = get_settings()
                min_price = float(getattr(settings, 'min_price', 50.0))
                min_intraday_volume = int(getattr(settings, 'min_intraday_volume', 1_000_000))
            except Exception:
                min_price = 50.0
                min_intraday_volume = 1_000_000

            candidates: List[str] = []
            for sym, q in quotes.items():
                try:
                    ltp = float(q.get("ltp") or 0)
                    vol = int(q.get("tradedVolume") or 0)
                    if ltp >= min_price and vol >= min_intraday_volume:
                        candidates.append(sym)
                except Exception:
                    continue

            # Ensure minimum of 30 by relaxing volume threshold if needed
            if len(candidates) < 30:
                sorted_by_vol = sorted(quotes.items(), key=lambda kv: int(kv[1].get("tradedVolume") or 0), reverse=True)
                for sym, q in sorted_by_vol:
                    if sym in candidates:
                        continue
                    candidates.append(sym)
                    if len(candidates) >= 30:
                        break

            if not candidates:
                logger.warning("No symbols matched filters; watchlist not updated.")
                return

            await self.watchlist_service.refresh_from_list(
                symbols=candidates[:60],  # cap for practicality
                category="day_trading",
                deactivate_missing=True,
            )

        except Exception as e:
            logger.error(f"Failed to build intraday watchlist: {str(e)}", exc_info=True)