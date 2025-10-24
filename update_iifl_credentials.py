#!/usr/bin/env python3
"""
IIFL Credentials Update Helper
Helps you securely update IIFL credentials in the .env file
"""

import os
import sys
import getpass
from pathlib import Path

def update_iifl_credentials():
    """Interactive credential update"""
    print("🔐 IIFL Credentials Update Helper")
    print("=" * 50)
    
    env_path = Path("/workspaces/stock-trading-system/.env")
    
    if not env_path.exists():
        print("❌ .env file not found!")
        return False
    
    print("This will update your IIFL API credentials in the .env file.")
    print("⚠️  Keep your credentials secure and don't share them!")
    print()
    
    # Get credentials from user
    print("Please enter your IIFL API credentials:")
    print("(You can find these in your IIFL account dashboard under API settings)")
    print()
    
    client_id = input("IIFL Client ID: ").strip()
    if not client_id:
        print("❌ Client ID cannot be empty!")
        return False
    
    auth_code = getpass.getpass("IIFL Auth Code (hidden input): ").strip()
    if not auth_code:
        print("❌ Auth Code cannot be empty!")
        return False
    
    app_secret = getpass.getpass("IIFL App Secret (hidden input): ").strip()
    if not app_secret:
        print("❌ App Secret cannot be empty!")
        return False
    
    # Read current .env file
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"❌ Error reading .env file: {e}")
        return False
    
    # Update the lines
    updated_lines = []
    for line in lines:
        if line.startswith('IIFL_CLIENT_ID='):
            updated_lines.append(f'IIFL_CLIENT_ID={client_id}\n')
        elif line.startswith('IIFL_AUTH_CODE='):
            updated_lines.append(f'IIFL_AUTH_CODE={auth_code}\n')
        elif line.startswith('IIFL_APP_SECRET='):
            updated_lines.append(f'IIFL_APP_SECRET={app_secret}\n')
        else:
            updated_lines.append(line)
    
    # Write updated .env file
    try:
        with open(env_path, 'w') as f:
            f.writelines(updated_lines)
        
        print("✅ IIFL credentials updated successfully!")
        print()
        print("Next steps:")
        print("1. Run the authentication test:")
        print("   python test_iifl_holdings.py")
        print()
        print("2. If authentication works, you can run trading strategies:")
        print("   python run_all_tests.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error writing .env file: {e}")
        return False

def show_current_credentials():
    """Show current credential status (masked)"""
    print("📋 Current IIFL Credentials Status:")
    print("-" * 40)
    
    env_path = Path("/workspaces/stock-trading-system/.env")
    if not env_path.exists():
        print("❌ .env file not found!")
        return
    
    try:
        with open(env_path, 'r') as f:
            content = f.read()
        
        # Check for each credential
        credentials = {
            'IIFL_CLIENT_ID': None,
            'IIFL_AUTH_CODE': None,
            'IIFL_APP_SECRET': None
        }
        
        for line in content.split('\n'):
            for cred in credentials:
                if line.startswith(f'{cred}='):
                    value = line.split('=', 1)[1]
                    credentials[cred] = value
        
        for cred, value in credentials.items():
            if value and not value.startswith('mock_'):
                # Show first 4 and last 4 characters with stars in between
                if len(value) > 8:
                    masked = f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"
                else:
                    masked = f"{value[:2]}{'*' * (len(value) - 2)}"
                print(f"✅ {cred}: {masked} (Real value)")
            else:
                print(f"❌ {cred}: {value or 'Not set'} (Mock or missing)")
                
    except Exception as e:
        print(f"❌ Error reading credentials: {e}")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        show_current_credentials()
    else:
        show_current_credentials()
        print()
        response = input("Do you want to update IIFL credentials? (y/N): ").lower().strip()
        if response in ['y', 'yes']:
            update_iifl_credentials()
        else:
            print("No changes made.")

if __name__ == "__main__":
    main()