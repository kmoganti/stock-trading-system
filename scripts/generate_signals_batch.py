#!/usr/bin/env python3
"""
Batch generate trading signals from DB watchlist categories with optimized data fetching.

- Fetches watchlist symbols by category (day_trading, short_term, long_term)
- Downloads only delta historical data using file cache (strict single-call per symbol)
- Generates signals from pre-fetched data and optionally persists them
  as pending in DB (no auto execution unless system config enables it)

Usage:
  python scripts/generate_signals_batch.py --category day_trading --persist true --validate false --interval 5m

Environment:
  DATABASE_URL must be set appropriately if not using default sqlite path.
"""

import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from models.database import AsyncSessionLocal, init_db
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.watchlist import WatchlistService
from services.order_manager import OrderManager
from services.risk import RiskService


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("signals_batch")


async def _load_symbols(category: str) -> List[str]:
    async with AsyncSessionLocal() as session:
        wl = WatchlistService(session)
        return await wl.get_watchlist(active_only=True, category=category)


async def _persist_signals(
    session,
    signals: List[Dict],
) -> List[int]:
    iifl = IIFLAPIService()
    fetcher = DataFetcher(iifl, db_session=session)
    risk_service = RiskService(fetcher, session)
    om = OrderManager(iifl, risk_service, fetcher, session)
    ids: List[int] = []
    for s in signals:
        created = await om.create_signal({
            "symbol": s["symbol"],
            "signal_type": s["signal_type"],
            "entry_price": s["entry_price"],
            "stop_loss": s.get("stop_loss"),
            "take_profit": s.get("target_price"),
            "reason": f"{s.get('strategy','strategy')} generated",
            "strategy": s.get("strategy", ""),
            "confidence": s.get("confidence", 0.7),
        })
        if created:
            ids.append(created.id)
    return ids


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", default="short_term", choices=["day_trading", "short_term", "long_term"]) 
    parser.add_argument("--persist", default="false")
    parser.add_argument("--validate", default="true")
    parser.add_argument("--interval", default=None, help="Override interval for fetching; defaults based on category")
    parser.add_argument("--days", type=int, default=None, help="Override days window; defaults based on category")
    parser.add_argument("--max-concurrency", type=int, default=4)
    args = parser.parse_args()

    persist = str(args.persist).lower() in {"1", "true", "yes", "y"}
    validate = str(args.validate).lower() in {"1", "true", "yes", "y"}

    await init_db()

    category = args.category
    # Set default interval/days per category
    interval = args.interval or ("5m" if category == "day_trading" else "1D")
    days = (
        args.days if args.days is not None else (2 if category == "day_trading" else (250 if category == "long_term" else 100))
    )

    symbols = await _load_symbols(category)
    if not symbols:
        logger.info("No symbols found for category %s", category)
        return

    iifl = IIFLAPIService()
    fetcher = DataFetcher(iifl)
    strategy = StrategyService(fetcher)

    logger.info("Fetching historical data for %d symbols (interval=%s, days=%d)", len(symbols), interval, days)
    hist_map = await fetcher.get_historical_data_many(
        symbols,
        interval=interval,
        days=days,
        max_concurrency=args.max_concurrency,
    )

    generated: List[Dict] = []
    for sym, data in hist_map.items():
        sigs = await strategy.generate_signals_from_data(sym, data, strategy_name=None, validate=validate)
        for ts in sigs:
            generated.append({
                "symbol": ts.symbol,
                "signal_type": ts.signal_type,
                "entry_price": ts.entry_price,
                "stop_loss": ts.stop_loss,
                "target_price": ts.target_price,
                "confidence": ts.confidence,
                "strategy": ts.strategy,
                "metadata": ts.metadata or {},
            })

    logger.info("Generated %d signals", len(generated))
    if persist and generated:
        async with AsyncSessionLocal() as session:
            ids = await _persist_signals(session, generated)
        logger.info("Persisted %d signals", len(ids))

    # Print a concise summary to stdout for scripting
    print({"count": len(generated)})


if __name__ == "__main__":
    asyncio.run(main())

