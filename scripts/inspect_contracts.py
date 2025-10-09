import asyncio
from services.data_fetcher import DataFetcher
from services.iifl_api import IIFLAPIService

async def main():
    svc = IIFLAPIService()
    df = DataFetcher(svc)
    id_map = await df._get_contract_id_map()
    print('Total contracts in map:', len(id_map))
    sample = list(id_map.items())[:20]
    for k,v in sample:
        print(k, '->', v)

if __name__ == '__main__':
    asyncio.run(main())
