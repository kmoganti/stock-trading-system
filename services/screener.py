import asyncio
import logging
from typing import List, Set

import httpx

from .watchlist import WatchlistService
from config.settings import get_settings
from services.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ScreenerService:
    """
    Service to build a dynamic intraday watchlist using external screeners.
    """

    def __init__(self, watchlist_service: WatchlistService):
        self.watchlist_service = watchlist_service
        self._settings = get_settings()
        self._notifier = TelegramNotifier()

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
        await self._notifier.send("▶️ Starting day trading screening...")
        try:
            # Fetch symbols from different screeners concurrently
            gainers_task = self._fetch_top_gainers_from_api()
            volume_task = self._fetch_high_volume_stocks_from_api()

            results = await asyncio.gather(gainers_task, volume_task)

            # Combine and deduplicate symbols
            final_symbols: Set[str] = set()
            for symbol_list in results:
                final_symbols.update(symbol_list)

            if not final_symbols:
                logger.warning("No symbols found from screeners. Watchlist not updated.")
                return

            # Use the watchlist service to refresh the 'day_trading' category
            await self.watchlist_service.refresh_from_list(
                symbols=list(final_symbols),
                category="day_trading",
                deactivate_missing=True,
            )

        except Exception as e:
            logger.error(f"Failed to build intraday watchlist: {str(e)}", exc_info=True)