#!/usr/bin/env python3
"""
Prefetch historical OHLCV caches for watchlist symbols with delta-only updates.

- Uses DataFetcher file cache (JSON sidecar) per symbol/interval
- If a cache exists from today, fetches only the missing delta range
- Otherwise performs a full fetch and persists to cache

Usage examples:
  python -m scripts.prefetch_historical_cache --category day_trading --interval 5m --days 2 --max-concurrency 6 --limit 20
  python -m scripts.prefetch_historical_cache --category short_term --interval 1D --days 120 --max-concurrency 6
  python -m scripts.prefetch_historical_cache --symbols RELIANCE,INFY,TCS --interval 1D --days 250

Notes:
- Requires valid IIFL authentication (same as server). Ensure the server has refreshed token or env creds are set.
- Watchlist is used when --symbols not provided.
"""
import asyncio
import argparse
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from models.database import init_db, AsyncSessionLocal
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.watchlist import WatchlistService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("prefetch_cache")


async def _get_symbols(category: Optional[str], explicit_symbols: Optional[List[str]]) -> List[str]:
    if explicit_symbols:
        return [s.strip().upper() for s in explicit_symbols if s and s.strip()]
    async with AsyncSessionLocal() as session:
        wl = WatchlistService(session)
        return await wl.get_watchlist(active_only=True, category=category)


async def prefetch(
    symbols: List[str],
    interval: str,
    days: int,
    max_concurrency: int = 6,
) -> Dict[str, int]:
    iifl = IIFLAPIService()
    fetcher = DataFetcher(iifl)

    # Batch fetch with delta logic built-in
    start = datetime.now()
    hist_map = await fetcher.get_historical_data_many(
        symbols,
        interval=interval,
        days=days,
        max_concurrency=max_concurrency,
    )

    fetched = 0
    empty = 0
    for s, data in hist_map.items():
        if data:
            fetched += 1
        else:
            empty += 1
    dur = (datetime.now() - start).total_seconds()
    logger.info("Prefetch completed in %.2fs (interval=%s, days=%d) -> total=%d, ok=%d, empty=%d",
                dur, interval, days, len(symbols), fetched, empty)
    return {"total": len(symbols), "ok": fetched, "empty": empty}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="short_term", choices=["day_trading", "short_term", "long_term"])
    parser.add_argument("--symbols", default=None, help="Comma-separated symbols to prefetch; overrides --category")
    parser.add_argument("--interval", default=None, help="5m for intraday; 1D for EOD")
    parser.add_argument("--days", type=int, default=None, help="Days window to fetch; defaults based on category")
    parser.add_argument("--max-concurrency", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None, help="Limit number of symbols for quick warm-up")
    args = parser.parse_args()

    await init_db()

    category = args.category
    interval = args.interval or ("5m" if category == "day_trading" else "1D")
    days = (
        args.days if args.days is not None else (2 if category == "day_trading" else (250 if category == "long_term" else 120))
    )

    symbols = await _get_symbols(category, args.symbols.split(",") if args.symbols else None)
    if args.limit:
        symbols = symbols[: args.limit]

    if not symbols:
        logger.warning("No symbols to prefetch (category=%s)", category)
        print({"total": 0, "ok": 0, "empty": 0})
        return

    stats = await prefetch(symbols, interval, days, max_concurrency=args.max_concurrency)
    print(stats)


if __name__ == "__main__":
    asyncio.run(main())
