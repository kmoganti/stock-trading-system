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
        
        data = {
            "symbol": test_symbol,
            "interval": "1D",
            "fromDate": from_date,
            "toDate": to_date
        }
        
        print(f"Request Payload: {json.dumps(data, indent=2)}")
        
        # We call _make_api_request directly to bypass any logic in get_historical_data
        test_result = await iifl_service._make_api_request("POST", "/marketdata/historicaldata", data)
        
        print(f"Raw API Response: {json.dumps(test_result, indent=2) if test_result else 'None'}")
        
        if test_result:
            status = test_result.get("status", "Unknown")
            message = test_result.get("message", "No message")
            result_data = test_result.get("result", [])
            
            if status == "Ok" and isinstance(result_data, list) and result_data:
                print(f"\n[SUCCESS] This format worked! Received {len(result_data)} records.")
                print(f"Sample record: {result_data[0]}")
                break # Stop on first success
            else:
                print(f"\n[FAILED] Status: {status}, Message: {message}")

if __name__ == "__main__":
    asyncio.run(debug_historical_data())