#!/usr/bin/env python3
"""
Startup script for the Automated Stock Trading System
"""

import asyncio
import uvicorn
import logging
from pathlib import Path
import sys
import os


# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.settings import get_settings
from models.database import init_db
from services.logging_service import trading_logger

async def startup_checks():
    """Perform startup checks and initialization"""
    try:
        # Initialize logging
        trading_logger.log_system_event("System startup initiated")
        
        # Load settings
        settings = get_settings()
        
        # Check required environment variables
        required_vars = [
            ("IIFL_CLIENT_ID", "iifl_client_id"), 
            ("IIFL_AUTH_CODE", "iifl_auth_code"), 
            ("IIFL_APP_SECRET", "iifl_app_secret"),
            ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"), 
            ("TELEGRAM_CHAT_ID", "telegram_chat_id")
        ]
        
        missing_vars = []
        for env_var, attr_name in required_vars:
            if not getattr(settings, attr_name, None):
                missing_vars.append(env_var)
        
        if missing_vars:
            trading_logger.error_logger.error(
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
            print(f"[ERROR] Missing environment variables: {', '.join(missing_vars)}")
            print("Please check your .env file and ensure all required variables are set.")
            return False
        
        # Initialize database
        print("[INFO] Initializing database...")
        await init_db()
        trading_logger.log_system_event("Database initialized successfully")
        
        # Create required directories
        dirs_to_create = ["logs", "reports", "data"]
        for dir_name in dirs_to_create:
            Path(dir_name).mkdir(exist_ok=True)
        
        print("[SUCCESS] Startup checks completed successfully")
        trading_logger.log_system_event("All startup checks passed")
        return True
        
    except Exception as e:
        trading_logger.log_error("startup", e)
        print(f"[ERROR] Startup failed: {str(e)}")
        return False

def main():
    """Main entry point"""
    print("Starting Automated Stock Trading System...")
    print("=" * 50)
    
    # Run startup checks
    startup_success = asyncio.run(startup_checks())
    
    if not startup_success:
        print("[ERROR] Startup checks failed. Please fix the issues and try again.")
        sys.exit(1)
    
    # Load settings for server configuration
    settings = get_settings()
    
    print(f"[INFO] Starting web server on http://localhost:{settings.port}")
    print(f"[INFO] Dashboard available at: http://localhost:{settings.port}/dashboard")
    print(f"[INFO] API documentation at: http://localhost:{settings.port}/docs")
    print("=" * 50)
    
    # Start the FastAPI server
    # Use subprocess to run uvicorn. This is the recommended way to handle
    # programmatic startup with reloading, as it avoids issues where the
    # reloader process and the worker process both try to bind to the same port.
    import subprocess
    
    is_debug = settings.environment.lower() == "development"
    log_level = "debug" if is_debug else "info"
    
    command = [
        sys.executable, "-m", "uvicorn", "main:app",
        "--host", str(settings.host),
        "--port", str(settings.port),
        "--log-level", log_level,
    ]
    if is_debug:
        command.append("--reload")
    
    subprocess.run(command)

if __name__ == "__main__":
    main()
