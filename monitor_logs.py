#!/usr/bin/env python3
"""
Real-time log monitoring and performance analysis for trading system.
"""
import os
import time
import json
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from collections import defaultdict, deque
from typing import Dict, List, Any
import threading

class LogPerformanceMonitor:
    """Monitor log performance and system metrics in real-time."""
    
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.metrics = {
            'events_per_second': deque(maxlen=60),  # Last 60 seconds
            'event_counts': defaultdict(int),
            'error_counts': defaultdict(int),
            'performance_alerts': [],
            'system_metrics': deque(maxlen=300)  # 5 minutes of data
        }
        self.start_time = datetime.now()
        self.running = False
        
    def start_monitoring(self):
        """Start real-time monitoring."""
        print("🚀 Starting log performance monitoring...")
        self.running = True
        
        # Start file monitoring
        event_handler = LogEventHandler(self)
        observer = Observer()
        observer.schedule(event_handler, str(self.log_dir), recursive=True)
        observer.start()
        
        # Start system metrics collection
        metrics_thread = threading.Thread(target=self._collect_system_metrics)
        metrics_thread.daemon = True
        metrics_thread.start()
        
        try:
            while self.running:
                self._display_dashboard()
                time.sleep(5)  # Update every 5 seconds
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping monitor...")
            self.running = False
            observer.stop()
        
        observer.join()
    
    def _collect_system_metrics(self):
        """Collect system performance metrics."""
        while self.running:
            try:
                cpu_percent = psutil.cpu_percent()
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('.')
                
                self.metrics['system_metrics'].append({
                    'timestamp': datetime.now(),
                    'cpu_percent': cpu_percent,
                    'memory_percent': memory.percent,
                    'memory_used_mb': memory.used / (1024 * 1024),
                    'disk_percent': disk.percent
                })
                
                # Check for performance alerts
                if cpu_percent > 80:
                    self._add_alert("HIGH_CPU", f"CPU usage: {cpu_percent:.1f}%")
                
                if memory.percent > 85:
                    self._add_alert("HIGH_MEMORY", f"Memory usage: {memory.percent:.1f}%")
                    
            except Exception as e:
                print(f"Error collecting system metrics: {e}")
            
            time.sleep(1)  # Collect every second
    
    def _add_alert(self, alert_type: str, message: str):
        """Add performance alert."""
        alert = {
            'timestamp': datetime.now(),
            'type': alert_type,
            'message': message
        }
        
        self.metrics['performance_alerts'].append(alert)
        
        # Keep only last 100 alerts
        if len(self.metrics['performance_alerts']) > 100:
            self.metrics['performance_alerts'] = self.metrics['performance_alerts'][-100:]
    
    def _display_dashboard(self):
        """Display real-time dashboard."""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("🔍 TRADING SYSTEM LOG MONITOR")
        print("=" * 50)
        print(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Running: {datetime.now() - self.start_time}")
        print()
        
        # Event statistics
        print("📊 EVENT STATISTICS (Last 60 seconds)")
        print("-" * 40)
        recent_events = sum(self.metrics['events_per_second'])
        print(f"Events/second: {recent_events / min(60, len(self.metrics['events_per_second'])):.1f}")
        
        if self.metrics['event_counts']:
            print("\nTop Event Types:")
            for event_type, count in sorted(self.metrics['event_counts'].items(), 
                                          key=lambda x: x[1], reverse=True)[:5]:
                print(f"  {event_type}: {count}")
        
        # System metrics
        if self.metrics['system_metrics']:
            latest_metrics = self.metrics['system_metrics'][-1]
            print(f"\n⚡ SYSTEM PERFORMANCE")
            print("-" * 30)
            print(f"CPU: {latest_metrics['cpu_percent']:.1f}%")
            print(f"Memory: {latest_metrics['memory_percent']:.1f}% ({latest_metrics['memory_used_mb']:.0f}MB)")
            print(f"Disk: {latest_metrics['disk_percent']:.1f}%")
        
        # Recent alerts
        if self.metrics['performance_alerts']:
            print(f"\n⚠️  RECENT ALERTS")
            print("-" * 20)
            recent_alerts = self.metrics['performance_alerts'][-5:]
            for alert in recent_alerts:
                time_str = alert['timestamp'].strftime('%H:%M:%S')
                print(f"  {time_str} {alert['type']}: {alert['message']}")
        
        # Error summary
        if self.metrics['error_counts']:
            print(f"\n🚨 ERROR SUMMARY")
            print("-" * 20)
            for error_type, count in sorted(self.metrics['error_counts'].items(), 
                                          key=lambda x: x[1], reverse=True)[:3]:
                print(f"  {error_type}: {count}")
        
        print("\nPress Ctrl+C to stop monitoring...")

class LogEventHandler(FileSystemEventHandler):
    """Handle log file changes."""
    
    def __init__(self, monitor: LogPerformanceMonitor):
        self.monitor = monitor
        self.file_positions = {}
        
    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Only monitor log files
        if file_path.suffix in ['.log', '.txt']:
            self._process_log_file(file_path)
    
    def _process_log_file(self, file_path: Path):
        """Process new log entries."""
        try:
            # Get current position or start from beginning
            last_pos = self.file_positions.get(str(file_path), 0)
            
            with open(file_path, 'r') as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                self.file_positions[str(file_path)] = f.tell()
            
            # Process new log entries
            for line in new_lines:
                self._analyze_log_entry(line.strip(), file_path.name)
                
        except Exception as e:
            pass  # Ignore file access errors
    
    def _analyze_log_entry(self, log_line: str, file_name: str):
        """Analyze individual log entry."""
        if not log_line:
            return
            
        current_second = int(time.time())
        
        # Update events per second counter
        if not self.monitor.metrics['events_per_second'] or \
           self.monitor.metrics['events_per_second'][-1] != current_second:
            self.monitor.metrics['events_per_second'].append(1)
        else:
            # Increment current second counter
            if len(self.monitor.metrics['events_per_second']) > 0:
                self.monitor.metrics['events_per_second'][-1] += 1
        
        # Try to parse JSON log entries
        try:
            if log_line.startswith('{') and log_line.endswith('}'):
                entry = json.loads(log_line)
                event_type = entry.get('event_type', 'unknown')
                level = entry.get('level', 'INFO')
                
                self.monitor.metrics['event_counts'][event_type] += 1
                
                # Track errors
                if level in ['ERROR', 'CRITICAL']:
                    error_type = entry.get('component', 'unknown')
                    self.monitor.metrics['error_counts'][error_type] += 1
                
                # Check for performance issues
                if event_type == 'operation_complete':
                    duration = entry.get('duration_seconds', 0)
                    if duration > 5:  # Slow operation
                        self.monitor._add_alert(
                            "SLOW_OPERATION",
                            f"{entry.get('operation', 'Unknown')}: {duration:.1f}s"
                        )
                
        except json.JSONDecodeError:
            # Regular log entry, categorize by level
            if 'ERROR' in log_line or 'CRITICAL' in log_line:
                self.monitor.metrics['error_counts']['general'] += 1
            elif 'WARNING' in log_line:
                self.monitor.metrics['event_counts']['warning'] += 1
            else:
                self.monitor.metrics['event_counts']['info'] += 1

def generate_performance_report(log_dir: str = "logs", hours: int = 24) -> str:
    """Generate performance analysis report."""
    monitor = LogPerformanceMonitor(log_dir)
    
    # Analyze log files for the specified period
    log_files = list(Path(log_dir).glob('*.log'))
    
    if not log_files:
        return "📋 No log files found for analysis."
    
    report = []
    report.append("📈 LOGGING PERFORMANCE REPORT")
    report.append("=" * 40)
    report.append(f"Analysis Period: Last {hours} hours")
    report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Analyze each log file
    total_events = 0
    file_stats = {}
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    for log_file in log_files:
        try:
            events_count = 0
            error_count = 0
            file_size = log_file.stat().st_size / (1024 * 1024)  # MB
            
            with open(log_file, 'r') as f:
                for line in f:
                    try:
                        if line.startswith('{'):
                            entry = json.loads(line.strip())
                            entry_time = datetime.fromisoformat(entry.get('timestamp', ''))
                            
                            if entry_time >= cutoff_time:
                                events_count += 1
                                if entry.get('level') in ['ERROR', 'CRITICAL']:
                                    error_count += 1
                    except:
                        continue
            
            file_stats[log_file.name] = {
                'events': events_count,
                'errors': error_count,
                'size_mb': file_size
            }
            total_events += events_count
            
        except Exception as e:
            continue
    
    # File statistics
    report.append("📁 LOG FILE STATISTICS")
    report.append("-" * 30)
    for file_name, stats in sorted(file_stats.items(), key=lambda x: x[1]['events'], reverse=True):
        report.append(f"{file_name}:")
        report.append(f"  Events: {stats['events']:,}")
        report.append(f"  Errors: {stats['errors']}")
        report.append(f"  Size: {stats['size_mb']:.1f}MB")
        report.append("")
    
    # Summary
    report.append("📊 SUMMARY")
    report.append("-" * 15)
    report.append(f"Total Events: {total_events:,}")
    report.append(f"Events/Hour: {total_events // max(1, hours):,}")
    report.append(f"Total Log Files: {len(log_files)}")
    report.append(f"Total Log Size: {sum(s['size_mb'] for s in file_stats.values()):.1f}MB")
    
    return "\n".join(report)

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor trading system logs')
    parser.add_argument('--monitor', action='store_true', help='Start real-time monitoring')
    parser.add_argument('--report', action='store_true', help='Generate performance report')
    parser.add_argument('--log-dir', default='logs', help='Log directory path')
    parser.add_argument('--hours', type=int, default=24, help='Hours for report analysis')
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor = LogPerformanceMonitor(args.log_dir)
        monitor.start_monitoring()
    elif args.report:
        report = generate_performance_report(args.log_dir, args.hours)
        print(report)
    else:
        print("Use --monitor for real-time monitoring or --report for analysis")

if __name__ == "__main__":
    main()