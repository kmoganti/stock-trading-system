#!/usr/bin/env python3
"""
Debug IIFL historical data API response
"""

import asyncio
import sys
import os
import json
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService

# Ensure env is loaded even without pydantic settings
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

async def debug_historical_data():
    """Debug historical data API response"""
    print("=== IIFL Historical Data Debug ===")
    
    # Initialize service
    iifl_service = IIFLAPIService()
    
    # Test authentication
    auth_result = await iifl_service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    
    if not auth_result or iifl_service.session_token.startswith('mock_'):
        print("Cannot proceed without a real authentication token. Please update your .env file.")
        return
    
    # Calculate date range
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"Date range: {from_date} to {to_date}")
    
    # Test with different symbol formats for a known stock (RELIANCE)
    # 2885 is the instrumentId for RELIANCE
    test_symbols = ["RELIANCE", "RELIANCE-EQ", "2885"]
    
    # Use a known working date format from other scripts as a primary test
    from_date_fmt = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y").lower()
    to_date_fmt = datetime.now().strftime("%d-%b-%Y").lower()
    
    # Define a few payload variants to test directly
    payload_variants = [
        {"desc": "Symbol with YYYY-MM-DD", "payload": {"symbol": "RELIANCE", "interval": "1D", "fromDate": from_date, "toDate": to_date}},
        {"desc": "InstrumentID with YYYY-MM-DD", "payload": {"instrumentId": "2885", "interval": "1D", "fromDate": from_date, "toDate": to_date}},
        {"desc": "InstrumentID with dd-Mon-YYYY", "payload": {"instrumentId": "2885", "exchange": "NSEEQ", "interval": "1 day", "fromDate": from_date_fmt, "toDate": to_date_fmt}},
        {"desc": "Symbol with dd-Mon-YYYY", "payload": {"symbol": "RELIANCE", "exchange": "NSEEQ", "interval": "1 day", "fromDate": from_date_fmt, "toDate": to_date_fmt}},
    ]
    
    for variant in payload_variants:
        print("\n" + "="*50)
        print(f"Testing with payload variant: '{variant['desc']}'")
        payload = variant["payload"]
        print(f"Request Payload: {json.dumps(payload, indent=2)}")
    
        # Use the internal _make_api_request for a direct test
        response = await iifl_service._make_api_request("POST", "/marketdata/historicaldata", payload)
    
        if isinstance(response, dict):
            print(f"Raw API Response: {json.dumps(response, indent=2)}")
            status = response.get("status", response.get("stat", "Unknown"))
            message = response.get("message", response.get("emsg", "No message"))
            result_data = response.get("result") or response.get("data") or response.get("resultData")
    
            if isinstance(result_data, list) and result_data:
                print(f"\n[SUCCESS] Received {len(result_data)} records. Sample: {result_data[0]}")
            else:
                print(f"\n[FAILED] Status: {status}, Message: {message}")
        else:
            print(f"\n[FAILED] Request failed. Response: {response}")

    print("\n" + "="*50)
    print("Testing high-level get_historical_data method...")
    # This will use all the internal fallbacks in iifl_api.py
    high_level_result = await iifl_service.get_historical_data("RELIANCE", "1D", from_date, to_date)
    if high_level_result and (high_level_result.get("result") or high_level_result.get("data")):
        print("[SUCCESS] High-level method succeeded.")
    else:
        print("[FAILED] High-level method failed to retrieve data.")

if __name__ == "__main__":
    asyncio.run(debug_historical_data())