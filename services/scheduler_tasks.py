import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from models.database import AsyncSessionLocal
from services.watchlist import WatchlistService
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


async def _get_active_symbols(session) -> List[str]:
    try:
        service = WatchlistService(session)
        return await service.get_watchlist(active_only=True)
    except Exception as e:
        logger.warning(f"Failed to load watchlist for prefetch: {str(e)}")
        return []


async def prefetch_watchlist_historical_data() -> None:
    """Prefetch historical data for active watchlist symbols.

    - Runs every 30 minutes (scheduled in main.py)
    - Limits concurrency to avoid overwhelming IIFL
    - Fetches last ~120 days of daily candles for each symbol
    """
    logger.info("Starting scheduled prefetch of watchlist historical data")
    async with AsyncSessionLocal() as session:
        symbols = await _get_active_symbols(session)
    if not symbols:
        logger.info("No active watchlist symbols to prefetch")
        return

    iifl = IIFLAPIService()
    fetcher = DataFetcher(iifl)

    # Limit concurrent fetches
    semaphore = asyncio.Semaphore(3)

    async def _prefetch_symbol(sym: str):
        async with semaphore:
            try:
                to_date = datetime.now().strftime("%Y-%m-%d")
                from_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
                data = await fetcher.get_historical_data(sym, "1D", from_date=from_date, to_date=to_date)
                logger.info(f"Prefetched {len(data) if data else 0} candles for {sym}")
            except Exception as e:
                logger.warning(f"Prefetch failed for {sym}: {str(e)}")

    await asyncio.gather(*[_prefetch_symbol(s) for s in symbols])
    logger.info("Completed scheduled prefetch of watchlist historical data")

