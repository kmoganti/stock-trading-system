#!/usr/bin/env python3
"""
IIFL Authentication Diagnostic and Test Tool
"""

import asyncio
import logging
import sys
import os
import json
import hashlib
import httpx
from datetime import datetime
import traceback

sys.path.insert(0, '/workspaces/stock-trading-system')

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("iifl_auth_test")

class IIFLAuthTester:
    """Comprehensive IIFL Authentication Tester"""
    
    def __init__(self):
        self.base_url = "https://api.iiflcapital.com/v1"
        self.client_id = None
        self.auth_code = None
        self.app_secret = None
        
    def load_credentials(self):
        """Load credentials from environment variables"""
        logger.info("📋 Loading IIFL credentials...")
        
        # Load from .env file if available
        try:
            from dotenv import load_dotenv
            load_dotenv()
            logger.info("✅ Loaded .env file")
        except ImportError:
            logger.warning("⚠️ python-dotenv not available, using direct env vars")
        
        self.client_id = os.getenv("IIFL_CLIENT_ID", "")
        self.auth_code = os.getenv("IIFL_AUTH_CODE", "")
        self.app_secret = os.getenv("IIFL_APP_SECRET", "")
        
        # Validate credentials
        if not self.client_id or self.client_id == "mock_client_id":
            logger.error("❌ IIFL_CLIENT_ID is missing or still set to mock value")
            return False
            
        if not self.auth_code or self.auth_code == "mock_auth_code":
            logger.error("❌ IIFL_AUTH_CODE is missing or still set to mock value")
            return False
            
        if not self.app_secret or self.app_secret == "mock_app_secret":
            logger.error("❌ IIFL_APP_SECRET is missing or still set to mock value")
            return False
        
        logger.info(f"✅ Client ID: {self.client_id[:10]}...")
        logger.info(f"✅ Auth Code: {self.auth_code[:10]}...")
        logger.info(f"✅ App Secret: {self.app_secret[:10]}...")
        
        return True
    
    def create_checksum(self):
        """Create checksum for IIFL authentication"""
        try:
            # IIFL checksum format: SHA256(client_id + auth_code + app_secret)
            combined = f"{self.client_id}{self.auth_code}{self.app_secret}"
            checksum = hashlib.sha256(combined.encode()).hexdigest()
            logger.info(f"✅ Generated checksum: {checksum[:16]}...")
            return checksum
        except Exception as e:
            logger.error(f"❌ Error creating checksum: {e}")
            return None
    
    async def test_connectivity(self):
        """Test basic connectivity to IIFL servers"""
        logger.info("🌐 Testing connectivity to IIFL servers...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test basic connectivity
                response = await client.get(f"{self.base_url.replace('/v1', '')}")
                logger.info(f"✅ Base connectivity: HTTP {response.status_code}")
                return True
        except httpx.TimeoutException:
            logger.error("❌ Connection timeout to IIFL servers")
            return False
        except Exception as e:
            logger.error(f"❌ Connectivity error: {e}")
            return False
    
    async def test_authentication(self):
        """Test IIFL authentication"""
        logger.info("🔐 Testing IIFL authentication...")
        
        checksum = self.create_checksum()
        if not checksum:
            return False
        
        payload = {"checkSum": checksum}
        endpoint = f"{self.base_url}/getusersession"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                logger.info(f"📤 Sending authentication request to: {endpoint}")
                logger.info(f"📤 Payload: {payload}")
                
                response = await client.post(endpoint, json=payload)
                
                logger.info(f"📥 Response Status: {response.status_code}")
                logger.info(f"📥 Response Headers: {dict(response.headers)}")
                
                try:
                    response_data = response.json()
                    logger.info(f"📥 Response Data: {json.dumps(response_data, indent=2)}")
                    
                    # Check for successful authentication
                    if response.status_code == 200:
                        if response_data.get("stat") == "Ok":
                            session_token = response_data.get("result", {}).get("sessionToken")
                            if session_token:
                                logger.info(f"✅ Authentication successful!")
                                logger.info(f"✅ Session Token: {session_token[:20]}...")
                                return session_token
                            else:
                                logger.error("❌ No session token in response")
                        else:
                            error_msg = response_data.get("emsg", "Unknown error")
                            logger.error(f"❌ Authentication failed: {error_msg}")
                    else:
                        logger.error(f"❌ HTTP Error: {response.status_code}")
                        
                except json.JSONDecodeError:
                    logger.error(f"❌ Invalid JSON response: {response.text}")
                
                return False
                
        except httpx.TimeoutException:
            logger.error("❌ Authentication timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Authentication error: {e}")
            logger.error(traceback.format_exc())
            return False
    
    async def test_api_call(self, session_token):
        """Test a sample API call with the session token"""
        logger.info("📊 Testing sample API call...")
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Test getting portfolio
                endpoint = f"{self.base_url}/getportfolio"
                payload = {"sessionToken": session_token}
                
                response = await client.post(endpoint, json=payload)
                
                logger.info(f"📥 Portfolio API Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        logger.info(f"✅ API call successful: {data.get('stat', 'Unknown')}")
                        return True
                    except json.JSONDecodeError:
                        logger.warning("⚠️ API response not JSON")
                        return False
                else:
                    logger.error(f"❌ API call failed: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ API call error: {e}")
            return False
    
    async def run_comprehensive_test(self):
        """Run comprehensive authentication tests"""
        logger.info("🚀 Starting Comprehensive IIFL Authentication Test")
        logger.info("=" * 60)
        
        # Test 1: Load credentials
        logger.info("\n1️⃣ Testing Credential Loading...")
        if not self.load_credentials():
            logger.error("❌ Credential loading failed - cannot proceed")
            return False
        
        # Test 2: Connectivity
        logger.info("\n2️⃣ Testing Connectivity...")
        if not await self.test_connectivity():
            logger.error("❌ Connectivity test failed - check internet connection")
            return False
        
        # Test 3: Authentication
        logger.info("\n3️⃣ Testing Authentication...")
        session_token = await self.test_authentication()
        if not session_token:
            logger.error("❌ Authentication failed - check credentials")
            return False
        
        # Test 4: API Call
        logger.info("\n4️⃣ Testing API Call...")
        api_success = await self.test_api_call(session_token)
        
        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("📊 AUTHENTICATION TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"📋 Credentials:    ✅ VALID")
        logger.info(f"🌐 Connectivity:   ✅ WORKING")
        logger.info(f"🔐 Authentication: ✅ SUCCESS")
        logger.info(f"📊 API Calls:      {'✅ WORKING' if api_success else '⚠️ LIMITED'}")
        logger.info("=" * 60)
        
        if api_success:
            logger.info("🎉 All tests passed! IIFL authentication is working correctly.")
        else:
            logger.info("⚠️ Authentication works but API calls may be limited.")
        
        return True

async def test_current_iifl_service():
    """Test the current IIFL service implementation"""
    logger.info("\n🔧 Testing Current IIFL Service Implementation...")
    
    try:
        from services.iifl_api import IIFLAPIService
        
        iifl = IIFLAPIService()
        logger.info("✅ IIFL service created")
        
        # Test authentication with timeout
        logger.info("🔐 Testing service authentication...")
        auth_result = await asyncio.wait_for(iifl.authenticate(), timeout=20.0)
        
        if auth_result:
            logger.info("✅ Service authentication successful")
            logger.info(f"✅ Session token: {iifl.session_token[:20] if iifl.session_token else 'None'}...")
            return True
        else:
            logger.error("❌ Service authentication failed")
            return False
            
    except asyncio.TimeoutError:
        logger.error("❌ Service authentication timed out")
        return False
    except Exception as e:
        logger.error(f"❌ Service test failed: {e}")
        logger.error(traceback.format_exc())
        return False

async def main():
    """Main test function"""
    logger.info("🎯 IIFL Authentication Comprehensive Test Suite")
    logger.info("=" * 80)
    
    # Test 1: Custom authentication tester
    tester = IIFLAuthTester()
    custom_test_success = await tester.run_comprehensive_test()
    
    # Test 2: Current service implementation
    service_test_success = await test_current_iifl_service()
    
    # Final summary
    logger.info("\n" + "=" * 80)
    logger.info("🏁 FINAL TEST RESULTS")
    logger.info("=" * 80)
    logger.info(f"🔧 Custom Auth Test:  {'✅ PASS' if custom_test_success else '❌ FAIL'}")
    logger.info(f"🏗️ Service Test:      {'✅ PASS' if service_test_success else '❌ FAIL'}")
    
    if custom_test_success and service_test_success:
        logger.info("🎉 ALL TESTS PASSED! IIFL authentication is working correctly.")
        return True
    elif custom_test_success:
        logger.info("⚠️ Custom auth works but service implementation has issues.")
        return False
    else:
        logger.info("❌ Authentication is not working. Please check your credentials.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)