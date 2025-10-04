import asyncio
import pytest

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher


class DummyResp:
    def __init__(self, status=200, text=None, json_data=None):
        self.status = status
        self._text = text
        self._json = json_data

    async def text(self):
        return self._text

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


@pytest.mark.asyncio
async def test_non_json_marketquotes_returns_none(monkeypatch):
    svc = IIFLAPIService()

    async def fake_make_request(method, endpoint, data=None):
        # Simulate a non-JSON response from marketquotes (e.g., HTML error page)
        return None

    monkeypatch.setattr(svc, "_make_api_request", fake_make_request)

    result = await svc.get_market_quotes(["7929"])
    assert result is None


@pytest.mark.asyncio
async def test_historical_symbol_fallback_to_instrument(monkeypatch):
    svc = IIFLAPIService()
    df = DataFetcher(svc)

    # First call (symbol) returns a dict with status Not ok or empty result
    async def fake_hist_symbol(method, endpoint, data=None):
        # If payload contains 'symbol' key, simulate empty Not ok
        if isinstance(data, dict) and data.get('symbol'):
            return {"status": "Not ok", "result": []}
        # If payload contains instrumentId, return an ok result with candles
        if isinstance(data, dict) and data.get('instrumentId'):
            return {"status": "Ok", "result": [{"candles": [["2025-09-29", 980, 995, 970, 990.2, 596135]]}]}
        return None

    monkeypatch.setattr(svc, "get_historical_data", lambda symbol, interval, from_date, to_date: fake_hist_symbol(None, None, {"symbol": symbol} if not str(symbol).isdigit() else {"instrumentId": symbol}))

    # Also monkeypatch contract map resolution to return a numeric id for the symbol
    async def fake_get_contract_id_map(self):
        return {"ZYDUSLIFE": "7929"}

    monkeypatch.setattr(DataFetcher, "_get_contract_id_map", fake_get_contract_id_map)

    # Call DataFetcher._fetch_and_standardize which uses svc.get_historical_data
    data = await df._fetch_and_standardize("ZYDUSLIFE", "1D", "2025-09-01", "2025-09-29")

    assert data is not None
    assert isinstance(data, list)
    # Expect at least one standardized candle
    assert len(data) >= 1
    first = data[0]
    assert 'close' in first or 'close' in first
