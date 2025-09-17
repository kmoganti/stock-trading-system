#!/usr/bin/env python3
import os
import json
import logging
from datetime import datetime, timedelta
import asyncio

import requests

# Reuse project services when available
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from services.iifl_api import IIFLAPIService  # type: ignore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def read_auth_token(auth_token_path: str) -> str:
    with open(auth_token_path, "r", encoding="utf-8") as f:
        raw_token = f.read().strip()
        return raw_token if raw_token.lower().startswith("bearer ") else f"Bearer {raw_token}"


def load_holdings(holding_path: str):
    with open(holding_path, 'r', encoding='utf-8') as f:
        obj = json.load(f)
        return obj.get('result') or obj


def ensure_dirs(path: str):
    os.makedirs(path, exist_ok=True)


async def fetch_with_internal_service(symbol: str, instrument_id: str | int, from_date_str: str, to_date_str: str, out_path: str) -> bool:
    """Try using internal IIFLAPIService first to leverage auth and normalization."""
    try:
        svc = IIFLAPIService()
        ok = await svc.authenticate()
        if not ok or (svc.session_token or "").startswith("mock_"):
            return False
        from services.data_fetcher import DataFetcher  # type: ignore
        fetcher = DataFetcher(svc)
        data = await fetcher.get_historical_data(str(instrument_id), "1D", from_date=from_date_str, to_date=to_date_str)
        if data:
            with open(out_path, "w", encoding="utf-8") as outf:
                json.dump({"status": "Ok", "result": data}, outf, indent=2)
            return True
        return False
    except Exception:
        return False


def fetch_direct(token: str, instrument_id: str | int, from_date_str: str, to_date_str: str, out_path: str) -> bool:
    url = "https://api.iiflcapital.com/v1/marketdata/historicaldata"
    headers = {"Content-Type": "application/json", "Authorization": token}
    payload = {
        "exchange": "NSEEQ",
        "instrumentId": str(instrument_id),
        "interval": "1 day",
        "fromDate": from_date_str,
        "toDate": to_date_str,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    with open(out_path, "w", encoding="utf-8") as outf:
        json.dump(data, outf, indent=2)
    return True


def main():
    base_dir = BASE_DIR
    files_dir = os.path.join(base_dir, 'files')
    ensure_dirs(files_dir)

    holding_path = os.path.join(files_dir, 'holding.json')
    auth_token_path = os.path.join(files_dir, 'auth_token.txt')
    output_dir = files_dir

    logger.info(f"Reading holdings from: {holding_path}")
    logger.info(f"Reading auth token from: {auth_token_path}")

    # Date range: last 5 years
    to_date = datetime.now()
    from_date = to_date - timedelta(days=5 * 365)
    to_date_str = to_date.strftime("%d-%b-%Y").lower()
    from_date_str = from_date.strftime("%d-%b-%Y").lower()

    # Inputs
    if not os.path.exists(holding_path):
        example_src = os.path.join(files_dir, 'holding.example.json')
        raise FileNotFoundError(f"{holding_path} not found. Copy {example_src} to holding.json and edit.")
    if not os.path.exists(auth_token_path):
        example_src = os.path.join(files_dir, 'auth_token.example.txt')
        raise FileNotFoundError(f"{auth_token_path} not found. Copy {example_src} to auth_token.txt and paste your token.")

    holdings = load_holdings(holding_path)
    token = read_auth_token(auth_token_path)

    # Iterate holdings
    successes = 0
    failures = 0
    for h in holdings:
        instrument_id = h.get("nseInstrumentId")
        symbol = h.get("nseTradingSymbol", "")
        if not instrument_id or not symbol:
            logger.warning(f"Skipping holding with missing instrumentId or symbol: {h}")
            continue

        out_path = os.path.join(output_dir, f"{symbol}_candles.json")

        try:
            logger.info(f"Fetching candle data for {symbol} (instrumentId={instrument_id})")
            # Try internal async service first
            if asyncio.run(fetch_with_internal_service(symbol, instrument_id, from_date_str, to_date_str, out_path)):
                logger.info(f"Saved (internal): {out_path}")
                successes += 1
                continue
        except Exception:
            pass

        try:
            # Fallback to direct requests flow
            if fetch_direct(token, instrument_id, from_date_str, to_date_str, out_path):
                logger.info(f"Saved: {out_path}")
                successes += 1
            else:
                failures += 1
        except Exception as e:
            logger.error(f"Failed for {symbol}: {e}")
            failures += 1

    logger.info(f"Done. Success: {successes}, Failed: {failures}")


if __name__ == "__main__":
    main()

