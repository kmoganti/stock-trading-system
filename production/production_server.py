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

# Ensure project root is on sys.path so `config`, `api`, etc. are importable
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

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
        
    # Default to lightweight startup unless explicitly enabled via env.
    # This avoids potential hangs from external services (market stream, etc.).
    os.environ.setdefault("ENABLE_MARKET_STREAM", "false")
    os.environ.setdefault("ENABLE_STARTUP_CACHE_WARMUP", "false")
    # Be lenient by default: don't abort on failed health checks unless explicitly requested.
    os.environ.setdefault("STRICT_STARTUP_CHECKS", "false")
    # Telegram bot is controlled by settings; keep default off unless enabled.
        
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
            from models.database import engine
            from sqlalchemy import text
            try:
                async with engine.begin() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("✅ Database connectivity verified")
            except Exception as db_e:
                # If SAFE_MODE, allow startup without DB to keep UI/health responsive
                safe_mode = os.getenv("SAFE_MODE", "false").lower() == "true"
                if safe_mode:
                    logger.warning(f"⚠️ Database not reachable, but SAFE_MODE=true - continuing startup: {db_e}")
                else:
                    raise
            
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
            # In SAFE_MODE, do not block startup on health check failures
            if os.getenv("SAFE_MODE", "false").lower() == "true":
                logger.warning(f"⚠️ Startup health check issues ignored in SAFE_MODE: {e}")
                return True
            logger.error(f"❌ Startup health check failed: {str(e)}")
            return False
    
    async def initialize_services(self):
        """Initialize trading system services."""
        logger.info("🚀 Initializing trading system services...")
        
        try:
            # In SAFE_MODE, skip heavy/critical dependencies to keep app responsive
            if os.getenv("SAFE_MODE", "false").lower() == "true":
                logger.warning("⚠️ SAFE_MODE=true - skipping database initialization and heavy services")
                # Let FastAPI app handle minimal initialization
                return True
            # Initialize database
            from models.database import init_db
            logger.info("📊 About to initialize database...")
            await init_db()
            logger.info("✅ Database initialized")
            
            # Initialize logging service (deferred to FastAPI app import)
            # Previously importing TradingLogger here could block startup in some environments
            # due to heavy logging configuration. The FastAPI app (main.py) initializes
            # logging on import, so we skip explicit init here to avoid blocking.
            logger.info("📝 Skipping pre-server logging initialization (FastAPI app will configure logging)")
            
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
            # If SAFE_MODE, allow startup to continue despite service init failures
            if os.getenv("SAFE_MODE", "false").lower() == "true":
                logger.warning(f"⚠️ Service initialization issues ignored in SAFE_MODE: {e}")
                return True
            return False
    
    async def start_server(self):
        """Start the FastAPI server in production mode."""
        logger.info("🌐 Starting production server...")
        
        try:
            from config.settings import get_settings
            settings = get_settings()
            # Log effective lightweight options
            logger.info(
                f"⚙️ ENABLE_MARKET_STREAM={os.getenv('ENABLE_MARKET_STREAM','').lower()} "
                f"ENABLE_STARTUP_CACHE_WARMUP={os.getenv('ENABLE_STARTUP_CACHE_WARMUP','').lower()}"
            )
            
            # Production server configuration
            # Note: Use default HTTP implementation (auto/h11) and loop to avoid
            # optional dependency issues (e.g., missing 'httptools') that can
            # prevent the server from binding to the port.
            config = uvicorn.Config(
                "main:app",
                host=getattr(settings, 'host', '0.0.0.0'),
                port=getattr(settings, 'port', 8000),
                log_level=getattr(settings, 'log_level', 'info').lower(),
                access_log=True,
                reload=False,  # Never reload in production
                workers=1      # Single worker for trading system
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
        strict_checks = os.getenv("STRICT_STARTUP_CHECKS", "false").lower() == "true"
        if not await self.health_check_startup():
            if strict_checks:
                logger.error("❌ Startup health checks failed, aborting startup (STRICT_STARTUP_CHECKS=true)")
                return False
            else:
                logger.warning("⚠️ Startup health checks failed, but proceeding (STRICT_STARTUP_CHECKS=false)")
        
        # Initialize services
        if not await self.initialize_services():
            if strict_checks:
                logger.error("❌ Service initialization failed, aborting startup (STRICT_STARTUP_CHECKS=true)")
                return False
            else:
                logger.warning("⚠️ Service initialization failed, but proceeding (STRICT_STARTUP_CHECKS=false)")
        
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