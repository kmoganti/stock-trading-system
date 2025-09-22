from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher
import asyncio


def test_format_order_data_fields():
    svc = IIFLAPIService()
    d = svc.format_order_data(symbol="1594", transaction_type="BUY", quantity=1, order_type="MARKET")
    assert d["instrumentId"] == "1594"
    assert d["exchange"] == "NSEEQ"
    assert d["orderType"] == "MARKET"


def test_calculate_required_margin_mocked():
    # With dummy env and no live API, ensure function handles None without crashing
    async def _run():
        f = DataFetcher(IIFLAPIService())
        resp = await f.calculate_required_margin("1594", 1, "BUY")
        assert resp is None or isinstance(resp, dict)

    asyncio.get_event_loop().run_until_complete(_run())

