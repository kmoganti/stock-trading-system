import asyncio
import logging

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_market_calls")


async def main():
    iifl = IIFLAPIService()
    fetcher = DataFetcher(iifl)

    symbols = ["RELIANCE", "TCS", "14366"]

    for sym in symbols:
        try:
            resolved_id = await fetcher._resolve_instrument_id(sym)
            trading_sym = await fetcher._resolve_trading_symbol(sym)
            logger.info(f"Symbol={sym} resolved_id={resolved_id} trading_sym={trading_sym}")

            # Test market quotes
            call_arg = resolved_id if resolved_id else (trading_sym if trading_sym else sym)
            logger.info(f"Calling get_market_quotes with: {call_arg}")
            # get_market_quotes expects a list
            mq = await iifl.get_market_quotes([call_arg])
            logger.info(f"marketquotes response keys: {list(mq.keys()) if mq else mq}")

            # Test market depth
            logger.info(f"Calling get_market_depth with: {call_arg}")
            depth = await iifl.get_market_depth(call_arg)
            logger.info(f"marketdepth response keys: {list(depth.keys()) if depth else depth}")

        except Exception as e:
            logger.exception(f"Error testing symbol {sym}: {e}")

    # Test margin info via DataFetcher
    try:
        margin = await fetcher.get_margin_info(force_refresh=True)
        logger.info(f"Margin info: {margin}")
    except Exception as e:
        logger.exception(f"Error fetching margin info: {e}")


if __name__ == "__main__":
    asyncio.run(main())
