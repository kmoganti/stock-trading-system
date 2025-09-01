#!/usr/bin/env python3
"""
Simplified setup script for the Automated Stock Trading System
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Main setup function"""
    print("Setting up Automated Stock Trading System")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("[ERROR] Python 3.8 or higher is required")
        print(f"Current version: {sys.version_info.major}.{sys.version_info.minor}")
        sys.exit(1)
    
    print(f"[SUCCESS] Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Create directories
    print("\n--- Creating directories ---")
    directories = ["logs", "reports", "data"]
    
    for directory in directories:
        try:
            Path(directory).mkdir(exist_ok=True)
            print(f"[INFO] Created directory: {directory}")
        except Exception as e:
            print(f"[ERROR] Failed to create directory {directory}: {str(e)}")
    
    # Setup environment file
    print("\n--- Setting up environment ---")
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists():
        if env_example.exists():
            try:
                env_file.write_text(env_example.read_text())
                print("[INFO] Created .env file from .env.example")
                print("[WARNING] Please edit .env file with your actual credentials")
            except Exception as e:
                print(f"[ERROR] Failed to create .env file: {str(e)}")
        else:
            print("[WARNING] No .env.example file found")
            # Create a basic .env template
            basic_env = """# IIFL API Configuration
CLIENT_ID=your_client_id
AUTH_CODE=your_auth_code
APP_SECRET=your_app_secret
BASE_URL=https://ttblaze.iifl.com

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Trading Configuration
AUTO_TRADE=false
SIGNAL_TIMEOUT=300
RISK_PER_TRADE=0.02
MAX_POSITIONS=10
MAX_DAILY_LOSS=5000.0
MIN_PRICE=10.0
MIN_LIQUIDITY=100000

# System Configuration
DATABASE_URL=sqlite+aiosqlite:///./trading.db
PORT=8000
DEBUG=true
SECRET_KEY=your-secret-key-change-this
"""
            try:
                env_file.write_text(basic_env)
                print("[INFO] Created basic .env template")
                print("[WARNING] Please edit .env file with your actual credentials")
            except Exception as e:
                print(f"[ERROR] Failed to create .env template: {str(e)}")
    else:
        print("[SUCCESS] .env file already exists")
    
    # Install dependencies
    print("\n--- Installing dependencies ---")
    if Path("requirements.txt").exists():
        try:
            print("[INFO] Installing dependencies...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print("[SUCCESS] Dependencies installed successfully")
            else:
                print(f"[ERROR] Failed to install dependencies: {result.stderr}")
                print("[INFO] You may need to install dependencies manually:")
                print("pip install -r requirements.txt")
        except subprocess.TimeoutExpired:
            print("[ERROR] Installation timed out")
            print("[INFO] Please install dependencies manually: pip install -r requirements.txt")
        except Exception as e:
            print(f"[ERROR] Installation failed: {str(e)}")
            print("[INFO] Please install dependencies manually: pip install -r requirements.txt")
    else:
        print("[ERROR] requirements.txt not found")
    
    # Create database (basic SQLite file)
    print("\n--- Setting up database ---")
    try:
        db_file = Path("trading.db")
        if not db_file.exists():
            # Just create an empty file - the app will initialize it
            db_file.touch()
            print("[INFO] Created database file")
        else:
            print("[INFO] Database file already exists")
        print("[SUCCESS] Database setup completed")
    except Exception as e:
        print(f"[WARNING] Database setup issue: {str(e)}")
        print("[INFO] Database will be created on first run")
    
    print("\n" + "=" * 50)
    print("[SUCCESS] Setup completed!")
    print("\nNext steps:")
    print("1. Edit .env file with your IIFL API credentials")
    print("2. Add your Telegram bot token and chat ID")
    print("3. Run: python run.py")
    print("4. Access dashboard at: http://localhost:8000")
    print("\nIf you encounter issues:")
    print("- Check that all dependencies are installed: pip install -r requirements.txt")
    print("- Verify your .env file has correct credentials")
    print("- Check logs/ directory for error messages")

if __name__ == "__main__":
    main()
