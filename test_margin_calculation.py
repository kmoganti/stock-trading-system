#!/usr/bin/env python3
"""
Test margin calculation using IIFL preordermargin API
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.data_fetcher import DataFetcher

async def test_margin_calculation():
    """Test margin calculation with real IIFL API"""
    print("=== IIFL Margin Calculation Test ===\n")
    
    # Initialize services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    
    # Test authentication
    auth_result = await iifl_service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    
    if not iifl_service.session_token.startswith('mock_'):
        print("Using real IIFL data\n")
        
        # First, let's test the raw API call to see the exact response
        print("Testing raw preordermargin API call...")
        
        # Test with a simple order payload
        test_payload = {
            "instrumentId": "1594",
            "exchange": "NSEEQ", 
            "transactionType": "BUY",
            "quantity": "10",
            "orderComplexity": "REGULAR",
            "product": "NORMAL",
            "orderType": "MARKET",
            "validity": "DAY"
        }
        
        print(f"Test payload: {json.dumps(test_payload, indent=2)}")
        
        # Make direct API call
        raw_result = await iifl_service._make_api_request("POST", "/preordermargin", test_payload)
        print(f"Raw API response: {json.dumps(raw_result, indent=2) if raw_result else 'None'}")
        
        # Test cases for margin calculation
        test_cases = [
            {
                "symbol": "1594",  # INFY instrument ID
                "quantity": 10,
                "transaction_type": "BUY",
                "price": None,  # Market order
                "product": "NORMAL",
                "exchange": "NSEEQ"
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"Test Case {i}: {test_case['symbol']} - {test_case['quantity']} shares")
            print(f"  Transaction: {test_case['transaction_type']} at Rs.{test_case['price']}")
            print(f"  Product: {test_case['product']}, Exchange: {test_case['exchange']}")
            
            try:
                margin_info = await data_fetcher.calculate_required_margin(
                    symbol=test_case["symbol"],
                    quantity=test_case["quantity"],
                    transaction_type=test_case["transaction_type"],
                    price=test_case["price"],
                    product=test_case["product"],
                    exchange=test_case["exchange"]
                )
                
                if margin_info:
                    print(f"  SUCCESS: Margin calculation completed")
                    print(f"    Total Cash Available: Rs.{margin_info['total_cash_available']:,.2f}")
                    print(f"    Pre-Order Margin: Rs.{margin_info['pre_order_margin']:,.2f}")
                    print(f"    Post-Order Margin: Rs.{margin_info['post_order_margin']:,.2f}")
                    print(f"    Required Margin: Rs.{margin_info['current_order_margin']:,.2f}")
                    print(f"    RMS Validation: {margin_info['rms_validation']}")
                    print(f"    Fund Shortage: Rs.{margin_info['fund_short']:,.2f}")
                else:
                    print(f"  FAILED: Could not calculate margin")
                    
            except Exception as e:
                print(f"  ERROR: {str(e)}")
            
            print()
    else:
        print("Using mock data - update auth code in .env for live testing")

if __name__ == "__main__":
    asyncio.run(test_margin_calculation())
