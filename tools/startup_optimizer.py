"""
Production Startup Optimizer

This script provides multiple startup modes optimized for different scenarios:
1. Fast Development Mode - Minimal components, fastest startup
2. Standard Mode - All components, optimized settings
3. Production Mode - Full production setup with monitoring

Usage:
  python startup_optimizer.py --mode fast        # Fastest startup (~2-3 seconds)
  python startup_optimizer.py --mode standard    # Standard startup (~5-8 seconds)  
  python startup_optimizer.py --mode production  # Full production startup (~10-15 seconds)
"""

import os
import sys
import argparse
import asyncio
import logging
import time
from pathlib import Path

def setup_fast_mode():
    """Configure environment for fastest possible startup"""
    print("⚡ Configuring FAST MODE - Development Only")
    
    # Core settings
    os.environ.update({
        'ENVIRONMENT': 'development',
        'DEBUG': 'true',
        'RELOAD': 'false',
        
        # Disable all heavy components
        'ENABLE_SCHEDULER': 'false',
        'SCHEDULER_ENABLED': 'false',
        'TELEGRAM_BOT_ENABLED': 'false',
        'ENABLE_SYSTEM_STATUS_CHECKS': 'false',
        'TELEGRAM_BACKGROUND_TASKS_ENABLED': 'false',
        'ENABLE_PRE_MARKET_ANALYSIS': 'false',
        'ENABLE_POST_MARKET_ANALYSIS': 'false',
        
        # Minimal logging
        'LOG_LEVEL': 'ERROR',
        'LOG_LEVEL_SCHEDULER': 'CRITICAL',
        'LOG_LEVEL_DATABASE': 'CRITICAL', 
        'LOG_LEVEL_MARKET_DATA': 'CRITICAL',
        'LOG_LEVEL_BACKTEST': 'CRITICAL',
        'LOG_LEVEL_TELEGRAM': 'CRITICAL',
        'LOG_LEVEL_API': 'CRITICAL',
        'LOG_LEVEL_TRADING': 'ERROR',
        'LOG_CONSOLE_ENABLED': 'false',
        'LOG_FILE_ENABLED': 'false',
        
        # Optimize performance settings
        'PERFORMANCE_MONITORING_ENABLED': 'false',
        'METRICS_COLLECTION_ENABLED': 'false',
        'BACKUP_ENABLED': 'false',
        'EMAIL_ENABLED': 'false',
        
        # Disable Sentry for development
        'SENTRY_DSN': '',
        'SENTRY_TRACES_SAMPLE_RATE': '0.0'
    })

def setup_standard_mode():
    """Configure environment for standard startup with key optimizations"""
    print("🔧 Configuring STANDARD MODE - Balanced Performance")
    
    os.environ.update({
        'ENVIRONMENT': 'development',
        'DEBUG': 'false',
        'RELOAD': 'false',
        
        # Enable core components only
        'ENABLE_SCHEDULER': 'true',
        'SCHEDULER_ENABLED': 'true', 
        'TELEGRAM_BOT_ENABLED': 'false',  # Keep disabled unless needed
        'ENABLE_SYSTEM_STATUS_CHECKS': 'true',
        
        # Optimized logging
        'LOG_LEVEL': 'INFO',
        'LOG_LEVEL_SCHEDULER': 'WARNING',
        'LOG_LEVEL_DATABASE': 'WARNING',
        'LOG_LEVEL_MARKET_DATA': 'WARNING',
        'LOG_CONSOLE_ENABLED': 'true',
        'LOG_FILE_ENABLED': 'true',
        
        # Moderate performance monitoring
        'PERFORMANCE_MONITORING_ENABLED': 'true',
        'METRICS_COLLECTION_ENABLED': 'false',  # Disable for faster startup
        'BACKUP_ENABLED': 'true',
    })

def setup_production_mode():
    """Configure environment for full production startup"""
    print("🏭 Configuring PRODUCTION MODE - Full Features")
    
    os.environ.update({
        'ENVIRONMENT': 'production',
        'DEBUG': 'false',
        'RELOAD': 'false',
        
        # Enable all production components
        'ENABLE_SCHEDULER': 'true',
        'SCHEDULER_ENABLED': 'true',
        'TELEGRAM_BOT_ENABLED': 'true',
        'ENABLE_SYSTEM_STATUS_CHECKS': 'true',
        'TELEGRAM_BACKGROUND_TASKS_ENABLED': 'true',
        
        # Full logging
        'LOG_LEVEL': 'INFO',
        'LOG_CONSOLE_ENABLED': 'true',
        'LOG_FILE_ENABLED': 'true',
        
        # Full monitoring
        'PERFORMANCE_MONITORING_ENABLED': 'true',
        'METRICS_COLLECTION_ENABLED': 'true',
        'BACKUP_ENABLED': 'true',
        'EMAIL_ENABLED': 'true',
    })

def start_server(mode: str):
    """Start the server with the specified mode"""
    
    # Ensure required directories
    Path("logs").mkdir(exist_ok=True)
    Path("backups").mkdir(exist_ok=True)
    
    try:
        import uvicorn
        from config.settings import get_settings
        
        settings = get_settings()
        
        # Configure uvicorn based on mode
        config = {
            "host": getattr(settings, 'host', '0.0.0.0'),
            "port": getattr(settings, 'port', 8000),
            "workers": 1,
            "loop": "asyncio",
            "http": "httptools",
            "interface": "asgi3",
        }
        
        if mode == "fast":
            config.update({
                "log_level": "critical",
                "access_log": False,
                "reload": False,
            })
            print(f"🚀 Starting FAST server on {config['host']}:{config['port']}")
            print("   ⚡ Heavy components disabled for speed")
            
        elif mode == "standard":
            config.update({
                "log_level": "warning", 
                "access_log": False,
                "reload": False,
            })
            print(f"🚀 Starting STANDARD server on {config['host']}:{config['port']}")
            print("   🔧 Core components enabled")
            
        else:  # production
            config.update({
                "log_level": "info",
                "access_log": True,
                "reload": False,
            })
            print(f"🚀 Starting PRODUCTION server on {config['host']}:{config['port']}")
            print("   🏭 All components enabled")
        
        # Start server
        uvicorn.run("main:app", **config)
        
    except KeyboardInterrupt:
        print("🛑 Server stopped by user")
        return 0
    except Exception as e:
        print(f"❌ Server startup failed: {str(e)}")
        return 1

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Trading System Startup Optimizer")
    parser.add_argument(
        "--mode", 
        choices=["fast", "standard", "production"],
        default="standard",
        help="Startup mode: fast (dev only), standard (balanced), production (full)"
    )
    
    args = parser.parse_args()
    
    print("🚀 TRADING SYSTEM STARTUP OPTIMIZER")
    print("=" * 50)
    
    start_time = time.perf_counter()
    
    # Configure environment based on mode
    if args.mode == "fast":
        setup_fast_mode()
    elif args.mode == "standard":
        setup_standard_mode()
    else:
        setup_production_mode()
    
    print(f"📅 Mode: {args.mode.upper()}")
    print(f"🕐 Starting at: {time.strftime('%H:%M:%S')}")
    print("=" * 50)
    
    # Start server
    exit_code = start_server(args.mode)
    
    duration = time.perf_counter() - start_time
    print(f"\n⏱️ Total runtime: {duration:.1f} seconds")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())