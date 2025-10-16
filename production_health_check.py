"""
Production Health Check and Monitoring System

This script provides comprehensive health monitoring for the production
trading system including system resources, database health, API status,
and trading system status.
"""

import asyncio
import logging
import psutil
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import aiohttp
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ProductionHealthMonitor:
    """Comprehensive health monitoring for production trading system."""
    
    def __init__(self):
        self.db_path = "trading_system.db"
        self.api_base_url = "http://localhost:8000"
        self.health_data = {}
        
    async def check_system_resources(self) -> Dict:
        """Check system CPU, memory, and disk usage."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('.')
            
            # Check network connectivity
            network_stats = psutil.net_io_counters()
            
            return {
                "status": "healthy" if cpu_percent < 80 and memory.percent < 80 else "warning",
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_gb": memory.available / (1024**3),
                "disk_percent": disk.percent,
                "disk_free_gb": disk.free / (1024**3),
                "network_bytes_sent": network_stats.bytes_sent,
                "network_bytes_recv": network_stats.bytes_recv,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"System resource check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def check_database_health(self) -> Dict:
        """Check database connectivity and recent activity."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check database file size
            db_size = Path(self.db_path).stat().st_size / (1024**2)  # MB
            
            # Check recent signals
            cursor.execute("""
                SELECT COUNT(*) FROM signals 
                WHERE created_at > datetime('now', '-1 hour')
            """)
            recent_signals = cursor.fetchone()[0]
            
            # Check recent trades
            cursor.execute("""
                SELECT COUNT(*) FROM pnl_reports 
                WHERE created_at > datetime('now', '-1 hour')
            """)
            recent_trades = cursor.fetchone()[0]
            
            # Check database integrity
            cursor.execute("PRAGMA integrity_check")
            integrity_result = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                "status": "healthy" if integrity_result == "ok" else "error",
                "database_size_mb": db_size,
                "recent_signals_1h": recent_signals,
                "recent_trades_1h": recent_trades,
                "integrity_check": integrity_result,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def check_api_health(self) -> Dict:
        """Check API endpoints are responding."""
        try:
            async with aiohttp.ClientSession() as session:
                # Check health endpoint
                try:
                    async with session.get(f"{self.api_base_url}/health", timeout=10) as response:
                        health_status = response.status == 200
                        health_response_time = response.headers.get('X-Response-Time', 'N/A')
                except:
                    health_status = False
                    health_response_time = 'N/A'
                
                # Check API documentation
                try:
                    async with session.get(f"{self.api_base_url}/docs", timeout=10) as response:
                        docs_status = response.status == 200
                except:
                    docs_status = False
                
                return {
                    "status": "healthy" if health_status else "error",
                    "health_endpoint": health_status,
                    "docs_endpoint": docs_status,
                    "response_time": health_response_time,
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"API health check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def check_trading_system_status(self) -> Dict:
        """Check trading system specific status."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check active positions
            cursor.execute("""
                SELECT symbol, COUNT(*) as count
                FROM signals 
                WHERE status = 'ACTIVE'
                GROUP BY symbol
            """)
            active_positions = dict(cursor.fetchall())
            
            # Check recent P&L
            cursor.execute("""
                SELECT SUM(daily_pnl) as total_pnl
                FROM pnl_reports 
                WHERE DATE(created_at) = DATE('now')
            """)
            daily_pnl = cursor.fetchone()[0] or 0
            
            # Check risk events
            cursor.execute("""
                SELECT COUNT(*) FROM risk_events 
                WHERE created_at > datetime('now', '-1 hour')
                AND severity IN ('HIGH', 'CRITICAL')
            """)
            recent_risk_events = cursor.fetchone()[0]
            
            # Check last signal generation time
            cursor.execute("""
                SELECT MAX(created_at) FROM signals
            """)
            last_signal_time = cursor.fetchone()[0]
            
            conn.close()
            
            # Calculate time since last signal
            if last_signal_time:
                last_signal_dt = datetime.fromisoformat(last_signal_time.replace('Z', '+00:00'))
                minutes_since_signal = (datetime.utcnow() - last_signal_dt).total_seconds() / 60
            else:
                minutes_since_signal = float('inf')
            
            status = "healthy"
            if recent_risk_events > 0:
                status = "warning"
            if minutes_since_signal > 120:  # No signals for 2+ hours
                status = "warning"
            if daily_pnl < -1000:  # Daily loss > 1000
                status = "critical"
            
            return {
                "status": status,
                "active_positions": active_positions,
                "active_positions_count": len(active_positions),
                "daily_pnl": daily_pnl,
                "recent_risk_events": recent_risk_events,
                "minutes_since_last_signal": minutes_since_signal,
                "last_signal_time": last_signal_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Trading system status check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def check_log_files(self) -> Dict:
        """Check log files for errors and warnings."""
        try:
            log_files = list(Path("logs").glob("*.log"))
            
            if not log_files:
                return {"status": "warning", "message": "No log files found"}
            
            recent_errors = 0
            recent_warnings = 0
            log_file_sizes = {}
            
            for log_file in log_files:
                try:
                    # Check file size
                    size_mb = log_file.stat().st_size / (1024**2)
                    log_file_sizes[log_file.name] = size_mb
                    
                    # Read recent log entries (last 100 lines)
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        recent_lines = lines[-100:] if len(lines) > 100 else lines
                        
                        for line in recent_lines:
                            if 'ERROR' in line.upper():
                                recent_errors += 1
                            elif 'WARNING' in line.upper():
                                recent_warnings += 1
                                
                except Exception as e:
                    logger.warning(f"Could not read log file {log_file}: {str(e)}")
            
            status = "healthy"
            if recent_errors > 10:
                status = "warning"
            if recent_errors > 50:
                status = "critical"
            
            return {
                "status": status,
                "log_files_count": len(log_files),
                "log_file_sizes_mb": log_file_sizes,
                "recent_errors": recent_errors,
                "recent_warnings": recent_warnings,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Log files check failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    async def run_comprehensive_health_check(self) -> Dict:
        """Run all health checks and return comprehensive status."""
        logger.info("🔍 Running comprehensive health check...")
        
        # Run all checks concurrently
        system_check, db_check, api_check, trading_check, log_check = await asyncio.gather(
            self.check_system_resources(),
            self.check_database_health(),
            self.check_api_health(),
            self.check_trading_system_status(),
            self.check_log_files(),
            return_exceptions=True
        )
        
        # Determine overall status
        checks = [system_check, db_check, api_check, trading_check, log_check]
        statuses = [check.get("status", "error") if isinstance(check, dict) else "error" for check in checks]
        
        if "critical" in statuses:
            overall_status = "critical"
        elif "error" in statuses:
            overall_status = "error"
        elif "warning" in statuses:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "system_resources": system_check,
                "database": db_check,
                "api": api_check,
                "trading_system": trading_check,
                "log_files": log_check
            }
        }
    
    def print_health_report(self, health_data: Dict):
        """Print formatted health report to console."""
        print("\n" + "="*60)
        print("🏥 PRODUCTION HEALTH CHECK REPORT")
        print("="*60)
        
        # Overall status
        status_emoji = {
            "healthy": "✅",
            "warning": "⚠️", 
            "error": "❌",
            "critical": "🚨"
        }
        
        overall_status = health_data.get("overall_status", "unknown")
        print(f"\n🎯 Overall Status: {status_emoji.get(overall_status, '❓')} {overall_status.upper()}")
        print(f"📅 Check Time: {health_data.get('timestamp', 'N/A')}")
        
        checks = health_data.get("checks", {})
        
        # System Resources
        system = checks.get("system_resources", {})
        print(f"\n💻 System Resources: {status_emoji.get(system.get('status'), '❓')}")
        if system.get("status") != "error":
            print(f"   CPU Usage: {system.get('cpu_percent', 'N/A')}%")
            print(f"   Memory Usage: {system.get('memory_percent', 'N/A')}%")
            print(f"   Memory Available: {system.get('memory_available_gb', 'N/A'):.1f} GB")
            print(f"   Disk Usage: {system.get('disk_percent', 'N/A')}%")
            print(f"   Disk Free: {system.get('disk_free_gb', 'N/A'):.1f} GB")
        
        # Database
        database = checks.get("database", {})
        print(f"\n🗄️ Database: {status_emoji.get(database.get('status'), '❓')}")
        if database.get("status") != "error":
            print(f"   Database Size: {database.get('database_size_mb', 'N/A'):.1f} MB")
            print(f"   Recent Signals (1h): {database.get('recent_signals_1h', 'N/A')}")
            print(f"   Recent Trades (1h): {database.get('recent_trades_1h', 'N/A')}")
            print(f"   Integrity: {database.get('integrity_check', 'N/A')}")
        
        # API
        api = checks.get("api", {})
        print(f"\n🌐 API: {status_emoji.get(api.get('status'), '❓')}")
        if api.get("status") != "error":
            print(f"   Health Endpoint: {'✅' if api.get('health_endpoint') else '❌'}")
            print(f"   Docs Endpoint: {'✅' if api.get('docs_endpoint') else '❌'}")
            print(f"   Response Time: {api.get('response_time', 'N/A')}")
        
        # Trading System
        trading = checks.get("trading_system", {})
        print(f"\n📈 Trading System: {status_emoji.get(trading.get('status'), '❓')}")
        if trading.get("status") != "error":
            print(f"   Active Positions: {trading.get('active_positions_count', 'N/A')}")
            print(f"   Daily P&L: ₹{trading.get('daily_pnl', 'N/A'):.2f}")
            print(f"   Risk Events (1h): {trading.get('recent_risk_events', 'N/A')}")
            print(f"   Minutes Since Last Signal: {trading.get('minutes_since_last_signal', 'N/A'):.1f}")
        
        # Logs
        logs = checks.get("log_files", {})
        print(f"\n📋 Log Files: {status_emoji.get(logs.get('status'), '❓')}")
        if logs.get("status") != "error":
            print(f"   Log Files Count: {logs.get('log_files_count', 'N/A')}")
            print(f"   Recent Errors: {logs.get('recent_errors', 'N/A')}")
            print(f"   Recent Warnings: {logs.get('recent_warnings', 'N/A')}")
        
        print("\n" + "="*60)
        
        # Recommendations
        if overall_status in ["warning", "error", "critical"]:
            print("\n🔧 RECOMMENDED ACTIONS:")
            
            if system.get("cpu_percent", 0) > 80:
                print("   • High CPU usage - consider reducing strategy frequency")
            if system.get("memory_percent", 0) > 80:
                print("   • High memory usage - restart service or check for memory leaks")
            if trading.get("recent_risk_events", 0) > 0:
                print("   • Risk events detected - review risk management settings")
            if trading.get("minutes_since_last_signal", 0) > 120:
                print("   • No recent signals - check strategy execution and market data")
            if logs.get("recent_errors", 0) > 10:
                print("   • High error rate - review log files for issues")
            
            print("")

async def main():
    """Main function to run health check."""
    monitor = ProductionHealthMonitor()
    
    try:
        # Run comprehensive health check
        health_data = await monitor.run_comprehensive_health_check()
        
        # Print report to console
        monitor.print_health_report(health_data)
        
        # Save to file
        health_file = Path("logs") / f"health_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        health_file.parent.mkdir(exist_ok=True)
        
        with open(health_file, 'w') as f:
            json.dump(health_data, f, indent=2)
        
        print(f"📄 Health check report saved to: {health_file}")
        
        # Return exit code based on status
        overall_status = health_data.get("overall_status", "error")
        if overall_status == "healthy":
            return 0
        elif overall_status == "warning":
            return 1
        else:
            return 2
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        print(f"\n❌ Health check failed: {str(e)}")
        return 3

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)