import httpx
import json

url = 'https://api.iiflcapital.com/v1/contractfiles/NSEEQ.json'
resp = httpx.get(url, timeout=10.0)
resp.raise_for_status()
data = resp.json()
# data may be dict with result list or list
contracts = data.get('result') if isinstance(data, dict) and isinstance(data.get('result'), list) else (data if isinstance(data, list) else [])
for c in contracts:
    ts = c.get('tradingSymbol') or c.get('nseTradingSymbol') or c.get('symbol')
    if ts and 'RELIANCE' in ts:
        print(json.dumps(c, indent=2))
        break
print('done')
