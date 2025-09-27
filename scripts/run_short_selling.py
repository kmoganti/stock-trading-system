import asyncio
import logging

from models.database import AsyncSessionLocal
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.risk import RiskService
from services.order_manager import OrderManager
from models.signals import SignalType
from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("short_selling_test")


async def main():
    settings = get_settings()
    iifl = IIFLAPIService()
    async with AsyncSessionLocal() as session:
        fetcher = DataFetcher(iifl, db_session=session)
        strategy = StrategyService(fetcher, db=session)
        risk = RiskService(fetcher, db_session=session)
        om = OrderManager(iifl, risk, fetcher, session)

        await fetcher.get_portfolio_data(force_refresh=True)
        await fetcher.get_margin_info(force_refresh=True)

        # Choose a symbol; this script attempts a SELL even without holdings (short sell)
        symbol = "RELIANCE"
        logger.info(f"Attempting short-sell test for {symbol}")

        # Use live data path to get an entry estimate if historical unavailable
        signals = await strategy.generate_signals(symbol, category="day_trading")
        entry_price = None
        if signals:
            entry_price = signals[0].entry_price
        else:
            entry_price = await fetcher.get_live_price(symbol) or 1000.0

        signal_data = {
            "symbol": symbol,
            "signal_type": SignalType.SELL,
            "reason": "short_selling_test",
            "stop_loss": (entry_price * 1.03) if entry_price else None,
            "take_profit": (entry_price * 0.97) if entry_price else None,
            "entry_price": entry_price,
        }

        db_signal = await om.create_signal(signal_data)
        if db_signal:
            await om.process_signal(db_signal)


if __name__ == "__main__":
    asyncio.run(main())

