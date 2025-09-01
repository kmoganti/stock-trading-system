#!/usr/bin/env python3
"""
System validation script for the Automated Stock Trading System
"""

import sys
import asyncio
from pathlib import Path

def test_imports():
    """Test if all core modules can be imported"""
    print("[INFO] Testing imports...")
    
    try:
        import fastapi
        print("[SUCCESS] FastAPI imported")
    except ImportError as e:
        print(f"[ERROR] FastAPI import failed: {e}")
        return False
    
    try:
        import uvicorn
        print("[SUCCESS] Uvicorn imported")
    except ImportError as e:
        print(f"[ERROR] Uvicorn import failed: {e}")
        return False
    
    try:
        import sqlalchemy
        print("[SUCCESS] SQLAlchemy imported")
    except ImportError as e:
        print(f"[ERROR] SQLAlchemy import failed: {e}")
        return False
    
    try:
        import aiosqlite
        print("[SUCCESS] aiosqlite imported")
    except ImportError as e:
        print(f"[ERROR] aiosqlite import failed: {e}")
        return False
    
    try:
        import httpx
        print("[SUCCESS] httpx imported")
    except ImportError as e:
        print(f"[ERROR] httpx import failed: {e}")
        return False
    
    return True

def test_project_structure():
    """Test if project structure is correct"""
    print("\n[INFO] Testing project structure...")
    
    required_dirs = ["logs", "reports", "data", "models", "services", "api", "templates"]
    missing_dirs = []
    
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            missing_dirs.append(dir_name)
        else:
            print(f"[SUCCESS] Directory exists: {dir_name}")
    
    if missing_dirs:
        print(f"[WARNING] Missing directories: {', '.join(missing_dirs)}")
        return False
    
    return True

def test_config_files():
    """Test if configuration files exist"""
    print("\n[INFO] Testing configuration files...")
    
    config_files = [".env", "requirements.txt"]
    missing_files = []
    
    for file_name in config_files:
        if not Path(file_name).exists():
            missing_files.append(file_name)
        else:
            print(f"[SUCCESS] File exists: {file_name}")
    
    if missing_files:
        print(f"[WARNING] Missing files: {', '.join(missing_files)}")
        return len(missing_files) == 0
    
    return True

async def test_database():
    """Test database connectivity"""
    print("\n[INFO] Testing database...")
    
    try:
        # Add project root to path
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from models.database import init_db, get_db
        
        # Initialize database
        await init_db()
        print("[SUCCESS] Database initialized")
        
        # Test connection
        async for db in get_db():
            print("[SUCCESS] Database connection successful")
            break
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Database test failed: {e}")
        return False

def test_basic_app():
    """Test if the FastAPI app can be created"""
    print("\n[INFO] Testing FastAPI app creation...")
    
    try:
        # Add project root to path
        project_root = Path(__file__).parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        from main import app
        print("[SUCCESS] FastAPI app created successfully")
        return True
        
    except Exception as e:
        print(f"[ERROR] FastAPI app creation failed: {e}")
        return False

async def main():
    """Main validation function"""
    print("Validating Automated Stock Trading System")
    print("=" * 50)
    
    tests = [
        ("Import Tests", test_imports),
        ("Project Structure", test_project_structure),
        ("Configuration Files", test_config_files),
        ("Database", test_database),
        ("FastAPI App", test_basic_app)
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            if result:
                passed += 1
                print(f"[SUCCESS] {test_name} passed")
            else:
                failed += 1
                print(f"[FAILED] {test_name} failed")
                
        except Exception as e:
            failed += 1
            print(f"[ERROR] {test_name} error: {e}")
    
    print("\n" + "=" * 50)
    print(f"Validation Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("[SUCCESS] All tests passed! System is ready to run.")
        print("\nTo start the system:")
        print("python run.py")
    else:
        print("[WARNING] Some tests failed. Please check the issues above.")
        print("\nCommon solutions:")
        print("- Install missing dependencies: pip install -r requirements-basic.txt")
        print("- Check .env file configuration")
        print("- Ensure all directories exist")

if __name__ == "__main__":
    asyncio.run(main())
