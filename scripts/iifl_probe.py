"""
Lightweight CLI probe for IIFL endpoints. Defaults to dry-run and prints candidate payloads.
Use --send to perform network calls (requires IIFL session token set via IIFL_SESSION env var or configured in services.iifl_api).

This script is intentionally minimal and safe: it won't modify accounts or place orders.
"""
from __future__ import annotations
import argparse
import os
import json
from typing import Any, Dict, List
import asyncio

try:
    from services.iifl_api import IIFLAPIService
except Exception:
    IIFLAPIService = None

try:
    import httpx
except Exception:  # pragma: no cover - optional runtime dependency
    httpx = None

IIFL_BASE = "https://tradeapi.iifl.in"


def build_marketquotes_variants(instrument_id: str | None = None, symbol: str | None = None) -> List[Dict[str, Any]]:
    variants: List[Dict[str, Any]] = []
    if instrument_id:
        variants.append({"exchange": "NSEEQ", "instrumentId": instrument_id})
        variants.append({"exchange": "NSEEQ", "instrumentId": str(instrument_id)})
    if symbol:
        variants.append({"exchange": "NSEEQ", "symbol": symbol})
        # old/alternate shapes
        variants.append({"exchange": "NSEEQ", "instrumentId": symbol})
    # payload documented as array-of-objects
    return variants


