#!/usr/bin/env python3
"""
Test script to validate logging performance optimizations.
"""
import time
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import os

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from services.logging_service import TradingLogger
from services.enhanced_logging import critical_events
from config.settings import get_settings

class LoggingPerformanceTest:
    """Test logging performance under various conditions."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = TradingLogger()
        self.results = {}
    
    def test_basic_logging_performance(self, num_messages: int = 1000):
        """Test basic logging performance."""
        print(f"🔬 Testing basic logging performance ({num_messages} messages)...")
        
        start_time = time.time()
        for i in range(num_messages):
            self.logger.log_trade(f"TEST_TRADE_{i}", "BUY", 100, 2500.0, "SUCCESS")
        
        duration = time.time() - start_time
        messages_per_second = num_messages / duration
        
        self.results['basic_logging'] = {
            'messages': num_messages,
            'duration': duration,
            'messages_per_second': messages_per_second
        }
        
        print(f"   ✅ {messages_per_second:.0f} messages/second")
        return messages_per_second
    
    def test_critical_events_performance(self, num_events: int = 500):
        """Test critical events logging performance."""
        print(f"🔬 Testing critical events performance ({num_events} events)...")
        
        start_time = time.time()
        for i in range(num_events):
            critical_events.log_order_execution(
                f"ORDER_{i}", "RELIANCE", "BUY", 10, 2500.0, "EXECUTED"
            )
        
        duration = time.time() - start_time
        events_per_second = num_events / duration
        
        self.results['critical_events'] = {
            'events': num_events,
            'duration': duration,
            'events_per_second': events_per_second
        }
        
        print(f"   ✅ {events_per_second:.0f} events/second")
        return events_per_second
    
    def test_concurrent_logging(self, num_threads: int = 5, messages_per_thread: int = 200):
        """Test concurrent logging performance."""
        print(f"🔬 Testing concurrent logging ({num_threads} threads, {messages_per_thread} messages each)...")
        
        def log_worker(thread_id: int):
            """Worker function for concurrent logging."""
            for i in range(messages_per_thread):
                self.logger.log_api_call(
                    f"GET /api/test/{thread_id}/{i}", 200, 0.05
                )
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [
                executor.submit(log_worker, thread_id) 
                for thread_id in range(num_threads)
            ]
            
            # Wait for all threads to complete
            for future in futures:
                future.result()
        
        duration = time.time() - start_time
        total_messages = num_threads * messages_per_thread
        messages_per_second = total_messages / duration
        
        self.results['concurrent_logging'] = {
            'threads': num_threads,
            'total_messages': total_messages,
            'duration': duration,
            'messages_per_second': messages_per_second
        }
        
        print(f"   ✅ {messages_per_second:.0f} messages/second (concurrent)")
        return messages_per_second
    
    async def test_async_logging_performance(self, num_messages: int = 1000):
        """Test async logging performance."""
        print(f"🔬 Testing async logging performance ({num_messages} messages)...")
        
        async def log_async_message(i: int):
            """Async logging function."""
            await asyncio.sleep(0.001)  # Simulate async work
            self.logger.log_risk_event(f"RISK_TEST_{i}", "LOW", {"test": True})
        
        start_time = time.time()
        
        # Run async logging tasks
        tasks = [log_async_message(i) for i in range(num_messages)]
        await asyncio.gather(*tasks)
        
        duration = time.time() - start_time
        messages_per_second = num_messages / duration
        
        self.results['async_logging'] = {
            'messages': num_messages,
            'duration': duration,
            'messages_per_second': messages_per_second
        }
        
        print(f"   ✅ {messages_per_second:.0f} messages/second (async)")
        return messages_per_second
    
    def test_large_message_logging(self, num_messages: int = 100):
        """Test logging of large messages."""
        print(f"🔬 Testing large message logging ({num_messages} large messages)...")
        
        # Create a large message (10KB)
        large_data = "x" * 10000
        
        start_time = time.time()
        for i in range(num_messages):
            self.logger.main_logger.info(f"Large message {i}: {large_data}")
        
        duration = time.time() - start_time
        messages_per_second = num_messages / duration
        
        self.results['large_messages'] = {
            'messages': num_messages,
            'message_size_kb': 10,
            'duration': duration,
            'messages_per_second': messages_per_second
        }
        
        print(f"   ✅ {messages_per_second:.1f} large messages/second")
        return messages_per_second
    
    def test_json_vs_text_formatting(self, num_messages: int = 1000):
        """Compare JSON vs text formatting performance."""
        print(f"🔬 Testing JSON vs text formatting ({num_messages} messages each)...")
        
        # Test JSON formatting
        start_time = time.time()
        for i in range(num_messages):
            critical_events.log_performance_metric(f"test_metric_{i}", float(i), "ms")
        json_duration = time.time() - start_time
        
        # Test text formatting  
        start_time = time.time()
        for i in range(num_messages):
            self.logger.main_logger.info(f"Test message {i} with value {float(i)}ms")
        text_duration = time.time() - start_time
        
        json_rate = num_messages / json_duration
        text_rate = num_messages / text_duration
        
        self.results['formatting_comparison'] = {
            'json_messages_per_second': json_rate,
            'text_messages_per_second': text_rate,
            'performance_ratio': text_rate / json_rate
        }
        
        print(f"   ✅ JSON: {json_rate:.0f} msg/sec, Text: {text_rate:.0f} msg/sec")
        print(f"   📊 Text is {text_rate/json_rate:.1f}x faster than JSON")
        
        return json_rate, text_rate
    
    def analyze_log_file_sizes(self):
        """Analyze current log file sizes."""
        print("📊 Analyzing log file sizes...")
        
        log_dir = Path("logs")
        if not log_dir.exists():
            print("   ⚠️  Log directory not found")
            return
        
        log_files = list(log_dir.glob("*.log"))
        total_size = 0
        
        for log_file in log_files:
            try:
                size_mb = log_file.stat().st_size / (1024 * 1024)
                total_size += size_mb
                print(f"   📄 {log_file.name}: {size_mb:.2f} MB")
            except Exception as e:
                print(f"   ❌ Error reading {log_file.name}: {e}")
        
        print(f"   📊 Total log size: {total_size:.2f} MB")
        
        self.results['log_file_analysis'] = {
            'total_files': len(log_files),
            'total_size_mb': total_size,
            'files': {f.name: f.stat().st_size / (1024 * 1024) for f in log_files}
        }
    
    def generate_performance_report(self):
        """Generate comprehensive performance report."""
        print("\n" + "="*60)
        print("🚀 LOGGING PERFORMANCE REPORT")
        print("="*60)
        
        if 'basic_logging' in self.results:
            basic = self.results['basic_logging']
            print(f"📈 Basic Logging: {basic['messages_per_second']:.0f} messages/second")
        
        if 'critical_events' in self.results:
            critical = self.results['critical_events']
            print(f"🔥 Critical Events: {critical['events_per_second']:.0f} events/second")
        
        if 'concurrent_logging' in self.results:
            concurrent = self.results['concurrent_logging']
            print(f"🔄 Concurrent Logging: {concurrent['messages_per_second']:.0f} messages/second")
        
        if 'async_logging' in self.results:
            async_log = self.results['async_logging']
            print(f"⚡ Async Logging: {async_log['messages_per_second']:.0f} messages/second")
        
        if 'large_messages' in self.results:
            large = self.results['large_messages']
            print(f"📦 Large Messages: {large['messages_per_second']:.1f} messages/second")
        
        if 'formatting_comparison' in self.results:
            fmt = self.results['formatting_comparison']
            print(f"🎨 Formatting - JSON: {fmt['json_messages_per_second']:.0f}, Text: {fmt['text_messages_per_second']:.0f} msg/sec")
        
        # Performance assessment
        print("\n📋 Performance Assessment:")
        
        basic_rate = self.results.get('basic_logging', {}).get('messages_per_second', 0)
        if basic_rate > 5000:
            print("   ✅ Excellent performance (>5000 msg/sec)")
        elif basic_rate > 1000:
            print("   ✅ Good performance (>1000 msg/sec)")
        elif basic_rate > 500:
            print("   ⚠️  Moderate performance (>500 msg/sec)")
        else:
            print("   ❌ Poor performance (<500 msg/sec) - optimization needed")
        
        # Configuration recommendations
        print("\n💡 Optimization Recommendations:")
        
        if self.logger.use_optimized:
            print("   ✅ Using optimized logging configuration")
        else:
            print("   ⚠️  Consider enabling optimized logging")
        
        if hasattr(self.settings, 'log_format') and self.settings.log_format == 'json':
            print("   ⚠️  JSON format active - consider 'text' for higher performance")
        
        if hasattr(self.settings, 'log_console_enabled') and self.settings.log_console_enabled:
            print("   ⚠️  Console logging enabled - disable for production")
    
    async def run_all_tests(self):
        """Run all performance tests."""
        print("🔍 Starting Logging Performance Tests...")
        print("="*50)
        
        # Run synchronous tests
        self.test_basic_logging_performance(1000)
        self.test_critical_events_performance(500)
        self.test_concurrent_logging(3, 100)
        self.test_large_message_logging(50)
        self.test_json_vs_text_formatting(500)
        
        # Run async test
        await self.test_async_logging_performance(500)
        
        # Analyze current state
        self.analyze_log_file_sizes()
        
        # Generate report
        self.generate_performance_report()

def main():
    """Main function to run logging performance tests."""
    test_suite = LoggingPerformanceTest()
    
    print("🚀 Logging Performance Optimization Test Suite")
    print("=" * 50)
    print(f"Configuration: {test_suite.logger.use_optimized and 'Optimized' or 'Standard'}")
    print()
    
    # Run tests
    asyncio.run(test_suite.run_all_tests())

if __name__ == "__main__":
    main()