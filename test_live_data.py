#!/usr/bin/env python3
"""
Test live data retrieval from IIFL API
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService

async def test_live_data():
    """Test live data retrieval from IIFL API"""
    print("=== IIFL Live Data Test ===\n")
    
    service = IIFLAPIService()
    
    # Authenticate
    auth_result = await service.authenticate()
    print(f"Authentication: {'SUCCESS' if auth_result else 'FAILED'}")
    print(f"Token Type: {'Real IIFL' if not service.session_token.startswith('mock_') else 'Mock'}")
    print()
    
    if not service.session_token.startswith('mock_'):
        print("Testing live data retrieval...")
        
        # Test holdings
        print("1. Testing Holdings API...")
        holdings = await service.get_holdings()
        if holdings:
            print(f"   SUCCESS: Holdings API successful")
            print(f"   Data type: {type(holdings)}")
            print(f"   Data: {json.dumps(holdings, indent=2)[:300]}...")
        else:
            print("   FAILED: Holdings API failed")
        
        # Test positions
        print("\n2. Testing Positions API...")
        positions = await service.get_positions()
        if positions:
            print(f"   SUCCESS: Positions API successful")
            print(f"   Data type: {type(positions)}")
            print(f"   Data: {json.dumps(positions, indent=2)[:300]}...")
        else:
            print("   FAILED: Positions API failed")
        
        # Test profile
        print("\n3. Testing Profile API...")
        profile = await service.get_profile()
        if profile:
            print(f"   SUCCESS: Profile API successful")
            if profile:
                print(f"   Sample: {json.dumps(profile, indent=2)[:200]}...")
        else:
            print("   FAILED: Profile API failed")
            
    else:
        print("Using mock token - cannot test live data")
        print("Update auth code in .env file for live data testing")

if __name__ == "__main__":
    asyncio.run(test_live_data())
