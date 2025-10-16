"""
Production Startup Script for Algorithmic Trading System

This script starts the trading system in production mode with proper
monitoring, health checks, and error handling.
"""

import asyncio
import logging
import os
import sys
import signal
import time
from pathlib import Path
import uvicorn
from contextlib import asynccontextmanager

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging for startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/startup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ProductionServer:
    """Production server manager for the trading system."""
    
    def __init__(self):
        self.server = None
        self.should_exit = False
        
        # Ensure required directories exist
        Path("logs").mkdir(exist_ok=True)
        Path("backups").mkdir(exist_ok=True)
        Path("reports").mkdir(exist_ok=True)
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
            self.should_exit = True
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def health_check_startup(self):
        """Perform startup health checks."""
        logger.info("🔍 Performing startup health checks...")
        
        try:
            # Check configuration
            from config.settings import get_settings
            settings = get_settings()
            
            logger.info(f"✅ Environment: {settings.environment}")
            logger.info(f"✅ Database: {settings.database_url}")
            logger.info(f"✅ Log Level: {settings.log_level}")
            
            # Check database connectivity
            import sqlite3
            conn = sqlite3.connect("trading_system.db")
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            conn.close()
            logger.info("✅ Database connectivity verified")
            
            # Check required environment variables
            required_vars = ['IIFL_CLIENT_ID', 'IIFL_AUTH_CODE', 'IIFL_APP_SECRET']
            missing_vars = []
            
            for var in required_vars:
                if not getattr(settings, var.lower(), None):
                    missing_vars.append(var)
            
            if missing_vars:
                logger.warning(f"⚠️ Missing environment variables: {missing_vars}")
            
            logger.info("✅ Startup health checks completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Startup health check failed: {str(e)}")
            return False
    
    async def initialize_services(self):
        """Initialize trading system services."""
        logger.info("🚀 Initializing trading system services...")
        
        try:
            # Initialize database
            from models.database import init_db
            await init_db()
            logger.info("✅ Database initialized")
            
            # Initialize logging service
            from services.logging_service import TradingLogger
            trading_logger = TradingLogger()
            logger.info("✅ Logging service initialized")
            
            # Initialize scheduler if enabled
            from config.settings import get_settings
            settings = get_settings()
            
            if getattr(settings, 'enable_scheduler', False):
                logger.info("📅 Scheduler is enabled in configuration")
                # Note: Scheduler will be started by the FastAPI app
            
            logger.info("✅ All services initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Service initialization failed: {str(e)}")
            return False
    
    async def start_server(self):
        """Start the FastAPI server in production mode."""
        logger.info("🌐 Starting production server...")
        
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            # Production server configuration
            config = uvicorn.Config(
                "main:app",
                host=getattr(settings, 'host', '0.0.0.0'),
                port=getattr(settings, 'port', 8000),
                log_level=getattr(settings, 'log_level', 'info').lower(),
                access_log=True,
                reload=False,  # Never reload in production
                workers=1,     # Single worker for trading system
                loop="asyncio",
                http="httptools"
            )
            
            self.server = uvicorn.Server(config)
            
            logger.info(f"🚀 Starting server on {config.host}:{config.port}")
            await self.server.serve()
            
        except Exception as e:
            logger.error(f"❌ Server startup failed: {str(e)}")
            raise
    
    async def run_production(self):
        """Run the complete production startup sequence."""
        logger.info("🏭 Starting Algorithmic Trading System in Production Mode")
        logger.info("="*60)
        
        # Setup signal handlers
        self.setup_signal_handlers()
        
        # Run startup health checks
        if not await self.health_check_startup():
            logger.error("❌ Startup health checks failed, aborting startup")
            return False
        
        # Initialize services
        if not await self.initialize_services():
            logger.error("❌ Service initialization failed, aborting startup")
            return False
        
        # Start server
        try:
            await self.start_server()
            logger.info("✅ Production server started successfully")
            return True
            
        except KeyboardInterrupt:
            logger.info("🛑 Keyboard interrupt received")
            return True
            
        except Exception as e:
            logger.error(f"❌ Production server error: {str(e)}")
            return False
    
    async def shutdown(self):
        """Graceful shutdown of all services."""
        logger.info("🛑 Initiating graceful shutdown...")
        
        if self.server:
            logger.info("🔌 Shutting down server...")
            self.server.should_exit = True
        
        # Give time for cleanup
        await asyncio.sleep(2)
        logger.info("✅ Shutdown completed")

def main():
    """Main entry point for production server."""
    server = ProductionServer()
    
    try:
        # Create and run the event loop
        if sys.platform.startswith('win'):
            # Windows-specific event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoop())
        
        # Run the production server
        success = asyncio.run(server.run_production())
        
        if success:
            logger.info("🎉 Production server completed successfully")
            return 0
        else:
            logger.error("❌ Production server failed")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Production server interrupted by user")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in production server: {str(e)}")
        return 1
    
    finally:
        # Cleanup
        try:
            asyncio.run(server.shutdown())
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {str(e)}")

if __name__ == "__main__":
    # Ensure we're running in production mode
    os.environ.setdefault('ENVIRONMENT', 'production')
    
    # Print startup banner
    print("🏭 ALGORITHMIC TRADING SYSTEM - PRODUCTION MODE")
    print("="*50)
    print(f"📅 Startup Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🐍 Python Version: {sys.version}")
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"🌐 Environment: {os.environ.get('ENVIRONMENT', 'production')}")
    print("="*50)
    
    # Run main function and exit with appropriate code
    exit_code = main()
    sys.exit(exit_code)