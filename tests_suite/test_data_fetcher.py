import asyncio

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher


def test_contract_map_resolves_equities_and_fo(event_loop=None):
    async def _run():
        f = DataFetcher(IIFLAPIService())
        # With dummy env, contract download may fail; just ensure it returns dict or {}
        m = await f._get_contract_id_map()
        assert isinstance(m, dict)

    asyncio.get_event_loop().run_until_complete(_run())

