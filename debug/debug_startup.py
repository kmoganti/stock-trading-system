"""
Startup Diagnostic Script
Identifies specific issues preventing the app from starting.
"""

import sys
import os
import traceback
import logging
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - DIAGNOSTIC - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test all critical imports step by step"""
    logger.info("🧪 Testing imports...")
    
    tests = [
        ("Standard library imports", lambda: [__import__(m) for m in ['asyncio', 'json', 'logging', 'os', 'time']]),
        ("FastAPI", lambda: __import__('fastapi')),
        ("Uvicorn", lambda: __import__('uvicorn')),
        ("Pydantic", lambda: __import__('pydantic')),
        ("SQLAlchemy", lambda: __import__('sqlalchemy')),
        ("APScheduler", lambda: __import__('apscheduler')),
        ("Config settings", lambda: __import__('config.settings')),
        ("Database models", lambda: __import__('models.database')),
        ("Logging service", lambda: __import__('services.logging_service')),
        ("Main app module", lambda: __import__('main')),
    ]
    
    failed = []
    for name, test_func in tests:
        try:
            test_func()
            logger.info(f"✅ {name}")
        except Exception as e:
            logger.error(f"❌ {name}: {str(e)}")
            failed.append((name, str(e)))
    
    return failed

def test_environment():
    """Test environment configuration"""
    logger.info("🌍 Testing environment...")
    
    # Check .env file
    env_file = Path(".env")
    if not env_file.exists():
        logger.warning("⚠️ No .env file found")
        return ["No .env file"]
    
    logger.info(f"✅ .env file exists ({env_file.stat().st_size} bytes)")
    
    # Test settings loading
    try:
        from config.settings import get_settings
        settings = get_settings()
        logger.info(f"✅ Settings loaded: environment={getattr(settings, 'environment', 'unknown')}")
        
        # Check critical settings
        critical_settings = ['host', 'port', 'database_url']
        missing = []
        for setting in critical_settings:
            if not hasattr(settings, setting) or not getattr(settings, setting):
                missing.append(setting)
        
        if missing:
            logger.error(f"❌ Missing critical settings: {missing}")
            return missing
        else:
            logger.info("✅ All critical settings present")
            return []
            
    except Exception as e:
        logger.error(f"❌ Settings loading failed: {str(e)}")
        return [f"Settings error: {str(e)}"]

def test_database():
    """Test database connectivity"""
    logger.info("🗄️ Testing database...")
    
    try:
        import sqlite3
        
        # Test basic sqlite connection
        conn = sqlite3.connect("trading_system.db", timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0] == 1:
            logger.info("✅ SQLite database accessible")
            return []
        else:
            logger.error("❌ Database query failed")
            return ["Database query failed"]
            
    except Exception as e:
        logger.error(f"❌ Database connection failed: {str(e)}")
        return [f"Database error: {str(e)}"]

def test_minimal_fastapi():
    """Test minimal FastAPI app creation"""
    logger.info("🚀 Testing minimal FastAPI app...")
    
    try:
        from fastapi import FastAPI
        
        # Create minimal app
        app = FastAPI(title="Test App")
        
        @app.get("/")
        def root():
            return {"status": "ok"}
        
        logger.info("✅ Minimal FastAPI app created successfully")
        return []
        
    except Exception as e:
        logger.error(f"❌ FastAPI app creation failed: {str(e)}")
        return [f"FastAPI error: {str(e)}"]

def test_main_app_import():
    """Test importing the main app module"""
    logger.info("📦 Testing main app import...")
    
    try:
        # Try to import main module
        import main
        logger.info("✅ Main module imported")
        
        # Try to access the app
        if hasattr(main, 'app'):
            logger.info("✅ FastAPI app object found")
            return []
        else:
            logger.error("❌ FastAPI app object not found in main module")
            return ["App object missing"]
            
    except Exception as e:
        logger.error(f"❌ Main app import failed: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return [f"Main import error: {str(e)}"]

def main():
    """Run all diagnostic tests"""
    logger.info("🔍 STARTUP DIAGNOSTIC SUITE")
    logger.info("=" * 50)
    
    all_issues = []
    
    # Run all tests
    issues = test_imports()
    all_issues.extend(issues)
    
    if not issues:  # Only continue if imports work
        all_issues.extend(test_environment())
        all_issues.extend(test_database())
        all_issues.extend(test_minimal_fastapi())
        all_issues.extend(test_main_app_import())
    
    # Summary
    logger.info("=" * 50)
    if all_issues:
        logger.error(f"❌ Found {len(all_issues)} issues:")
        for i, issue in enumerate(all_issues, 1):
            logger.error(f"   {i}. {issue}")
        logger.info("\n💡 RECOMMENDED ACTIONS:")
        logger.info("1. Fix import errors first")
        logger.info("2. Check .env file configuration") 
        logger.info("3. Verify database accessibility")
        logger.info("4. Test with minimal FastAPI server")
        return 1
    else:
        logger.info("✅ All diagnostic tests passed!")
        logger.info("🚀 App should be able to start successfully")
        return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)