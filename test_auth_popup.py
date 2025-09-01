#!/usr/bin/env python3
"""
Test script to trigger auth code popup functionality
"""
import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.iifl_api import IIFLAPIService
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_auth_popup():
    """Test auth code popup by forcing authentication failure"""
    try:
        logger.info("Testing IIFL API authentication with current auth code...")
        
        # Initialize IIFL API service
        iifl = IIFLAPIService()
        
        # Try to authenticate - this should fail and trigger popup
        result = await iifl.authenticate()
        
        if result:
            logger.info("Authentication successful!")
        else:
            logger.info("Authentication failed - popup should have appeared")
        
        # Try to get portfolio data which will also trigger auth
        logger.info("Testing portfolio data fetch...")
        portfolio_data = await iifl.get_positions()
        
        if portfolio_data:
            logger.info(f"Portfolio data received: {portfolio_data}")
        else:
            logger.info("Portfolio data fetch failed")
            
    except Exception as e:
        logger.error(f"Error testing auth popup: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_auth_popup())
