import asyncio
import json
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

async def main():
    svc = IIFLAPIService()
    await svc._ensure_authenticated()
    df = DataFetcher(svc)
    symbol = 'RELIANCE'
    resolved = await df._resolve_instrument_id(symbol)
    print('resolved ->', resolved)
    instr = resolved if resolved else symbol
    resp = await svc.get_market_quotes([instr])
    print('response type:', type(resp))
    try:
        print('response keys:', list(resp.keys()) if isinstance(resp, dict) else resp)
        print('response preview:', json.dumps(resp, indent=2) if isinstance(resp, dict) else resp)
    except Exception as e:
        print('could not pretty-print response:', e)
    print('\nNow fetching historical data (10 days)...')
    hist = await df.get_historical_data(symbol, interval='1D', days=10)
    print('historical result length:', len(hist) if hist is not None else None)

if __name__ == '__main__':
    asyncio.run(main())
