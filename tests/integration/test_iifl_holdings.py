#!/usr/bin/env python3
"""
IIFL Authentication Test - Fetch Holdings
This script tests IIFL authentication by attempting to fetch actual holdings data
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, '/workspaces/stock-trading-system')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("iifl_holdings_test")

async def test_iifl_holdings():
    """Test IIFL authentication by fetching holdings"""
    logger.info("🔍 Testing IIFL Authentication via Holdings Fetch")
    logger.info("=" * 60)
    
    try:
        # 1. Check environment configuration
        logger.info("1️⃣ Checking Configuration...")
        from config.settings import get_settings
        settings = get_settings()
        
        logger.info(f"   Environment: {settings.environment}")
        logger.info(f"   IIFL Base URL: {settings.iifl_base_url}")
        
        # Check if we have real credentials
        has_real_creds = (
            settings.iifl_client_id and settings.iifl_client_id != 'mock_client_id' and
            settings.iifl_auth_code and settings.iifl_auth_code != 'mock_auth_code' and
            settings.iifl_app_secret and settings.iifl_app_secret != 'mock_app_secret'
        )
        
        if not has_real_creds:
            logger.warning("⚠️ WARNING: Using mock credentials!")
            logger.info("   Mock credentials detected. Real API calls will fail.")
            logger.info("   Update .env with real IIFL credentials to test authentication.")
            return False
            
        logger.info("   ✅ Real IIFL credentials configured")
        
        # 2. Initialize IIFL API Service
        logger.info("\n2️⃣ Initializing IIFL API Service...")
        from services.iifl_api import IIFLAPIService
        iifl_service = IIFLAPIService()
        logger.info("   ✅ IIFL service created")
        
        # 3. Test Authentication
        logger.info("\n3️⃣ Testing Authentication...")
        try:
            auth_result = await asyncio.wait_for(
                iifl_service.authenticate(),
                timeout=20.0
            )
            
            if not auth_result:
                logger.error("   ❌ Authentication failed")
                logger.error("   Possible reasons:")
                logger.error("     - Invalid client ID, auth code, or app secret")
                logger.error("     - Expired auth code (IIFL auth codes expire)")
                logger.error("     - Account not activated for API trading")
                logger.error("     - Network connectivity issues")
                return False
                
            logger.info("   ✅ Authentication successful!")
            logger.info(f"   Session Token: {iifl_service.session_token[:20]}..." if iifl_service.session_token else "No token")
            
        except asyncio.TimeoutError:
            logger.error("   ⏰ Authentication timed out")
            logger.error("   This usually indicates network or server issues")
            return False
        except Exception as e:
            logger.error(f"   ❌ Authentication error: {e}")
            return False
            
        # 4. Test Holdings Fetch
        logger.info("\n4️⃣ Testing Holdings Fetch...")
        try:
            from services.data_fetcher import DataFetcher
            from models.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as session:
                fetcher = DataFetcher(iifl_service, db_session=session)
                
                logger.info("   Fetching portfolio holdings...")
                holdings_result = await asyncio.wait_for(
                    fetcher.get_portfolio_data(force_refresh=True),
                    timeout=30.0
                )
                
                if holdings_result:
                    logger.info("   ✅ Holdings fetch successful!")
                    
                    # Display holdings summary
                    if isinstance(holdings_result, dict):
                        logger.info(f"   Holdings data type: {type(holdings_result)}")
                        if 'holdings' in holdings_result:
                            holdings_count = len(holdings_result.get('holdings', []))
                            logger.info(f"   Number of holdings: {holdings_count}")
                            
                            # Show first few holdings (without sensitive data)
                            holdings = holdings_result.get('holdings', [])[:3]
                            for i, holding in enumerate(holdings, 1):
                                if isinstance(holding, dict):
                                    symbol = holding.get('symbol', 'Unknown')
                                    quantity = holding.get('quantity', 0)
                                    logger.info(f"   Holding {i}: {symbol} (Qty: {quantity})")
                        else:
                            logger.info(f"   Holdings data keys: {list(holdings_result.keys())}")
                    else:
                        logger.info(f"   Holdings data: {str(holdings_result)[:200]}...")
                        
                    return True
                else:
                    logger.warning("   ⚠️ Holdings fetch returned empty result")
                    logger.info("   This might indicate:")
                    logger.info("     - No holdings in the account")
                    logger.info("     - API response format changed")
                    logger.info("     - Insufficient API permissions")
                    return False
                    
        except asyncio.TimeoutError:
            logger.error("   ⏰ Holdings fetch timed out")
            return False
        except Exception as e:
            logger.error(f"   ❌ Holdings fetch error: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        return False

async def test_other_api_calls():
    """Test other API calls to verify authentication"""
    logger.info("\n5️⃣ Testing Additional API Calls...")
    
    try:
        from services.iifl_api import IIFLAPIService
        from services.data_fetcher import DataFetcher
        from models.database import AsyncSessionLocal
        
        iifl_service = IIFLAPIService()
        
        # Re-authenticate if needed
        if not iifl_service.session_token:
            await iifl_service.authenticate()
            
        async with AsyncSessionLocal() as session:
            fetcher = DataFetcher(iifl_service, db_session=session)
            
            # Test margin info
            logger.info("   Testing margin info fetch...")
            try:
                margin_result = await asyncio.wait_for(
                    fetcher.get_margin_info(force_refresh=True),
                    timeout=15.0
                )
                if margin_result:
                    logger.info("   ✅ Margin info fetch successful")
                    logger.info(f"   Margin data type: {type(margin_result)}")
                else:
                    logger.warning("   ⚠️ Margin info fetch returned empty")
            except Exception as e:
                logger.warning(f"   ⚠️ Margin info fetch failed: {e}")
            
            # Test historical data for a popular stock
            logger.info("   Testing historical data fetch...")
            try:
                historical_result = await asyncio.wait_for(
                    fetcher.get_historical_data("RELIANCE", period="1d", interval="1m"),
                    timeout=20.0
                )
                if historical_result:
                    logger.info("   ✅ Historical data fetch successful")
                    logger.info(f"   Historical data points: {len(historical_result) if isinstance(historical_result, list) else 'Unknown'}")
                else:
                    logger.warning("   ⚠️ Historical data fetch returned empty")
            except Exception as e:
                logger.warning(f"   ⚠️ Historical data fetch failed: {e}")
                
        return True
        
    except Exception as e:
        logger.error(f"   ❌ Additional API tests failed: {e}")
        return False

def check_credentials_in_env():
    """Check what credentials are actually in the .env file"""
    logger.info("📁 Checking .env file credentials...")
    
    env_path = "/workspaces/stock-trading-system/.env"
    if not os.path.exists(env_path):
        logger.error("   ❌ .env file not found!")
        return False
        
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
            
        creds_info = {}
        for line in lines:
            line = line.strip()
            if line.startswith('IIFL_CLIENT_ID='):
                value = line.split('=', 1)[1]
                creds_info['client_id'] = value
            elif line.startswith('IIFL_AUTH_CODE='):
                value = line.split('=', 1)[1]
                creds_info['auth_code'] = value
            elif line.startswith('IIFL_APP_SECRET='):
                value = line.split('=', 1)[1]
                creds_info['app_secret'] = value
                
        logger.info("   Credential status:")
        for key, value in creds_info.items():
            if value and not value.startswith('mock_'):
                logger.info(f"   ✅ {key}: Real value set (length: {len(value)})")
            else:
                logger.warning(f"   ❌ {key}: Mock or missing value")
                
        return all(value and not value.startswith('mock_') for value in creds_info.values())
        
    except Exception as e:
        logger.error(f"   ❌ Error reading .env file: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🩺 IIFL Holdings Authentication Test")
    logger.info("=" * 60)
    
    # Check credentials first
    creds_ok = check_credentials_in_env()
    if not creds_ok:
        logger.error("\n❌ Cannot proceed - no real IIFL credentials found")
        logger.info("\n💡 To fix this:")
        logger.info("1. Get your IIFL API credentials from your IIFL account dashboard")
        logger.info("2. Update your .env file:")
        logger.info("   IIFL_CLIENT_ID=your_real_client_id")
        logger.info("   IIFL_AUTH_CODE=your_real_auth_code")
        logger.info("   IIFL_APP_SECRET=your_real_app_secret")
        logger.info("3. Run this test again")
        return False
    
    # Run main authentication and holdings test
    main_test_result = await test_iifl_holdings()
    
    if main_test_result:
        # Run additional API tests
        additional_test_result = await test_other_api_calls()
    else:
        additional_test_result = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 IIFL AUTHENTICATION TEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Credentials Configuration: {'✅ OK' if creds_ok else '❌ FAILED'}")
    logger.info(f"Holdings Fetch Test:       {'✅ PASSED' if main_test_result else '❌ FAILED'}")
    logger.info(f"Additional API Tests:      {'✅ PASSED' if additional_test_result else '❌ FAILED'}")
    
    overall_success = creds_ok and main_test_result
    
    if overall_success:
        logger.info("\n🎉 SUCCESS: IIFL authentication is working correctly!")
        logger.info("   You can now run trading strategies and other API-dependent features.")
    else:
        logger.info("\n🔧 ISSUES FOUND: IIFL authentication needs attention")
        if not creds_ok:
            logger.info("   → Fix: Update .env with real IIFL credentials")
        if creds_ok and not main_test_result:
            logger.info("   → Fix: Check IIFL account status and API permissions")
            logger.info("   → Fix: Verify auth code hasn't expired")
            logger.info("   → Fix: Check network connectivity")
    
    return overall_success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)