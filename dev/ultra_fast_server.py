#!/usr/bin/env python3
"""
Ultra-fast development server with instant startup
No complex configuration loading, just the essentials
"""
import os
import sys
import time
import uvicorn
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_minimal_environment():
    """Set up minimal environment for development"""
    print("⚡ Setting up minimal environment...")
    
    # Essential environment variables
    env_vars = {
        'HOST': '0.0.0.0',
        'PORT': '8000',
        'DEBUG': 'true',
        'DRY_RUN': 'true',
        'AUTO_TRADE': 'false',
        'LOG_LEVEL': 'INFO',
        'LOG_CONSOLE_ENABLED': 'true',
        'LOG_FILE_ENABLED': 'false',
        'ENABLE_SCHEDULER': 'false',
        'TELEGRAM_BOT_ENABLED': 'false',
        'SECRET_KEY': 'dev_secret_key_for_development_only',
        'API_SECRET_KEY': 'dev_api_secret_key_for_development_only',
        'JWT_SECRET_KEY': 'dev_jwt_secret_key_for_development_only',
        'DATABASE_URL': 'sqlite+aiosqlite:///./trading_system.db',
        'IIFL_CLIENT_ID': os.getenv('IIFL_CLIENT_ID', ''),
        'IIFL_AUTH_CODE': os.getenv('IIFL_AUTH_CODE', ''),
        'IIFL_APP_SECRET': os.getenv('IIFL_APP_SECRET', ''),
    }
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ.setdefault(key, value)
    
    print(f"✅ Environment setup complete")

def create_app():
    """Create FastAPI app"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    
    app = FastAPI(
        title="Lightning Trading System",
        description="Ultra-fast development server",
        version="lightning-1.0"
    )
    
    # Simple CORS
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
            "message": "⚡ Lightning Trading System",
            "status": "running",
            "mode": "ultra-fast-development",
            "startup": "instant"
        }
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "server": "lightning"}
    
    @app.get("/config")
    async def config():
        return {
            "host": os.getenv('HOST'),
            "port": int(os.getenv('PORT')),
            "debug": os.getenv('DEBUG') == 'true',
            "dry_run": os.getenv('DRY_RUN') == 'true',
            "auto_trade": os.getenv('AUTO_TRADE') == 'true',
            "log_level": os.getenv('LOG_LEVEL'),
            "scheduler": os.getenv('ENABLE_SCHEDULER') == 'true'
        }
    
    return app

def main():
    """Main function"""
    print("🚀 Lightning Development Server")
    print("=" * 50)
    
    start_time = time.time()
    
    # Setup environment
    setup_minimal_environment()
    env_time = time.time()
    
    # Create app
    app = create_app()
    app_time = time.time()
    
    total_time = app_time - start_time
    print(f"⚡ Total startup time: {total_time:.3f}s")
    
    # Get configuration
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '8000'))
    
    print(f"🌟 Server starting at http://{host}:{port}")
    print("🔧 Features: Minimal config, instant startup")
    print("💡 Use Ctrl+C to stop")
    print("=" * 50)
    
    # Start server
    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            reload=False,
            access_log=False
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

if __name__ == "__main__":
    main()