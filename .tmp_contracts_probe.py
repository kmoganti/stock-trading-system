import asyncio, sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

async def main():
    svc = IIFLAPIService()
    await svc.authenticate()
    df = DataFetcher(svc)
    m = await df._get_contract_id_map()
    matches = [(k,v) for k,v in (m or {}).items() if 'ZYDUS' in str(k).upper()]
    print('matches count', len(matches))
    print(matches[:50])
    await svc.close_http_client()

if __name__ == '__main__':
    asyncio.run(main())
