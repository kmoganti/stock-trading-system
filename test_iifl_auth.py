#!/usr/bin/env python3
"""
Test IIFL authentication and token storage
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
from services.logging_service import trading_logger

async def test_iifl_authentication():
    """Test IIFL authentication and verify token storage"""
    print("=== IIFL Authentication Test ===\n")
    
    # Create IIFL service instance
    iifl_service = IIFLAPIService()
    
    print("1. Initial state:")
    print(f"   Session Token: {iifl_service.session_token}")
    print(f"   Token Expiry: {iifl_service.token_expiry}")
    print(f"   Auth Code: {iifl_service.auth_code[:8]}..." if iifl_service.auth_code else "   Auth Code: None")
    print(f"   Base URL: {iifl_service.base_url}")
    print(f"   Endpoint: {iifl_service.get_user_session_endpoint}")
    print()
    
    print("2. Testing authentication...")
    auth_result = await iifl_service.authenticate()
    print(f"   Authentication result: {auth_result}")
    print(f"   Session Token after auth: {iifl_service.session_token[:20]}..." if iifl_service.session_token else "   Session Token: None")
    print(f"   Token Expiry after auth: {iifl_service.token_expiry}")
    print()
    
    print("3. Testing token reuse...")
    # Test that subsequent calls reuse the token
    auth_result2 = await iifl_service._ensure_authenticated()
    print(f"   Token reuse result: {auth_result2}")
    print(f"   Same token: {iifl_service.session_token[:20]}..." if iifl_service.session_token else "   Token: None")
    print()
    
    print("4. Testing API calls with token...")
    try:
        # Test holdings API call
        print("   Testing holdings API...")
        holdings = await iifl_service.get_holdings()
        print(f"   Holdings result: {'Success' if holdings else 'Failed'}")
        
        # Test positions API call
        print("   Testing positions API...")
        positions = await iifl_service.get_positions()
        print(f"   Positions result: {'Success' if positions else 'Failed'}")
        
        # Test profile API call
        print("   Testing profile API...")
        profile = await iifl_service.get_profile()
        print(f"   Profile result: {'Success' if profile else 'Failed'}")
        
    except Exception as e:
        print(f"   API test error: {e}")
    
    print("\n5. Final token state:")
    print(f"   Session Token: {iifl_service.session_token[:20]}..." if iifl_service.session_token else "   Session Token: None")
    print(f"   Token Expiry: {iifl_service.token_expiry}")
    print(f"   Token Valid: {iifl_service.token_expiry and iifl_service.token_expiry > iifl_service.token_expiry.__class__.now() if iifl_service.token_expiry else False}")

if __name__ == "__main__":
    asyncio.run(test_iifl_authentication())
