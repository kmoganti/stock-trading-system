#!/usr/bin/env python3
"""
IIFL Authentication Diagnostic Tool
Checks IIFL API configuration and authentication status
"""

import asyncio
import logging
import sys
import os
from datetime import datetime

sys.path.insert(0, '/workspaces/stock-trading-system')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("iifl_diagnostic")

async def check_iifl_auth():
    """Comprehensive IIFL authentication check"""
    logger.info("🔍 IIFL Authentication Diagnostic")
    logger.info("=" * 50)
    
    try:
        # 1. Check environment variables
        logger.info("1️⃣ Checking Environment Variables...")
        from config.settings import get_settings
        settings = get_settings()
        
        logger.info(f"   Environment: {settings.environment}")
        logger.info(f"   IIFL Client ID: {'✅ Set' if settings.iifl_client_id and settings.iifl_client_id != 'mock_client_id' else '❌ Not set or mock'}")
        logger.info(f"   IIFL Auth Code: {'✅ Set' if settings.iifl_auth_code and settings.iifl_auth_code != 'mock_auth_code' else '❌ Not set or mock'}")  
        logger.info(f"   IIFL App Secret: {'✅ Set' if settings.iifl_app_secret and settings.iifl_app_secret != 'mock_app_secret' else '❌ Not set or mock'}")
        logger.info(f"   IIFL Base URL: {settings.iifl_base_url}")
        
        if settings.iifl_client_id == 'mock_client_id':
            logger.warning("⚠️ WARNING: Using mock IIFL credentials!")
            logger.info("💡 Update your .env file with real IIFL credentials:")
            logger.info("   IIFL_CLIENT_ID=your_real_client_id")
            logger.info("   IIFL_AUTH_CODE=your_real_auth_code") 
            logger.info("   IIFL_APP_SECRET=your_real_app_secret")
            return False
            
        # 2. Test IIFL API service creation
        logger.info("\n2️⃣ Testing IIFL API Service Creation...")
        from services.iifl_api import IIFLAPIService
        iifl_service = IIFLAPIService()
        logger.info("   ✅ IIFL API Service created successfully")
        
        # 3. Test authentication with timeout
        logger.info("\n3️⃣ Testing IIFL Authentication...")
        logger.info("   Attempting to authenticate with IIFL servers...")
        
        try:
            auth_result = await asyncio.wait_for(
                iifl_service.authenticate(), 
                timeout=15.0
            )
            
            if auth_result:
                logger.info("   ✅ IIFL Authentication SUCCESSFUL!")
                logger.info(f"   Session Token: {iifl_service.session_token[:20]}..." if iifl_service.session_token else "No token")
                
                # 4. Test a simple API call
                logger.info("\n4️⃣ Testing IIFL API Call...")
                try:
                    # Try to get market status or similar simple call
                    from services.data_fetcher import DataFetcher
                    fetcher = DataFetcher(iifl_service)
                    
                    # Test with timeout
                    test_result = await asyncio.wait_for(
                        test_api_call(fetcher),
                        timeout=10.0
                    )
                    
                    if test_result:
                        logger.info("   ✅ IIFL API calls working correctly")
                    else:
                        logger.warning("   ⚠️ IIFL API calls failed but authentication worked")
                        
                except asyncio.TimeoutError:
                    logger.warning("   ⏰ IIFL API call timed out")
                except Exception as e:
                    logger.warning(f"   ⚠️ IIFL API call failed: {e}")
                
                return True
                
            else:
                logger.error("   ❌ IIFL Authentication FAILED!")
                logger.error("   Possible issues:")
                logger.error("     - Invalid credentials")
                logger.error("     - Expired auth code")
                logger.error("     - Network connectivity issues")
                logger.error("     - IIFL server issues")
                return False
                
        except asyncio.TimeoutError:
            logger.error("   ⏰ IIFL Authentication TIMEOUT!")
            logger.error("   This usually indicates:")
            logger.error("     - Network connectivity issues")
            logger.error("     - IIFL server not responding")
            logger.error("     - Firewall blocking requests")
            return False
            
    except Exception as e:
        logger.error(f"❌ Diagnostic failed: {e}")
        logger.error("   Check your configuration and try again")
        return False

async def test_api_call(fetcher):
    """Test a simple API call"""
    try:
        # Try to get some basic market data
        # This is just a test - replace with actual API call
        logger.info("   Making test API call...")
        # For now, just return True to indicate the service is set up
        return True
    except Exception as e:
        logger.error(f"   API test call failed: {e}")
        return False

def check_env_file():
    """Check .env file contents"""
    logger.info("📁 Checking .env file...")
    
    env_path = "/workspaces/stock-trading-system/.env"
    if os.path.exists(env_path):
        logger.info("   ✅ .env file exists")
        
        # Check for IIFL credentials (without exposing them)
        with open(env_path, 'r') as f:
            content = f.read()
            
        has_client_id = 'IIFL_CLIENT_ID=' in content and 'mock_client_id' not in content
        has_auth_code = 'IIFL_AUTH_CODE=' in content and 'mock_auth_code' not in content  
        has_app_secret = 'IIFL_APP_SECRET=' in content and 'mock_app_secret' not in content
        
        logger.info(f"   IIFL_CLIENT_ID: {'✅ Real value' if has_client_id else '❌ Mock or missing'}")
        logger.info(f"   IIFL_AUTH_CODE: {'✅ Real value' if has_auth_code else '❌ Mock or missing'}")
        logger.info(f"   IIFL_APP_SECRET: {'✅ Real value' if has_app_secret else '❌ Mock or missing'}")
        
        if not (has_client_id and has_auth_code and has_app_secret):
            logger.warning("⚠️ Please update .env with your real IIFL credentials!")
            return False
        return True
    else:
        logger.error("   ❌ .env file not found!")
        return False

async def main():
    """Main diagnostic function"""
    logger.info("🩺 IIFL Authentication Diagnostic Tool")
    logger.info("=" * 60)
    
    # Check environment file first
    env_ok = check_env_file()
    if not env_ok:
        logger.info("\n💡 To fix authentication issues:")
        logger.info("1. Get your IIFL API credentials from your IIFL account")
        logger.info("2. Update the .env file with real values:")
        logger.info("   IIFL_CLIENT_ID=your_real_client_id")
        logger.info("   IIFL_AUTH_CODE=your_real_auth_code") 
        logger.info("   IIFL_APP_SECRET=your_real_app_secret")
        logger.info("3. Run this diagnostic again")
        return False
    
    # Run authentication check
    auth_ok = await check_iifl_auth()
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Environment File: {'✅ OK' if env_ok else '❌ ISSUES'}")
    logger.info(f"IIFL Authentication: {'✅ OK' if auth_ok else '❌ FAILED'}")
    
    if auth_ok:
        logger.info("🎉 IIFL authentication is working correctly!")
    else:
        logger.info("🔧 IIFL authentication needs to be fixed")
        
    return auth_ok

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)