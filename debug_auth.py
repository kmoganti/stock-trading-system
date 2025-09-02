#!/usr/bin/env python3
"""
Debug IIFL authentication - shows exact response structure
"""

import asyncio
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService

async def debug_authentication():
    """Debug authentication and show exact response"""
    print("=== IIFL Authentication Debug ===\n")
    
    service = IIFLAPIService()
    
    print("Configuration:")
    print(f"  Client ID: {service.client_id}")
    print(f"  Auth Code: {service.auth_code[:8]}..." if service.auth_code else "  Auth Code: None")
    print(f"  Base URL: {service.base_url}")
    print(f"  Endpoint: {service.get_user_session_endpoint}")
    print()
    
    print("Testing direct session request...")
    response_data = service.get_user_session(service.auth_code)
    
    print("Raw IIFL Response:")
    print(json.dumps(response_data, indent=2))
    print()
    
    print("Response Analysis:")
    print(f"  Status (stat): {response_data.get('stat')}")
    print(f"  Error Message (emsg): {response_data.get('emsg')}")
    print(f"  All Keys: {list(response_data.keys())}")
    print()
    
    if response_data.get("stat") == "Ok":
        print("[SUCCESS] Authentication successful!")
        # Look for session token
        for key in response_data.keys():
            if "token" in key.lower() or "session" in key.lower():
                print(f"  Found token field '{key}': {response_data[key]}")
    elif response_data.get("stat") == "Not_ok":
        print("[FAILED] Authentication failed!")
        print(f"  Error: {response_data.get('emsg')}")
        print("\nAction needed:")
        print("  1. Go to your IIFL trading account")
        print("  2. Navigate to Settings > API > Generate Auth Code")
        print("  3. Generate a new auth code")
        print("  4. Update it via the web interface at http://localhost:8000/auth")
    else:
        print(f"[UNKNOWN] Unknown status: {response_data.get('stat')}")

if __name__ == "__main__":
    asyncio.run(debug_authentication())
