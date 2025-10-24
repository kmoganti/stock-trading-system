#!/usr/bin/env python3
"""
Lightning-fast development server with minimal configuration loading
Optimized for rapid development cycles with instant startup
"""
import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def load_minimal_env():
    """Load minimal environment variables for fast startup"""
    env_file = project_root / '.env.minimal'
    
    if env_file.exists():
        print(f"⚡ Loading minimal config from {env_file}")
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    else:
        print(f"⚠️  Minimal config not found, using defaults")
        # Set essential defaults
        os.environ.setdefault('HOST', '0.0.0.0')
        os.environ.setdefault('PORT', '8000')
        os.environ.setdefault('DEBUG', 'true')
        os.environ.setdefault('DRY_RUN', 'true')
        os.environ.setdefault('AUTO_TRADE', 'false')
        os.environ.setdefault('LOG_LEVEL', 'INFO')
        os.environ.setdefault('ENABLE_SCHEDULER', 'false')

def create_minimal_settings():
    """Create a minimal settings object for development"""
    from dataclasses import dataclass
    from typing import Optional
    
    @dataclass
    class MinimalSettings:
        # Server
        HOST: str = "0.0.0.0"
        PORT: int = 8000
        DEBUG: bool = True
        
        # Security (development only)
        SECRET_KEY: str = "dev_secret_key"
        API_SECRET_KEY: str = "dev_api_secret"
        JWT_SECRET_KEY: str = "dev_jwt_secret"
        
        # Trading
        DRY_RUN: bool = True
        AUTO_TRADE: bool = False
        
        # IIFL API
        IIFL_CLIENT_ID: str = ""
        IIFL_AUTH_CODE: str = ""
        IIFL_APP_SECRET: str = ""
        
        # Database
        DATABASE_URL: str = "sqlite+aiosqlite:///./trading_system.db"
        
        # Logging
        LOG_LEVEL: str = "INFO"
        LOG_CONSOLE_ENABLED: bool = True
        LOG_FILE_ENABLED: bool = False  # Disable for speed
        
        # Scheduler
        ENABLE_SCHEDULER: bool = False
        
        # Telegram
        TELEGRAM_BOT_ENABLED: bool = False
        TELEGRAM_NOTIFICATIONS_ENABLED: bool = False
        
        def __post_init__(self):
            # Load from environment if available
            self.HOST = os.getenv('HOST', self.HOST)
            self.PORT = int(os.getenv('PORT', self.PORT))
            self.DEBUG = os.getenv('DEBUG', str(self.DEBUG)).lower() == 'true'
            self.SECRET_KEY = os.getenv('SECRET_KEY', self.SECRET_KEY)
            self.API_SECRET_KEY = os.getenv('API_SECRET_KEY', self.API_SECRET_KEY)
            self.JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', self.JWT_SECRET_KEY)
            self.DRY_RUN = os.getenv('DRY_RUN', str(self.DRY_RUN)).lower() == 'true'
            self.AUTO_TRADE = os.getenv('AUTO_TRADE', str(self.AUTO_TRADE)).lower() == 'true'
            self.IIFL_CLIENT_ID = os.getenv('IIFL_CLIENT_ID', self.IIFL_CLIENT_ID)
            self.IIFL_AUTH_CODE = os.getenv('IIFL_AUTH_CODE', self.IIFL_AUTH_CODE)
            self.IIFL_APP_SECRET = os.getenv('IIFL_APP_SECRET', self.IIFL_APP_SECRET)
            self.DATABASE_URL = os.getenv('DATABASE_URL', self.DATABASE_URL)
            self.LOG_LEVEL = os.getenv('LOG_LEVEL', self.LOG_LEVEL)
            self.ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', str(self.ENABLE_SCHEDULER)).lower() == 'true'
    
    return MinimalSettings()

async def create_minimal_app():
    """Create a minimal FastAPI app for development"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import logging
    
    # Set up basic logging
    logging.basicConfig(
        level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    app = FastAPI(
        title="Trading System (Lightning Dev Mode)",
        description="Fast development server with minimal features",
        version="dev-fast"
    )
    
    # Basic CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return {
            "message": "Trading System Lightning Dev Server",
            "mode": "development",
            "startup_time": "⚡ instant",
            "features": "minimal for speed"
        }
    
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "mode": "lightning-dev",
            "timestamp": time.time()
        }
    
    @app.get("/settings")
    async def get_settings_info():
        settings = create_minimal_settings()
        return {
            "host": settings.HOST,
            "port": settings.PORT,
            "debug": settings.DEBUG,
            "dry_run": settings.DRY_RUN,
            "auto_trade": settings.AUTO_TRADE,
            "scheduler_enabled": settings.ENABLE_SCHEDULER,
            "telegram_enabled": settings.TELEGRAM_BOT_ENABLED
        }
    
    return app

async def main():
    """Main entry point"""
    print("🚀 Starting Lightning Development Server...")
    print("=" * 60)
    
    start_time = time.time()
    
    # Load minimal configuration
    load_minimal_env()
    setup_time = time.time()
    print(f"⚡ Configuration loaded in {setup_time - start_time:.3f}s")
    
    # Create settings
    settings = create_minimal_settings()
    settings_time = time.time()
    print(f"⚡ Settings created in {settings_time - setup_time:.3f}s")
    
    # Create app
    app = await create_minimal_app()
    app_time = time.time()
    print(f"⚡ App created in {app_time - settings_time:.3f}s")
    
    total_time = app_time - start_time
    print(f"🎯 Total startup time: {total_time:.3f}s")
    print("=" * 60)
    
    print(f"🌟 Server Configuration:")
    print(f"   Host: {settings.HOST}")
    print(f"   Port: {settings.PORT}")
    print(f"   Debug: {settings.DEBUG}")
    print(f"   Dry Run: {settings.DRY_RUN}")
    print(f"   Auto Trade: {settings.AUTO_TRADE}")
    print(f"   Scheduler: {settings.ENABLE_SCHEDULER}")
    print("=" * 60)
    
    # Start server
    try:
        import uvicorn
        print(f"🚀 Starting server at http://{settings.HOST}:{settings.PORT}")
        print("💡 Use Ctrl+C to stop")
        
        uvicorn.run(
            app,
            host=settings.HOST,
            port=settings.PORT,
            log_level="info" if settings.DEBUG else "warning",
            reload=False,  # Disable reload for speed
            access_log=False  # Disable access logs for speed
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Server error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())