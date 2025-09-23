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
    print("=== IIFL Order Format & Margin Validation Test ===\n")
    
    # Initialize services
    iifl_service = IIFLAPIService()
    data_fetcher = DataFetcher(iifl_service)
    
    # Test authentication
    auth_result = await iifl_service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    
    if not iifl_service.session_token.startswith('mock_'):
        print("Using real IIFL data\n")
        
        # Test cases for margin calculation
        # Using instrument IDs as required by the IIFL API.
        # 1594: INFY, 2885: RELIANCE, 11536: TCS
        test_cases = [
            {
                "description": "Simple MARKET BUY order (Normal)",
                "symbol": "1594",  # INFY
                "quantity": 10,
                "transaction_type": "BUY",
                "price": None,  # Market order
                "product": "NORMAL",
                "exchange": "NSEEQ"
            },
            {
                "description": "LIMIT SELL order (Intraday)",
                "symbol": "2885", # RELIANCE
                "quantity": 5,
                "transaction_type": "SELL",
                "price": 3000.00, # Required for LIMIT order
                "product": "INTRADAY",
                "exchange": "NSEEQ"
            },
            {
                "description": "Large quantity MARKET BUY order (Delivery)",
                "symbol": "11536", # TCS
                "quantity": 50,
                "transaction_type": "BUY",
                "price": None,
                "product": "DELIVERY",
                "exchange": "NSEEQ"
            },
            {
                "description": "BNPL (Buy Now, Pay Later) order",
                "symbol": "1594", # INFY
                "quantity": 2,
                "transaction_type": "BUY",
                "price": 1600.00,
                "product": "BNPL",
                "exchange": "NSEEQ"
            },
            {
                "description": "Invalid Request: LIMIT order without price",
                "symbol": "2885", # RELIANCE
                "quantity": 1,
                "transaction_type": "BUY",
                "price": None, # This should cause an error from the API
                "product": "NORMAL",
                "exchange": "NSEEQ",
                "order_type": "LIMIT", # Explicitly set for this test
                "expect_fail": True
            }
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print("-" * 50)
            print(f"Test Case {i}: {test_case['description']}")
            print(f"  - Symbol: {test_case['symbol']}, Quantity: {test_case['quantity']}")
            print(f"  - Type: {test_case['transaction_type']}, Product: {test_case['product']}")
            if test_case.get('price'):
                print(f"  - Price: {test_case.get('price')}")
            
            try:
                margin_info = await data_fetcher.calculate_required_margin(
                    symbol=test_case["symbol"],
                    quantity=test_case["quantity"],
                    transaction_type=test_case["transaction_type"],
                    price=test_case.get("price"),
                    product=test_case["product"],
                    exchange=test_case["exchange"],
                    order_type=test_case.get("order_type")
                )
                
                if margin_info:
                    print(f"  ✅ SUCCESS: IIFL API accepted the request format.")
                    print(f"     - Required Margin: Rs.{margin_info.get('current_order_margin', 0):,.2f}")
                    print(f"     - RMS Validation: {margin_info.get('rms_validation', 'N/A')}")
                    if test_case.get("expect_fail"):
                        print("  ⚠️ WARNING: This test was expected to fail but succeeded.")
                else:
                    if test_case.get("expect_fail"):
                        print(f"  ✅ SUCCESS (as expected): IIFL API correctly rejected the invalid request.")
                    else:
                        print(f"  ❌ FAILED: Could not get a valid response from IIFL API.")
                    
            except Exception as e:
                print(f"  ERROR: {str(e)}")
            
            print()
    else:
        print("Using mock data - update auth code in .env for live testing")

if __name__ == "__main__":
    asyncio.run(test_margin_calculation())
