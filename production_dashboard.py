"""
Production Dashboard - Quick Status Overview

This script provides a quick overview of the production trading system status.
Run this anytime to get current system status.
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
import json
from pathlib import Path
import requests
import sys
import os

# Add project directory to Python path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class ProductionDashboard:
    """Quick production status dashboard."""
    
    def __init__(self):
        self.db_path = "trading_system.db"
        self.api_url = "http://localhost:8000"
    
    def get_trading_status(self):
        """Get current trading system status."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get active signals
            cursor.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE status = 'ACTIVE'
            """)
            active_signals = cursor.fetchone()[0]
            
            # Get today's signals
            cursor.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE DATE(created_at) = DATE('now')
            """)
            todays_signals = cursor.fetchone()[0]
            
            # Get recent P&L
            cursor.execute("""
                SELECT daily_pnl FROM pnl_reports 
                WHERE DATE(created_at) = DATE('now')
                ORDER BY created_at DESC LIMIT 1
            """)
            result = cursor.fetchone()
            daily_pnl = result[0] if result else 0
            
            # Get risk events today
            cursor.execute("""
                SELECT COUNT(*) FROM risk_events 
                WHERE DATE(created_at) = DATE('now')
            """)
            risk_events_today = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "active_signals": active_signals,
                "todays_signals": todays_signals,
                "daily_pnl": daily_pnl,
                "risk_events_today": risk_events_today
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def get_server_status(self):
        """Check if server is running."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return {
                "running": True,
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000
            }
        except:
            return {"running": False}
    
    def get_config_status(self):
        """Get configuration status."""
        try:
            from config.settings import get_settings
            settings = get_settings()
            
            return {
                "environment": settings.environment,
                "auto_trade": getattr(settings, 'auto_trade', False),
                "dry_run": getattr(settings, 'dry_run', True),
                "scheduler_enabled": getattr(settings, 'enable_scheduler', False)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def print_dashboard(self):
        """Print formatted dashboard to console."""
        print("\n" + "🏭 PRODUCTION TRADING SYSTEM DASHBOARD")
        print("="*50)
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Server Status
        server_status = self.get_server_status()
        if server_status.get("running"):
            print(f"🟢 Server: RUNNING (Response: {server_status.get('response_time_ms', 0):.1f}ms)")
        else:
            print("🔴 Server: NOT RUNNING")
        
        # Configuration
        config = self.get_config_status()
        if "error" not in config:
            print(f"⚙️ Environment: {config.get('environment', 'unknown').upper()}")
            
            auto_trade = config.get('auto_trade', False)
            dry_run = config.get('dry_run', True)
            
            if auto_trade and not dry_run:
                print("🚨 Mode: LIVE TRADING")
            elif auto_trade and dry_run:
                print("📊 Mode: PAPER TRADING")
            else:
                print("⏸️ Mode: MANUAL")
            
            scheduler = config.get('scheduler_enabled', False)
            print(f"📅 Scheduler: {'ENABLED' if scheduler else 'DISABLED'}")
        
        # Trading Status
        trading_status = self.get_trading_status()
        if "error" not in trading_status:
            print(f"📈 Active Signals: {trading_status.get('active_signals', 0)}")
            print(f"📊 Today's Signals: {trading_status.get('todays_signals', 0)}")
            
            daily_pnl = trading_status.get('daily_pnl', 0)
            pnl_emoji = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "➡️"
            print(f"{pnl_emoji} Daily P&L: ₹{daily_pnl:.2f}")
            
            risk_events = trading_status.get('risk_events_today', 0)
            if risk_events > 0:
                print(f"⚠️ Risk Events Today: {risk_events}")
            else:
                print("✅ No Risk Events Today")
        
        # Recent Files
        log_files = list(Path("logs").glob("*.log")) if Path("logs").exists() else []
        if log_files:
            latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
            log_size_mb = latest_log.stat().st_size / (1024**2)
            print(f"📋 Latest Log: {latest_log.name} ({log_size_mb:.1f}MB)")
        
        print("="*50)
        
        # Quick Commands
        print("\n🔧 QUICK COMMANDS:")
        print("Health Check:     python production_health_check.py")
        print("View Logs:        Get-Content logs\\trading_system.log -Tail 20")
        print("Server Status:    Invoke-RestMethod http://localhost:8000/health")
        print("Stop Server:      Ctrl+C (if running in foreground)")
        
        # Warnings
        if not server_status.get("running"):
            print("\n⚠️ WARNING: Server is not running!")
            print("   Start with: python production_server.py")
        
        if config.get('auto_trade') and not config.get('dry_run'):
            print("\n🚨 CAUTION: LIVE TRADING IS ENABLED!")
            print("   Monitor closely and ensure proper risk management")
        
        print("")

def main():
    """Main function to display dashboard."""
    dashboard = ProductionDashboard()
    
    try:
        dashboard.print_dashboard()
        return 0
    except Exception as e:
        print(f"❌ Dashboard error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())