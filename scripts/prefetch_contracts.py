"""CLI: Prefetch and persist the NSEEQ contract map to data/contracts_nseeq.json

Usage: python -m scripts.prefetch_contracts
"""
import asyncio
import logging
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

async def main():
    iifl = IIFLAPIService()
    logger.info("Authenticating with IIFL (if needed)")
    auth_res = await iifl.authenticate()
    logger.info(f"Authenticate result: {auth_res}")
    df = DataFetcher(iifl)
    logger.info("Fetching NSEEQ contract map (will persist to data/contracts_nseeq.json)")
    mapping = await df._get_contract_id_map()
    if mapping:
        logger.info(f"Fetched contract map with {len(mapping)} entries")
        # print small sample
        sample_keys = list(mapping.keys())[:10]
        logger.info(f"Sample symbols: {sample_keys}")
    else:
        logger.error("Failed to fetch contract map or map empty")

if __name__ == '__main__':
    asyncio.run(main())
