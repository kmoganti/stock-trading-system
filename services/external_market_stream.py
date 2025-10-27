#!/usr/bin/env python3
"""
External Market Stream Service
Run as: python services/external_market_stream.py
"""

import asyncio
import logging
import os
import sys
import signal
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from services.iifl_api import IIFLAPIService
from services.market_stream import MarketStreamService
from services.watchlist import WatchlistService
from services.screener import ScreenerService
from models.database import AsyncSessionLocal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('logs/market_stream.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class ExternalMarketStreamService:
    """External Market Stream Service Runner"""
    
    def __init__(self):
        self.market_stream: MarketStreamService = None
        self.running = False
        self.settings = get_settings()
        self.iifl_service: IIFLAPIService = None
        
    async def start(self):
        """Start the market stream service"""
        try:
            # Check if market stream is enabled
            enable_market_stream = getattr(self.settings, "enable_market_stream", True)
            enable_market_stream = os.getenv("ENABLE_MARKET_STREAM", "true").lower() == "true" if enable_market_stream else False
            
            if not enable_market_stream:
                logger.warning("Market stream is disabled in configuration")
                return False
            
            logger.info("Starting External Market Stream Service...")
            
            # Initialize IIFL API service
            self.iifl_service = IIFLAPIService()
            auth_result = await self.iifl_service.authenticate()
            
            # Check for authentication errors
            if not auth_result:
                logger.error("❌ IIFL authentication failed - cannot start market stream")
                return False
            
            # Check for specific authentication issues
            if isinstance(auth_result, dict):
                if auth_result.get("auth_code_expired"):
                    logger.error("🔒 Auth code has expired. Please update IIFL_AUTH_CODE in .env file")
                    logger.error("Market stream service cannot continue - exiting")
                    return False
                    
                if auth_result.get("error"):
                    logger.error(f"❌ Authentication error: {auth_result['error']}")
                    logger.error("Market stream service cannot continue - exiting")
                    return False
            
            if not self.iifl_service.session_token:
                logger.error("❌ No session token received - authentication failed")
                return False
                
            if self.iifl_service.session_token.startswith("mock_"):
                logger.warning("⚠️ Using mock token - market stream will not connect to real bridge")
                return False
            
            logger.info("IIFL authentication successful")
            
            # Create database session and services
            async with AsyncSessionLocal() as session:
                watchlist_service = WatchlistService(session)
                screener_service = ScreenerService(watchlist_service)
                
                # Create market stream service
                self.market_stream = MarketStreamService(self.iifl_service, screener_service)
                
                # Connect to market stream
                logger.info("Connecting to IIFL market stream...")
                await self.market_stream.connect_and_subscribe()
                
                if self.market_stream.is_connected:
                    self.running = True
                    logger.info("📈 Market Stream Service started successfully!")
                    logger.info("Listening for 52-week high events...")
                    return True
                else:
                    logger.error("Failed to connect to market stream")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to start market stream service: {e}")
            return False
    
    async def stop(self):
        """Stop the market stream service"""
        try:
            if self.market_stream and self.running:
                logger.info("Stopping Market Stream Service...")
                await self.market_stream.disconnect()
                self.running = False
                logger.info("Market Stream Service stopped")
                
            if self.iifl_service:
                await self.iifl_service.close_http_client()
                
        except Exception as e:
            logger.error(f"Error stopping market stream service: {e}")
    
    async def run_forever(self):
        """Run the service until interrupted"""
        if not await self.start():
            logger.error("🛑 Market stream service failed to start - exiting")
            sys.exit(1)
        
        try:
            # Keep running and monitoring connection
            while self.running:
                await asyncio.sleep(5)
                
                # Check if still connected
                if self.market_stream and not self.market_stream.is_connected:
                    logger.warning("Market stream connection lost - attempting reconnect...")
                    try:
                        await self.market_stream.connect_and_subscribe()
                        if self.market_stream.is_connected:
                            logger.info("Market stream reconnected successfully")
                        else:
                            logger.error("Failed to reconnect to market stream")
                    except Exception as e:
                        logger.error(f"Reconnection failed: {e}")
                
        except (KeyboardInterrupt, SystemExit):
            logger.info("Received shutdown signal")
        finally:
            await self.stop()

def setup_signal_handlers(service):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        service.running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main():
    """Main entry point"""
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    logger.info("Initializing External Market Stream Service...")
    
    service = ExternalMarketStreamService()
    setup_signal_handlers(service)
    
    try:
        await service.run_forever()
    except Exception as e:
        logger.error(f"Service error: {e}")
        await service.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)