import asyncio
import logging

from models.database import AsyncSessionLocal
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
from services.strategy import StrategyService
from services.risk import RiskService
from services.order_manager import OrderManager
from config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("long_term_test")


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

        symbols = ["RELIANCE", "INFY", "ICICIBANK"]
        logger.info("Generating long-term signals...")
        for sym in symbols:
            sigs = await strategy.generate_signals(sym, category="long_term")
            for s in sigs:
                signal_data = {
                    "symbol": s.symbol,
                    "signal_type": s.signal_type,
                    "reason": s.strategy,
                    "stop_loss": s.stop_loss,
                    "take_profit": s.target_price,
                    "entry_price": s.entry_price,
                }
                logger.info(f"Creating signal for {sym}: {s.signal_type.value} @ {s.entry_price}")
                db_signal = await om.create_signal(signal_data)
                if db_signal:
                    await om.process_signal(db_signal)


if __name__ == "__main__":
    asyncio.run(main())

