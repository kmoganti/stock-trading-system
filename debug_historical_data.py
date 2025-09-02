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
    
    if not auth_result:
        print("Cannot proceed without authentication")
        return
    
    # Calculate date range
    to_date = datetime.now().strftime("%Y-%m-%d")
    from_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    
    print(f"Date range: {from_date} to {to_date}")
    
    # Test with a simple symbol
    symbol = "RELIANCE"
    interval = "1D"
    
    print(f"\nTesting historical data for {symbol}...")
    
    # Make direct API call to see raw response
    data = {
        "symbol": symbol,
        "interval": interval,
        "fromDate": from_date,
        "toDate": to_date
    }
    
    print(f"Request payload: {json.dumps(data, indent=2)}")
    
    result = await iifl_service._make_api_request("POST", "/marketdata/historicaldata", data)
    
    print(f"\nRaw API Response:")
    print(f"Type: {type(result)}")
    print(f"Content: {json.dumps(result, indent=2) if result else 'None'}")
    
    # Test with different symbol formats
    test_symbols = ["RELIANCE", "RELIANCE-EQ", "RELIANCE.NSE", "500325"]
    
    for test_symbol in test_symbols:
        print(f"\nTesting symbol format: {test_symbol}")
        test_data = data.copy()
        test_data["symbol"] = test_symbol
        
        test_result = await iifl_service._make_api_request("POST", "/marketdata/historicaldata", test_data)
        
        if test_result:
            status = test_result.get("status", "Unknown")
            message = test_result.get("message", "No message")
            result_data = test_result.get("result", [])
            
            print(f"  Status: {status}")
            print(f"  Message: {message}")
            print(f"  Result count: {len(result_data) if isinstance(result_data, list) else 'Not a list'}")
            
            if isinstance(result_data, list) and result_data:
                print(f"  Sample data: {result_data[0]}")
                break
        else:
            print(f"  No response")

if __name__ == "__main__":
    asyncio.run(debug_historical_data())