def _normalize_date_input(d: str | None) -> str | None:
    """Normalize various date representations to ISO YYYY-MM-DD or return None."""
    if not d:
        return None
    d = str(d).strip()
    # Already ISO
    try:
        # Accept YYYY-MM-DD
        from datetime import datetime
        datetime.strptime(d, "%Y-%m-%d")
        return d
    except Exception:
        pass
    # Try DD-MMM-YYYY (01-Jan-2025)
    try:
        from datetime import datetime
        dt = datetime.strptime(d, "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    # Try many common formats
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            from datetime import datetime
            dt = datetime.strptime(d, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    return None


def _normalize_interval(iv: str | None) -> str:
    if not iv:
        return "DAY"
    s = str(iv).strip().lower()
    mapping = {
        "1d": "DAY",
        "d": "DAY",
        "day": "DAY",
        "1m": "1 minute",
        "5m": "5 minutes",
        "15m": "15 minutes",
        "30m": "30 minutes",
        "60m": "60 minutes",
        "1h": "60 minutes",
        "1w": "WEEKLY",
        "1mo": "MONTHLY",
        "day": "DAY",
    }
    return mapping.get(s, s.upper() if len(s) > 1 else mapping.get(s, "DAY"))


def build_historical_variants(instrument_id: str | None = None, symbol: str | None = None, from_date: str | None = None, to_date: str | None = None, interval: str | None = None) -> List[Dict[str, Any]]:
    variants: List[Dict[str, Any]] = []
    # Default date range: last 30 days
    from datetime import date, timedelta
    today = date.today()
    default_to = today
    default_from = today - timedelta(days=30)
    fd = _normalize_date_input(from_date) or default_from.strftime("%Y-%m-%d")
    td = _normalize_date_input(to_date) or default_to.strftime("%Y-%m-%d")
    iv = _normalize_interval(interval)

    # Provider prefers DD-MMM-YYYY in payload; format accordingly
    try:
        from datetime import datetime
        fd_dd = datetime.strptime(fd, "%Y-%m-%d").strftime("%d-%b-%Y")
        td_dd = datetime.strptime(td, "%Y-%m-%d").strftime("%d-%b-%Y")
    except Exception:
        fd_dd = fd
        td_dd = td

    base = {"fromDate": fd_dd, "toDate": td_dd, "interval": iv}

    if instrument_id:
        v = dict(base)
        v.update({"instrumentId": str(instrument_id)})
        variants.append(v)

    if symbol:
        v = dict(base)
        v.update({"symbol": str(symbol)})
        variants.append(v)

    # Alternative documented shape (list of symbols)
    if symbol:
        variants.append({"fromDate": fd_dd, "toDate": td_dd, "interval": iv, "symbols": [str(symbol)]})

    return variants


def send_request(path: str, json_payload: Any, session_token: str | None, method: str = "POST") -> Dict[str, Any]:
    if not httpx:
        return {"error": "httpx not available in this environment"}
    url = IIFL_BASE + path
    headers = {"Content-Type": "application/json"}
    if session_token:
        headers["Authorization"] = f"Bearer {session_token}"
    with httpx.Client(timeout=30.0) as client:
        if method.upper() == "GET":
            r = client.get(url, params=json_payload, headers=headers)
        else:
            r = client.post(url, json=json_payload, headers=headers)
        out = {"status_code": r.status_code}
        try:
            out["body"] = r.json()
        except Exception:
            out["body_text_preview"] = r.text[:1000]
        return out


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="IIFL probe helper (dry-run by default).")
    p.add_argument("--instrument", "-i", help="InstrumentId to probe")
    p.add_argument("--symbol", "-s", help="Symbol to probe")
    p.add_argument("--send", action="store_true", help="Actually send requests to IIFL (requires httpx and IIFL_SESSION env var)")
    p.add_argument("--use-service", action="store_true", help="Use project's services.iifl_api.IIFLAPIService for auth/session and requests")
    p.add_argument("--show", choices=["marketquotes", "historical"], default="marketquotes")
    p.add_argument("--path", help="Custom path to send request to (overrides --show)")
    p.add_argument("--method", choices=["GET", "POST"], default="POST")
    ns = p.parse_args(argv)

    session_token = os.getenv("IIFL_SESSION")

    if ns.path:
        path = ns.path
    else:
        if ns.show == "marketquotes":
            path = "/marketdata/marketquotes"
        else:
            path = "/marketdata/historicaldata"

    if ns.show == "marketquotes":
        variants = build_marketquotes_variants(ns.instrument, ns.symbol)
    else:
        variants = build_historical_variants(ns.instrument, ns.symbol)

    print(f"Path: {path}")
    print(f"Session token present: {'yes' if session_token else 'no'}")
    print(f"Send mode: {'real' if ns.send else 'dry-run'}")
    print(f"Method: {ns.method}")
    print(f"Use project service: {'yes' if ns.use_service else 'no'}")
    print("---- Variants to try ----")
    async def _run_with_service():
        if IIFLAPIService is None:
            print("Project IIFLAPIService not importable. Ensure script is run from project root where services package is available.")
            return
        svc = IIFLAPIService()
        ok = await svc._ensure_authenticated()
        print(f"Service authenticated: {ok} (token present: {'yes' if svc.session_token else 'no'})")
        for i, v in enumerate(variants, 1):
            print(f"[{i}] payload: {json.dumps(v)}")
            if ns.show == 'marketquotes':
                # service expects list of instruments (str or dict)
                instruments = []
                if isinstance(v, dict):
                    instruments = [v]
                else:
                    instruments = [v]
                if ns.send:
                    try:
                        res = await svc.get_market_quotes(instruments)
                        print(f"    -> result: {json.dumps(res)[:200]}")
                    except Exception as e:
                        print(f"    -> error: {e}")
            else:
                # historical variant mapping
                if ns.send:
                    # Prefer instrumentId if present
                    inst = v.get('instrumentId') or (v.get('symbols') and v.get('symbols')[0])
                    sym = v.get('symbol')
                    chosen = inst or sym
                    # Convert provider's DD-MMM-YYYY back to ISO for get_historical_data
                    def _to_iso(dstr):
                        try:
                            from datetime import datetime
                            return datetime.strptime(dstr, "%d-%b-%Y").strftime("%Y-%m-%d")
                        except Exception:
                            return dstr

                    fd = _to_iso(v.get('fromDate') or v.get('from_date') or '')
                    td = _to_iso(v.get('toDate') or v.get('to_date') or '')
                    iv = v.get('interval') or 'DAY'
                    if not chosen:
                        print("    -> no instrumentId or symbol available for historical call; skipping")
                        continue
                    try:
                        res = await svc.get_historical_data(chosen, iv, fd, td)
                        print(f"    -> result: {json.dumps(res)[:200]}")
                    except Exception as e:
                        print(f"    -> error: {e}")

    for i, v in enumerate(variants, 1):
        print(f"[{i}] payload: {json.dumps(v)}")
        if ns.use_service:
            # run via project's service (async)
            if ns.send:
                asyncio.run(_run_with_service())
            else:
                # dry-run with service: show whether service would be used and token availability
                if IIFLAPIService is None:
                    print("    -> service not available for dry-run (import failed)")
                else:
                    svc = IIFLAPIService()
                    print(f"    -> would use IIFLAPIService (existing token: {'yes' if svc.session_token else 'no'})")
            # when using the service we only run once for all variants above
            break
        else:
            if ns.send:
                res = send_request(path, v, session_token, method=ns.method)
                print(f"    -> status: {res.get('status_code')}")
                if "body" in res:
                    print(f"    -> body (json): {json.dumps(res['body'])[:1000]}")
                else:
                    print(f"    -> body_preview: {res.get('body_text_preview')}")
    if not variants:
        print("No payload variants built (provide --instrument or --symbol)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
