#!/usr/bin/env python3
"""
Service Manager for External Services
Run as: python manage_services.py [start|stop|status|restart] [telegram|market|all]
"""

import asyncio
import subprocess
import sys
import os
import signal
import time
from typing import List, Dict, Optional

class ServiceManager:
    """Manage external services (Telegram bot and Market stream)"""
    
    def __init__(self):
        self.services = {
            'telegram': {
                'script': 'services/external_telegram_bot.py',
                'name': 'Telegram Bot Service',
                'process': None,
                'log_file': 'logs/telegram_bot.log'
            },
            'market': {
                'script': 'services/external_market_stream.py', 
                'name': 'Market Stream Service',
                'process': None,
                'log_file': 'logs/market_stream.log'
            }
        }
        
    def get_service_pid(self, service_name: str) -> Optional[int]:
        """Get PID of running service"""
        try:
            script_path = self.services[service_name]['script']
            result = subprocess.run(
                ['pgrep', '-f', script_path],
                capture_output=True,
                text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split('\n')[0])
        except Exception:
            pass
        return None
    
    def is_service_running(self, service_name: str) -> bool:
        """Check if service is running"""
        return self.get_service_pid(service_name) is not None
    
    def start_service(self, service_name: str) -> bool:
        """Start a service"""
        if service_name not in self.services:
            print(f"❌ Unknown service: {service_name}")
            return False
            
        if self.is_service_running(service_name):
            print(f"✅ {self.services[service_name]['name']} is already running")
            return True
            
        try:
            script_path = self.services[service_name]['script']
            print(f"🚀 Starting {self.services[service_name]['name']}...")
            
            # Ensure logs directory exists
            os.makedirs('logs', exist_ok=True)
            
            # Start service in background
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            if self.is_service_running(service_name):
                pid = self.get_service_pid(service_name)
                print(f"✅ {self.services[service_name]['name']} started (PID: {pid})")
                print(f"📄 Logs: {self.services[service_name]['log_file']}")
                return True
            else:
                print(f"❌ Failed to start {self.services[service_name]['name']}")
                return False
                
        except Exception as e:
            print(f"❌ Error starting {self.services[service_name]['name']}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a service"""
        if service_name not in self.services:
            print(f"❌ Unknown service: {service_name}")
            return False
            
        pid = self.get_service_pid(service_name)
        if not pid:
            print(f"✅ {self.services[service_name]['name']} is not running")
            return True
            
        try:
            print(f"🛑 Stopping {self.services[service_name]['name']} (PID: {pid})...")
            
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            
            # Wait for graceful shutdown
            for _ in range(10):
                time.sleep(0.5)
                if not self.is_service_running(service_name):
                    print(f"✅ {self.services[service_name]['name']} stopped gracefully")
                    return True
            
            # Force kill if still running
            if self.is_service_running(service_name):
                print(f"⚠️  Force killing {self.services[service_name]['name']}...")
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
                
            if not self.is_service_running(service_name):
                print(f"✅ {self.services[service_name]['name']} stopped")
                return True
            else:
                print(f"❌ Failed to stop {self.services[service_name]['name']}")
                return False
                
        except Exception as e:
            print(f"❌ Error stopping {self.services[service_name]['name']}: {e}")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a service"""
        print(f"🔄 Restarting {self.services[service_name]['name']}...")
        self.stop_service(service_name)
        time.sleep(1)
        return self.start_service(service_name)
    
    def show_status(self, service_name: str = None):
        """Show service status"""
        services_to_check = [service_name] if service_name else list(self.services.keys())
        
        print("📊 Service Status:")
        print("-" * 50)
        
        for svc in services_to_check:
            if svc not in self.services:
                continue
                
            running = self.is_service_running(svc)
            pid = self.get_service_pid(svc) if running else None
            status = "🟢 RUNNING" if running else "🔴 STOPPED"
            pid_info = f" (PID: {pid})" if pid else ""
            
            print(f"{self.services[svc]['name']:<25} {status}{pid_info}")
            print(f"  Script: {self.services[svc]['script']}")
            print(f"  Logs:   {self.services[svc]['log_file']}")
            print()

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage: python manage_services.py [start|stop|status|restart] [telegram|market|all]")
        print()
        print("Commands:")
        print("  start   - Start service(s)")
        print("  stop    - Stop service(s)")
        print("  restart - Restart service(s)")
        print("  status  - Show service status")
        print()
        print("Services:")
        print("  telegram - Telegram Bot Service")
        print("  market   - Market Stream Service")
        print("  all      - All services")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    service = sys.argv[2].lower() if len(sys.argv) > 2 else 'all'
    
    manager = ServiceManager()
    
    if command == 'status':
        if service == 'all':
            manager.show_status()
        else:
            manager.show_status(service)
    
    elif command == 'start':
        services_to_start = list(manager.services.keys()) if service == 'all' else [service]
        success = True
        for svc in services_to_start:
            if not manager.start_service(svc):
                success = False
        sys.exit(0 if success else 1)
    
    elif command == 'stop':
        services_to_stop = list(manager.services.keys()) if service == 'all' else [service]
        success = True
        for svc in services_to_stop:
            if not manager.stop_service(svc):
                success = False
        sys.exit(0 if success else 1)
    
    elif command == 'restart':
        services_to_restart = list(manager.services.keys()) if service == 'all' else [service]
        success = True
        for svc in services_to_restart:
            if not manager.restart_service(svc):
                success = False
        sys.exit(0 if success else 1)
    
    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()