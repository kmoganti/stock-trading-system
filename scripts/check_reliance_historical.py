#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES_DIR = os.path.join(BASE_DIR, "files")
AUTH_TOKEN_PATH = os.path.join(FILES_DIR, "auth_token.txt")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def read_auth_token(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read().strip()
            if not raw:
                return None
            return raw if raw.lower().startswith("bearer ") else f"Bearer {raw}"
    except Exception as e:
        logger.error(f"Failed to read auth token: {e}")
        return None


def load_contracts() -> List[Dict[str, Any]]:
    url = "https://api.iiflcapital.com/v1/contractfiles/NSEEQ.json"
    logger.info("Downloading NSEEQ contracts JSON...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("result") and isinstance(data["result"], list):
        return data["result"]
    if isinstance(data, list):
        return data
    raise ValueError("Unexpected contracts JSON structure")


def get_instrument_id_map(contracts: List[Dict[str, Any]]) -> Dict[str, Any]:
    id_map: Dict[str, Any] = {}
    for c in contracts:
        tsym = c.get("tradingSymbol")
        exch = c.get("exchange")
        if tsym and exch == "NSEEQ":
            id_map[tsym] = c.get("instrumentId")
    logger.info(f"Created instrument ID map with {len(id_map)} entries.")
    return id_map


def find_reliance_instrument_id(id_map: Dict[str, Any]) -> Optional[str]:
    # Try common trading symbols
    for key in ["RELIANCE", "RELIANCE-EQ"]:
        if key in id_map and id_map[key]:
            return str(id_map[key])
    # Fallback: search keys containing RELIANCE
    for k, v in id_map.items():
        if isinstance(k, str) and "RELIANCE" in k.upper() and v:
            return str(v)
    return None


def fetch_historical_direct(token: str, instrument_id: str, from_date: str, to_date: str) -> Dict[str, Any]:
    url = "https://api.iiflcapital.com/v1/marketdata/historicaldata"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {
        "exchange": "NSEEQ",
        "instrumentId": str(instrument_id),
        "interval": "1 day",
        "fromDate": from_date,
        "toDate": to_date,
    }
    logger.info(f"POST {url} for instrumentId={instrument_id}")
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    # Date range: ~1 year for a quick check
    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=365)
    to_date_str = to_dt.strftime("%d-%b-%Y").lower()
    from_date_str = from_dt.strftime("%d-%b-%Y").lower()

    if not os.path.exists(AUTH_TOKEN_PATH):
        example = os.path.join(FILES_DIR, "auth_token.example.txt")
        logger.error(f"{AUTH_TOKEN_PATH} not found. Copy {example} to auth_token.txt and paste your token.")
        return 1

    token = read_auth_token(AUTH_TOKEN_PATH)
    if not token:
        logger.error("Auth token is missing or empty.")
        return 1

    try:
        contracts = load_contracts()
        id_map = get_instrument_id_map(contracts)
        reliance_id = find_reliance_instrument_id(id_map)
        if not reliance_id:
            logger.error("Could not resolve RELIANCE instrumentId from contracts map.")
            return 1

        logger.info(f"Using RELIANCE instrumentId={reliance_id}")
        data = fetch_historical_direct(token, reliance_id, from_date_str, to_date_str)
        # Summarize
        result_list = (
            data.get("result")
            or data.get("data")
            or data.get("resultData")
            or data.get("candles")
            or data.get("history")
            or []
        )
        count = len(result_list) if isinstance(result_list, list) else 0
        status = data.get("status") or data.get("stat")
        logger.info(f"Historical fetch status={status}, records={count}")

        # Save minimal output for inspection
        out_path = os.path.join(FILES_DIR, "RELIANCE_candles_check.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved response to {out_path}")
        print(json.dumps({"ok": True, "status": status, "records": count, "out": out_path}, indent=2))
        return 0
    except Exception as e:
        logger.exception(f"Failed to fetch RELIANCE historical data: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())

