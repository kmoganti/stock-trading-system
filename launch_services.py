#!/usr/bin/env python3
"""
Simple Service Launcher for Trading System
Python-based service manager as alternative to bash script
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

class ServiceManager:
    def __init__(self):
        self.services = {
            'telegram': {
                'script': 'services/external_telegram_bot.py',
                'name': 'Telegram Bot',
                'log': 'logs/telegram_bot.log'
            },
            'market': {
                'script': 'services/external_market_stream.py', 
                'name': 'Market Stream',
                'log': 'logs/market_stream.log'
            },
            'main': {
                'script': 'main.py',
                'name': 'Main Server',
                'log': 'logs/main_server.log'
            }
        }
        
        # Ensure logs directory exists
        os.makedirs('logs', exist_ok=True)
    
    def start_service(self, service_key):
        """Start a specific service"""
        if service_key not in self.services:
            print(f"❌ Unknown service: {service_key}")
            return False
            
        service = self.services[service_key]
        print(f"🚀 Starting {service['name']}...")
        
        try:
            # Start the service in background
            with open(service['log'], 'w') as log_file:
                process = subprocess.Popen(
                    [sys.executable, service['script']],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            # Give it a moment to start
            time.sleep(2)
            
            # Check if it's still running
            if process.poll() is None:
                print(f"✅ {service['name']} started successfully (PID: {process.pid})")
                print(f"📝 Logs: {service['log']}")
                return True
            else:
                print(f"❌ {service['name']} failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Error starting {service['name']}: {e}")
            return False
    
    def test_service(self, service_key):
        """Test a service by running it directly (foreground)"""
        if service_key not in self.services:
            print(f"❌ Unknown service: {service_key}")
            return False
            
        service = self.services[service_key]
        print(f"🧪 Testing {service['name']}...")
        print(f"📄 Script: {service['script']}")
        print(f"🔗 Running: python3 {service['script']}")
        print("=" * 50)
        
        try:
            # Run in foreground for testing
            result = subprocess.run([sys.executable, service['script']], 
                                  timeout=30, capture_output=True, text=True)
            
            print("STDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            print(f"\nReturn code: {result.returncode}")
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("⏰ Service test timed out (30s) - this might be normal for long-running services")
            return True
        except Exception as e:
            print(f"❌ Error testing {service['name']}: {e}")
            return False

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 launch_services.py start <service>    # Start service in background")
        print("  python3 launch_services.py test <service>     # Test service in foreground")
        print()
        print("Services: telegram, market, main")
        print()
        print("Examples:")
        print("  python3 launch_services.py test telegram")
        print("  python3 launch_services.py start market")
        sys.exit(1)
    
    manager = ServiceManager()
    command = sys.argv[1]
    service = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "start" and service:
        manager.start_service(service)
    elif command == "test" and service:
        manager.test_service(service)
    else:
        print("❌ Invalid command or missing service name")
        sys.exit(1)

if __name__ == "__main__":
    main()