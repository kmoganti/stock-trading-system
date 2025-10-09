import asyncio
import json
import time
from services.iifl_api import IIFLAPIService

REPORT_PATH = 'reports/marketquotes_jiofin_debug.json'

PAYLOAD_VARIANTS = []

# Base symbol(s)
SYMBOL = 'JIOFIN'
SYMBOL_EQ = SYMBOL + '-EQ'

# Variant helpers
PAYLOAD_VARIANTS.append({'desc': 'instruments_array_symbols', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': [SYMBOL]}})
PAYLOAD_VARIANTS.append({'desc': 'instruments_array_symbols_eq', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': [SYMBOL_EQ]}})
PAYLOAD_VARIANTS.append({'desc': 'instruments_comma_separated', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': ','.join([SYMBOL])}})
PAYLOAD_VARIANTS.append({'desc': 'symbols_array', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'symbols': [SYMBOL]}})
PAYLOAD_VARIANTS.append({'desc': 'symbol_single', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'symbol': SYMBOL}})
PAYLOAD_VARIANTS.append({'desc': 'instrumentIds_array_numeric', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instrumentIds': ['2885']}})
PAYLOAD_VARIANTS.append({'desc': 'instrumentId_single_numeric', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instrumentId': '2885'}})
PAYLOAD_VARIANTS.append({'desc': 'instruments_array_numeric', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': ['2885']}})
PAYLOAD_VARIANTS.append({'desc': 'instruments_obj_list_symbol', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': [{'symbol': SYMBOL, 'exchange': 'NSEEQ'}]}})
PAYLOAD_VARIANTS.append({'desc': 'instruments_obj_list_tradingSymbol', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': {'instruments': [{'tradingSymbol': SYMBOL, 'exchange': 'NSEEQ'}]}})

# Add exact curl-shaped payload (raw JSON array) observed from user
PAYLOAD_VARIANTS.append({'desc': 'curl_raw_array_instrumentId_14366', 'method': 'POST', 'headers': {'Content-Type': 'application/json'}, 'body': [{"exchange": "NSEEQ", "instrumentId": "14366"}]})

# form-encoded variants
FORM_VARIANTS = [
    ('instruments', SYMBOL),
    ('instruments', SYMBOL_EQ),
    ('instrumentIds', '2885'),
    ('instrumentId', '2885'),
]

async def run_variant(svc: IIFLAPIService, variant: dict, client_only=False):
    """Run one JSON payload variant through svc._make_api_request by calling get_market_quotes (which tries variants internally) or directly via client.post for form variants.
    We call svc._make_api_request directly for JSON variants to capture headers & body.
    """
    out = {'desc': variant.get('desc'), 'method': variant.get('method'), 'body': variant.get('body'), 'timestamp': time.time()}
    try:
        # Use private call to build the request through existing helper to keep auth handling consistent
        resp = await svc._make_api_request(variant.get('method', 'POST'), '/marketdata/marketquotes', variant.get('body'))
        out['response'] = resp
        out['status'] = 'ok' if resp is not None else 'none'
    except Exception as e:
        out['error'] = str(e)
    return out

async def run_form_variant(svc: IIFLAPIService, k, v):
    out = {'desc': f'form_{k}', 'form_key': k, 'form_value': v, 'timestamp': time.time()}
    try:
        client = await svc.get_http_client()
        headers = {'User-Agent': 'IIFL-Trading-System/1.0'}
        if svc.session_token:
            token = svc.session_token if str(svc.session_token).lower().startswith('bearer ') else f'Bearer {svc.session_token}'
            headers['Authorization'] = token
        # form post
        resp = await client.post(f"{svc.base_url.rstrip('/')}/marketdata/marketquotes", headers=headers, data={k: v})
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        out['http_status'] = resp.status_code
        out['response_headers'] = dict(resp.headers)
        out['response_body'] = body
    except Exception as e:
        out['error'] = str(e)
    return out

async def main():
    svc = IIFLAPIService()
    await svc._ensure_authenticated()

    results = []

    # run JSON-like variants using the service helper
    for v in PAYLOAD_VARIANTS:
        r = await run_variant(svc, v)
        results.append(r)

    # run form-encoded variants
    for k, val in FORM_VARIANTS:
        r = await run_form_variant(svc, k, val)
        results.append(r)

    # Also try GET fallback
    try:
        rget = await svc._make_api_request('GET', '/marketdata/marketquotes', {'instruments': SYMBOL})
        results.append({'desc': 'get_instruments', 'method': 'GET', 'body': {'instruments': SYMBOL}, 'response': rget})
    except Exception as e:
        results.append({'desc': 'get_instruments', 'error': str(e)})

    # save to reports
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump({'symbol': SYMBOL, 'timestamp': time.time(), 'variants': results}, f, indent=2)

    print(f"Wrote report to {REPORT_PATH}")

if __name__ == '__main__':
    asyncio.run(main())
