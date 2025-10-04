import asyncio
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

async def main():
    svc = IIFLAPIService()
    ok = await svc.authenticate()
    print('Auth OK', ok)
    df = DataFetcher(svc)
    price = await df.get_live_price('ZYDUSLIFE')
    print('Live price:', price)
    await svc.close_http_client()

if __name__ == '__main__':
    asyncio.run(main())
