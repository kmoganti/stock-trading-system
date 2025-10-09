import asyncio
import logging

from services.scheduler_tasks import build_daily_intraday_watchlist

logger = logging.getLogger("smoke_scheduler")

async def main():
    logger.info("Starting scheduler smoke test: build_daily_intraday_watchlist()")
    try:
        await build_daily_intraday_watchlist()
        logger.info("Scheduler smoke test completed successfully")
    except Exception as e:
        logger.exception(f"Scheduler smoke test failed: {e}")

if __name__ == '__main__':
    asyncio.run(main())
