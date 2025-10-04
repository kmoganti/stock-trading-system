import asyncio, json, os, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services.iifl_api import IIFLAPIService

async def probe(symbol='ZYDUSLIFE'):
    svc = IIFLAPIService()
    ok = await svc.authenticate()
    print('Auth OK', ok, 'token preview', (svc.session_token[:10] + '...') if svc.session_token else None)
    client = await svc.get_http_client()
    url = f"{svc.base_url.rstrip('/')}/marketdata/marketquotes"
    headers = {'Content-Type':'application/json', 'Authorization': svc.session_token or ''}
    payloads = [
        {'instruments':[symbol]},
        {'instrumentId': symbol},
        {'instruments':[symbol], 'exchange':'NSEEQ'},
        {'instrumentId': symbol, 'exchange':'NSEEQ'},
    ]
    for p in payloads:
        print('\n-- Trying payload:', p)
        try:
            resp = await client.post(url, headers=headers, json=p, timeout=30.0)
            print('Status:', resp.status_code)
            txt = await resp.text()
            print('Body preview:', (txt[:800] + '...') if len(txt) > 800 else txt)
        except Exception as e:
            print('Exception:', e)
    await svc.close_http_client()

if __name__ == '__main__':
    asyncio.run(probe())
