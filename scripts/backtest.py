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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_backtest(symbol: str, start_date: str, end_date: str):
    """Runs a backtest for a given symbol and date range."""
    logger.info(f"Starting backtest for {symbol} from {start_date} to {end_date}")

    # 1. Initialize services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    strategy_service = StrategyService(data_fetcher)

    # 2. Fetch historical data
    try:
        historical_data = await data_fetcher.get_historical_data(
            symbol,
            interval="1D",
            from_date=start_date,
            to_date=end_date
        )
    except Exception as e:
        logger.error(f"Failed to fetch historical data: {e}")
        return

    if not historical_data:
        logger.warning("No historical data found for the given period.")
        return

    logger.info(f"Fetched {len(historical_data)} data points.")

    # 3. Iterate through data and generate signals
    generated_signals = []
    # We need at least 50 days of data for indicators, so we start from day 50
    for i in range(50, len(historical_data)):
        # The history is the data up to the current day
        history_for_signal = historical_data[:i]
        
        # The StrategyService expects a pandas DataFrame
        # We need to simulate the behavior of generate_signals which takes a symbol
        # and fetches data internally. We can't directly pass the historical slice.
        # So, we will mock the data fetcher to return our historical slice.
        
        # This is a simplified approach. A proper backtest would require more setup.
        # For now, we will call a modified version of the strategy logic.
        
        # The current `generate_signals` is not designed for backtesting.
        # It fetches the latest data and generates a signal for *now*.
        # A true backtest would require iterating day by day.
        
        # Let's adapt the strategy service logic for backtesting
        # This is a simplified simulation
        try:
            import pandas as pd
            df = pd.DataFrame(history_for_signal)
            df = strategy_service.calculate_indicators(df)
            if not df.empty:
                signal = strategy_service._ema_crossover_strategy(df, symbol)
                if signal:
                    # Add the date of the signal
                    signal_date = history_for_signal[-1]['date']
                    generated_signals.append((signal_date, signal))
        except Exception as e:
            logger.error(f"Error generating signal at step {i}: {e}")


    # 4. Display signals
    if generated_signals:
        logger.info(f"\n--- Generated Signals for {symbol} ---")
        for date, signal in generated_signals:
            print(f"Date: {date}, Type: {signal.signal_type.value}, Price: {signal.entry_price:.2f}, Strategy: {signal.strategy}")
        logger.info("-------------------------------------")
    else:
        logger.info("No signals were generated during this backtest period.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a backtest for a stock symbol.")
    parser.add_argument("symbol", type=str, help="The stock symbol to backtest (e.g., RELIANCE).")
    parser.add_argument("--days", type=int, default=7, help="The number of days to backtest.")

    args = parser.parse_args()

    end_date_dt = datetime.now()
    start_date_dt = end_date_dt - timedelta(days=args.days)

    start_date_str = start_date_dt.strftime("%Y-%m-%d")
    end_date_str = end_date_dt.strftime("%Y-%m-%d")

    asyncio.run(run_backtest(args.symbol, start_date_str, end_date_str))
