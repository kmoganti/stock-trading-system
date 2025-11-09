import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

from models.database import AsyncSessionLocal
from services.watchlist import WatchlistService
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.screener import ScreenerService

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
    - Has timeout protection to prevent hanging
    """
    logger.info("Starting scheduled prefetch of watchlist historical data")
    
    try:
        # Overall timeout for the entire prefetch operation (15 minutes)
        await asyncio.wait_for(
            _execute_prefetch(),
            timeout=15 * 60
        )
    except asyncio.TimeoutError:
        logger.error("⏱️ Prefetch operation exceeded 15 minute timeout")
    except Exception as e:
        logger.error(f"❌ Prefetch operation failed: {e}")

async def _execute_prefetch():
    """Internal function to execute prefetch with timeout protection"""
    async with AsyncSessionLocal() as session:
        symbols = await asyncio.wait_for(_get_active_symbols(session), timeout=10.0)
    
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
                # Timeout per symbol: 60 seconds
                await asyncio.wait_for(
                    _fetch_symbol_data(fetcher, sym),
                    timeout=60.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ Timeout prefetching {sym}")
            except Exception as e:
                logger.warning(f"Prefetch failed for {sym}: {str(e)}")
    
    await asyncio.gather(*[_prefetch_symbol(s) for s in symbols], return_exceptions=True)
    logger.info("Completed scheduled prefetch of watchlist historical data")

async def _fetch_symbol_data(fetcher: DataFetcher, sym: str):
    """Fetch data for a single symbol"""
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    data = await fetcher.get_historical_data(sym, "1D", from_date=from_date, to_date=to_date)
    logger.info(f"Prefetched {len(data) if data else 0} candles for {sym}")


async def build_daily_intraday_watchlist() -> None:
    """
    Runs the screener service to build a dynamic watchlist for intraday trading.
    This should be scheduled to run once before the market opens.
    Has timeout protection to prevent hanging (10 minute limit).
    """
    logger.info("Starting scheduled task to build intraday watchlist.")
    
    try:
        # Timeout for watchlist building: 10 minutes
        await asyncio.wait_for(
            _execute_watchlist_build(),
            timeout=10 * 60
        )
        logger.info("Completed scheduled task for intraday watchlist.")
    except asyncio.TimeoutError:
        logger.error("⏱️ Intraday watchlist building exceeded 10 minute timeout")
    except Exception as e:
        logger.error(f"❌ Intraday watchlist building failed: {e}")

async def _execute_watchlist_build():
    """Internal function to build watchlist with timeout protection"""
    async with AsyncSessionLocal() as session:
        watchlist_service = WatchlistService(session)
        screener_service = ScreenerService(watchlist_service)
        await screener_service.build_intraday_watchlist()
