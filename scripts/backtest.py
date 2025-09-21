import asyncio
import argparse
from datetime import datetime, timedelta
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.backtest import BacktestService
from services.watchlist import WatchlistService
from models.database import AsyncSessionLocal, init_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def generate_signals_over_history(symbol: str, start_date: str, end_date: str, strategy_service: StrategyService, data_fetcher: DataFetcher):
    """Generate signals day-by-day for a symbol between start_date and end_date."""
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        warmup_start_dt = start_dt - timedelta(days=120)
        historical_data = await data_fetcher.get_historical_data(
            symbol,
            interval="1D",
            from_date=warmup_start_dt.strftime("%Y-%m-%d"),
            to_date=end_date,
        )
    except Exception as e:
        logger.error(f"Failed to fetch historical data for {symbol}: {e}")
        return []

    if not historical_data:
        logger.warning(f"No historical data found for {symbol}.")
        return []

    generated_signals = []
    try:
        import pandas as pd
        for i in range(50, len(historical_data)):
            history_for_signal = historical_data[:i]
            df = pd.DataFrame(history_for_signal)
            df = strategy_service.calculate_indicators(df)
            if getattr(df, "empty", True):
                continue
            signal = strategy_service._ema_crossover_strategy(df, symbol)
            if signal:
                signal_date = history_for_signal[-1]["date"]
                generated_signals.append((signal_date, signal))
    except Exception as e:
        logger.error(f"Error generating signals for {symbol}: {e}")

    # Filter to requested window only
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    except Exception:
        start_dt = None
    filtered = []
    for date, sig in generated_signals:
        try:
            date_dt = datetime.fromisoformat(str(date).split("T")[0]) if "T" in str(date) else datetime.fromisoformat(str(date))
        except Exception:
            date_dt = datetime.strptime(str(date)[:10], "%Y-%m-%d")
        if (start_dt is None) or (date_dt >= start_dt):
            filtered.append((date, sig))
    return filtered


async def get_watchlist_symbols(category: str) -> list:
    """Fetch active watchlist symbols from DB for a given category."""
    await init_db()
    async with AsyncSessionLocal() as db:
        service = WatchlistService(db)
        symbols = await service.get_watchlist(active_only=True, category=category)
        return symbols


async def main():
    parser = argparse.ArgumentParser(description="Generate signals over last N days and run backtests.")
    parser.add_argument("-s", "--symbol", type=str, help="Single stock symbol to run (e.g., RELIANCE)")
    parser.add_argument("--all-watchlist", action="store_true", help="Run for all symbols in watchlist DB")
    parser.add_argument("--category", type=str, default="short_term", help="Watchlist category to use when --all-watchlist is set")
    parser.add_argument("--strategy", type=str, default="ema_crossover", choices=["ema_crossover", "bollinger_bands", "momentum"], help="Strategy to backtest")
    parser.add_argument("--days", type=int, default=7, help="Number of days to analyze/backtest (default: 7)")
    parser.add_argument("--no-signals", action="store_true", help="Skip signal generation output")
    parser.add_argument("--no-backtest", action="store_true", help="Skip backtest run")

    args = parser.parse_args()

    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=args.days)
    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")

    # Determine symbols to run
    symbols: list[str]
    if args.all_watchlist:
        symbols = await get_watchlist_symbols(args.category)
        if not symbols:
            logger.warning("Watchlist returned no active symbols. Exiting.")
            return
    elif args.symbol:
        symbols = [args.symbol.upper()]
    else:
        parser.error("Provide --symbol or --all-watchlist")
        return

    # Initialize shared services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    strategy_service = StrategyService(data_fetcher)
    backtest_service = BacktestService(data_fetcher)

    logger.info(f"Running for {len(symbols)} symbol(s) from {start_date_str} to {end_date_str}")

    aggregate = {
        "symbols": 0,
        "signals": 0,
        "total_trades": 0,
        "avg_win_rate": 0.0,
        "avg_total_return": 0.0,
    }

    win_rates = []
    total_returns = []

    for sym in symbols:
        logger.info(f"\n=== {sym} ===")

        if not args.no_signals:
            sigs = await generate_signals_over_history(sym, start_date_str, end_date_str, strategy_service, data_fetcher)
            aggregate["signals"] += len(sigs)
            if sigs:
                logger.info(f"Generated {len(sigs)} signal(s) in window for {sym}:")
                for dt, s in sigs:
                    print(f"Date: {dt}, Type: {s.signal_type.value}, Price: {s.entry_price:.2f}, Strategy: {s.strategy}")
            else:
                logger.info("No signals in window.")

        if not args.no_backtest:
            result = await backtest_service.run_backtest(
                strategy_name=args.strategy,
                symbol=sym,
                start_date=start_date_str,
                end_date=end_date_str,
            )
            metrics = result.get("metrics", {}) if isinstance(result, dict) else {}
            total_trades = metrics.get("total_trades", 0)
            win_rate = metrics.get("win_rate", 0)
            total_return = metrics.get("total_return", 0)
            aggregate["total_trades"] += total_trades
            if isinstance(win_rate, (int, float)):
                win_rates.append(win_rate)
            if isinstance(total_return, (int, float)):
                total_returns.append(total_return)

            logger.info(
                f"Backtest: trades={total_trades}, win_rate={win_rate:.2%}, total_return={total_return:.2%}"
            )

        aggregate["symbols"] += 1

    # Aggregate summary
    if win_rates:
        aggregate["avg_win_rate"] = sum(win_rates) / len(win_rates)
    if total_returns:
        aggregate["avg_total_return"] = sum(total_returns) / len(total_returns)

    logger.info(
        f"\n=== Summary ===\nSymbols: {aggregate['symbols']}\nSignals: {aggregate['signals']}\nTotal trades: {aggregate['total_trades']}\nAvg win rate: {aggregate['avg_win_rate']:.2%}\nAvg total return: {aggregate['avg_total_return']:.2%}"
    )


if __name__ == "__main__":
    asyncio.run(main())
