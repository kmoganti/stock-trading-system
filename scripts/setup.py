#!/usr/bin/env python3
"""
Setup script for the Automated Stock Trading System
"""

import os
import sys
import subprocess
import asyncio
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"[INFO] {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"[SUCCESS] {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {description} failed: {e.stderr}")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["logs", "reports", "data"]
    
    for directory in directories:
        try:
            Path(directory).mkdir(exist_ok=True)
            print(f"[INFO] Created directory: {directory}")
        except Exception as e:
            print(f"[ERROR] Failed to create directory {directory}: {str(e)}")
            return False
    
    return True

def setup_environment():
    """Setup environment file"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        try:
            env_file.write_text(env_example.read_text())
            print("[INFO] Created .env file from .env.example")
            print("[WARNING] Please edit .env file with your actual credentials")
        except Exception as e:
            print(f"[ERROR] Failed to create .env file: {str(e)}")
            return False
    elif env_file.exists():
        print("[SUCCESS] .env file already exists")
    else:
        print("[WARNING] No .env.example file found")
        print("[INFO] You'll need to create a .env file manually")
    
    return True

def install_dependencies():
    """Install Python dependencies"""
    if Path("requirements.txt").exists():
        return run_command("pip install -r requirements.txt", "Installing dependencies")
    else:
        print("[ERROR] requirements.txt not found")
        return False

def initialize_database():
    """Initialize the database"""
    print("[INFO] Initializing database...")
    try:
        # Add project root to Python path
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Import after adding to path
        from models.database import init_db
        
        async def init():
            await init_db()
        
        asyncio.run(init())
        print("[SUCCESS] Database initialized")
        return True
    except ImportError as e:
        print(f"[WARNING] Could not import database modules: {str(e)}")
        print("[INFO] Database will be initialized on first run")
        return True  # Don't fail setup for this
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {str(e)}")
        print("[INFO] Database will be initialized on first run")
        return True  # Don't fail setup for this

def run_tests():
    """Run basic tests"""
    if Path("tests").exists():
        # Check if pytest is installed
        try:
            subprocess.run(["python", "-m", "pytest", "--version"], 
                         capture_output=True, check=True)
            return run_command("python -m pytest tests/ -v", "Running tests")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("[WARNING] pytest not installed, skipping tests")
            return True
    else:
        print("[WARNING] No tests directory found, skipping tests")
        return True

def main():
    """Main setup function"""
    print("Setting up Automated Stock Trading System")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("[ERROR] Python 3.8 or higher is required")
        sys.exit(1)
    
    print(f"[SUCCESS] Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Setup steps
    steps = [
        ("Creating directories", create_directories),
        ("Setting up environment", setup_environment),
        ("Installing dependencies", install_dependencies),
        ("Initializing database", initialize_database),
        ("Running tests", run_tests)
    ]
    
    failed_steps = []
    
    for step_name, step_func in steps:
        try:
            print(f"\n--- {step_name} ---")
            result = step_func()
            if result is None:
                result = True  # Treat None as success
            if not result:
                failed_steps.append(step_name)
        except Exception as e:
            print(f"[ERROR] {step_name} failed with error: {str(e)}")
            failed_steps.append(step_name)
    
    print("\n" + "=" * 50)
    
    if failed_steps:
        print("[WARNING] Setup completed with some issues:")
        for step in failed_steps:
            print(f"   - {step}")
        print("\nPlease resolve these issues before running the system.")
    else:
        print("[SUCCESS] Setup completed successfully!")
        print("\nNext steps:")
        print("1. Edit .env file with your IIFL API credentials")
        print("2. Add your Telegram bot token and chat ID")
        print("3. Run: python run.py")
        print("4. Access dashboard at: http://localhost:8000")

if __name__ == "__main__":
    main()
