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
    
    for test_symbol in test_symbols:
        print("\n" + "="*50)
        print(f"Testing with symbol format: '{test_symbol}'")
        
        payload_preview = {
            "symbol": test_symbol,
            "interval": "1D",
            "fromDate": from_date,
            "toDate": to_date
        }
        print(f"Request Payload (initial intent): {json.dumps(payload_preview, indent=2)}")

        # Use high-level method with enhanced fallbacks
        normalized = await iifl_service.get_historical_data(test_symbol, "1D", from_date, to_date)

        if isinstance(normalized, dict):
            # Show raw when available
            print(f"Raw API Response: {json.dumps(normalized, indent=2)}")
            status = normalized.get("status", normalized.get("stat", "Unknown"))
            message = normalized.get("message", normalized.get("emsg", "No message"))
            result_data = normalized.get("result") or normalized.get("data") or normalized.get("resultData") or []
            if isinstance(result_data, list) and result_data:
                print(f"\n[SUCCESS] Received {len(result_data)} records (dict form). Sample: {result_data[0]}")
                break
            else:
                print(f"\n[FAILED] Status: {status}, Message: {message}")
        elif isinstance(normalized, list):
            print(f"\n[SUCCESS] Received {len(normalized)} records (standardized list). Sample: {normalized[0] if normalized else {}}")
            break
        else:
            print("\n[FAILED] No data returned.")

if __name__ == "__main__":
    asyncio.run(debug_historical_data())