#!/usr/bin/env python3
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

import asyncio
from services.iifl_api import IIFLAPIService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Ensure env is loaded for the service to find credentials
from dotenv import load_dotenv
load_dotenv()

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
    import requests
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

async def main() -> int:
    try:
        # 1. Get instrument ID for Reliance
        contracts = load_contracts()
        id_map = get_instrument_id_map(contracts)
        reliance_id = find_reliance_instrument_id(id_map)
        if not reliance_id:
            logger.error("Could not resolve RELIANCE instrumentId from contracts map.")
            return 1
        logger.info(f"Using RELIANCE instrumentId={reliance_id}")

        # 2. Instantiate service and authenticate
        service = IIFLAPIService()
        auth_ok = await service.authenticate()
        if not auth_ok or (service.session_token or "").startswith("mock_"):
            logger.error("Authentication failed or using mock token. Cannot proceed.")
            return 1

        # 3. Fetch historical data using the service
        to_date = datetime.now()
        from_date = to_date - timedelta(days=5)
        from_date_str = from_date.strftime("%Y-%m-%d")
        to_date_str = to_date.strftime("%Y-%m-%d")

        logger.info(f"Fetching historical data for ID {reliance_id} from {from_date_str} to {to_date_str}")
        data = await service.get_historical_data(reliance_id, "1D", from_date_str, to_date_str)

        if data and (data.get("result") or data.get("data")):
            logger.info("Successfully fetched historical data.")
            logger.info(f"Response sample: {json.dumps(data, indent=2)}")
        else:
            logger.error("Failed to fetch historical data via service.")
            logger.error(f"Final API response: {json.dumps(data, indent=2)}")
            return 1

        return 0
    except Exception as e:
        logger.exception(f"Failed to fetch RELIANCE historical data: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
