"""
Fast Development Server
Optimized startup for development with minimal overhead.
"""

import os
import sys
import asyncio
import logging
import uvicorn
from pathlib import Path

# Ensure project directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure minimal logging for fast startup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set environment for fast development mode
os.environ.setdefault('ENVIRONMENT', 'development')
os.environ.setdefault('DEBUG', 'true')
os.environ.setdefault('RELOAD', 'false')  # Disable reload for fastest startup

# Disable heavy components for development
os.environ.setdefault('ENABLE_SCHEDULER', 'false')
os.environ.setdefault('TELEGRAM_BOT_ENABLED', 'false')
os.environ.setdefault('ENABLE_SYSTEM_STATUS_CHECKS', 'false')
os.environ.setdefault('TELEGRAM_BACKGROUND_TASKS_ENABLED', 'false')

# Optimize logging for development
os.environ.setdefault('LOG_LEVEL', 'WARNING')
os.environ.setdefault('LOG_LEVEL_SCHEDULER', 'ERROR')
os.environ.setdefault('LOG_LEVEL_DATABASE', 'ERROR')
os.environ.setdefault('LOG_LEVEL_MARKET_DATA', 'ERROR')
os.environ.setdefault('LOG_LEVEL_BACKTEST', 'ERROR')
os.environ.setdefault('LOG_LEVEL_TELEGRAM', 'ERROR')
os.environ.setdefault('LOG_LEVEL_API', 'ERROR')

def main():
    """Fast development server startup"""
    
    print("🚀 FAST DEVELOPMENT SERVER")
    print("=" * 40)
    print("⚡ Optimized for fastest startup")
    print("🔧 Development mode enabled")
    print("📊 Heavy components disabled")
    print("=" * 40)
    
    # Ensure required directories exist
    Path("logs").mkdir(exist_ok=True)
    
    try:
        from config.settings import get_settings
        settings = get_settings()
        
        logger.info(f"🌐 Starting server on {settings.host}:{settings.port}")
        logger.info("⚡ Fast mode: scheduler, telegram bot, and heavy logging disabled")
        
        # Start uvicorn with optimized settings
        uvicorn.run(
            "main:app",
            host=settings.host,
            port=settings.port,
            log_level="warning",  # Minimal logging
            access_log=False,     # Disable access logging for speed
            reload=False,         # Disable auto-reload
            workers=1,            # Single worker
            loop="asyncio",
            http="httptools",
            interface="asgi3"
        )
        
    except KeyboardInterrupt:
        logger.info("🛑 Server stopped by user")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Server startup failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)