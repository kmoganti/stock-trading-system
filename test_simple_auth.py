#!/usr/bin/env python3
"""
Simple test for IIFL authentication using env file only
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService

async def test_simple_auth():
    """Test authentication using only env file"""
    print("=== Simple IIFL Auth Test (Env File Only) ===\n")
    
    service = IIFLAPIService()
    
    print("DEBUG: Configuration from env file:")
    print(f"  Client ID: {service.client_id}")
    print(f"  Auth Code: {service.auth_code}")
    print(f"  App Secret: {service.app_secret[:8]}..." if service.app_secret else "  App Secret: None")
    print(f"  Base URL: {service.base_url}")
    print(f"  Endpoint: {service.get_user_session_endpoint}")
    print()
    
    print("DEBUG: Testing checksum generation...")
    checksum_str = service.client_id + service.auth_code + service.app_secret
    checksum = service.sha256_hash(checksum_str)
    print(f"  Checksum String Length: {len(checksum_str)}")
    print(f"  Generated Checksum: {checksum}")
    print()
    
    print("DEBUG: Testing authentication...")
    auth_result = await service.authenticate()
    print(f"  Authentication Result: {auth_result}")
    print(f"  Session Token: {service.session_token}")
    print(f"  Token Expiry: {service.token_expiry}")
    print()
    
    if service.session_token and not service.session_token.startswith("mock_"):
        print("SUCCESS: Real IIFL authentication successful!")
        print("Testing API calls...")
        
        # Test holdings
        holdings = await service.get_holdings()
        print(f"  Holdings API: {'Success' if holdings else 'Failed'}")
        
        # Test positions  
        positions = await service.get_positions()
        print(f"  Positions API: {'Success' if positions else 'Failed'}")
        
    elif service.session_token and service.session_token.startswith("mock_"):
        print("INFO: Using mock session (IIFL auth failed)")
        print("  This means the auth code in .env file needs to be updated")
    else:
        print("ERROR: No session token generated")

if __name__ == "__main__":
    asyncio.run(test_simple_auth())
