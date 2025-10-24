#!/usr/bin/env python3
"""
Startup Performance Profiler
Helps identify slow startup bottlenecks in the trading system.
"""

import time
import sys
import os
import asyncio
import logging
from pathlib import Path

# Setup basic logging for profiler
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - PROFILER - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StartupProfiler:
    """Profile trading system startup performance"""
    
    def __init__(self):
        self.timings = {}
        self.start_time = time.perf_counter()
        
    async def time_step(self, step_name: str, func=None, *args, **kwargs):
        """Time a startup step"""
        step_start = time.perf_counter()
        logger.info(f"🔄 Starting: {step_name}")
        
        try:
            if func:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            else:
                result = None
                
            duration = time.perf_counter() - step_start
            self.timings[step_name] = duration
            
            if duration > 2.0:
                logger.warning(f"⚠️ SLOW: {step_name} took {duration:.2f}s")
            elif duration > 1.0:
                logger.info(f"⏰ {step_name} took {duration:.2f}s")
            else:
                logger.info(f"✅ {step_name} completed in {duration:.2f}s")
                
            return result
            
        except Exception as e:
            duration = time.perf_counter() - step_start
            logger.error(f"❌ {step_name} failed after {duration:.2f}s: {str(e)}")
            self.timings[step_name] = duration
            raise
    
    async def profile_imports(self):
        """Profile import times"""
        logger.info("📦 Profiling import performance...")
        
        # Test core imports
        self.time_step("Import FastAPI", lambda: __import__('fastapi'))
        self.time_step("Import Uvicorn", lambda: __import__('uvicorn'))
        self.time_step("Import AsyncIO", lambda: __import__('asyncio'))
        
        # Test project imports
        try:
            sys.path.insert(0, os.getcwd())
            self.time_step("Import Config Settings", self._import_config)
            self.time_step("Import Database Models", self._import_database)
            self.time_step("Import Services", self._import_services)
            self.time_step("Import API Routes", self._import_api_routes)
        except Exception as e:
            logger.error(f"Import error: {str(e)}")
    
    def _import_config(self):
        from config.settings import get_settings
        return get_settings()
    
    def _import_database(self):
        from models.database import init_db
        return init_db
    
    def _import_services(self):
        from services.logging_service import TradingLogger
        return TradingLogger()
    
    def _import_api_routes(self):
        from api import system_router, signals_router, portfolio_router
        return [system_router, signals_router, portfolio_router]
    
    async def profile_database_setup(self):
        """Profile database initialization"""
        logger.info("🗄️ Profiling database setup...")
        
        try:
            from models.database import init_db
            await self.time_step("Database Initialization", init_db)
        except Exception as e:
            logger.error(f"Database setup failed: {str(e)}")
    
    async def profile_services_init(self):
        """Profile service initialization"""
        logger.info("🔧 Profiling service initialization...")
        
        try:
            # Test logging service
            def init_logging():
                from services.logging_service import TradingLogger
                return TradingLogger()
            
            self.time_step("Logging Service Init", init_logging)
            
            # Test IIFL API service
            def init_iifl():
                from services.iifl_api import IIFLAPIService
                return IIFLAPIService()
            
            self.time_step("IIFL API Service Init", init_iifl)
            
        except Exception as e:
            logger.error(f"Service initialization failed: {str(e)}")
    
    async def profile_scheduler_init(self):
        """Profile scheduler initialization"""
        logger.info("📅 Profiling scheduler initialization...")
        
        try:
            def init_scheduler():
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                return AsyncIOScheduler()
            
            self.time_step("Scheduler Creation", init_scheduler)
            
        except Exception as e:
            logger.error(f"Scheduler initialization failed: {str(e)}")
    
    def check_file_system(self):
        """Check file system performance"""
        logger.info("📁 Checking file system performance...")
        
        # Test directory creation
        test_dir = Path("logs/profiler_test")
        start = time.perf_counter()
        test_dir.mkdir(parents=True, exist_ok=True)
        dir_time = time.perf_counter() - start
        
        # Test file write
        test_file = test_dir / "test.log"
        start = time.perf_counter()
        test_file.write_text("test")
        write_time = time.perf_counter() - start
        
        # Test file read
        start = time.perf_counter()
        test_file.read_text()
        read_time = time.perf_counter() - start
        
        # Cleanup
        test_file.unlink()
        test_dir.rmdir()
        
        logger.info(f"📁 Directory creation: {dir_time:.4f}s")
        logger.info(f"✏️ File write: {write_time:.4f}s")
        logger.info(f"📖 File read: {read_time:.4f}s")
        
        if write_time > 0.1:
            logger.warning("⚠️ Slow file system performance detected")
    
    def check_environment(self):
        """Check environment configuration"""
        logger.info("🌍 Checking environment configuration...")
        
        # Check .env file
        env_file = Path(".env")
        if env_file.exists():
            size = env_file.stat().st_size
            logger.info(f"📄 .env file size: {size} bytes")
            if size > 10000:
                logger.warning("⚠️ Large .env file may slow startup")
        else:
            logger.warning("⚠️ No .env file found")
        
        # Check Python path
        logger.info(f"🐍 Python executable: {sys.executable}")
        logger.info(f"📁 Working directory: {os.getcwd()}")
        logger.info(f"📦 Python path entries: {len(sys.path)}")
        
        # Check memory usage
        try:
            import psutil
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            logger.info(f"💾 Memory usage: {memory_mb:.1f} MB")
        except ImportError:
            logger.info("💾 Memory info unavailable (psutil not installed)")
    
    async def run_full_profile(self):
        """Run complete startup profiling"""
        logger.info("🚀 Starting comprehensive startup profiling...")
        logger.info("=" * 60)
        
        # Environment checks
        await self.time_step("Environment Check", self.check_environment)
        await self.time_step("File System Check", self.check_file_system)
        
        # Import profiling
        await self.time_step("Import Profiling", self.profile_imports)
        
        # Component profiling
        await self.time_step("Database Profiling", self.profile_database_setup)
        await self.time_step("Services Profiling", self.profile_services_init)
        await self.time_step("Scheduler Profiling", self.profile_scheduler_init)
        
        # Summary
        total_time = time.perf_counter() - self.start_time
        logger.info("=" * 60)
        logger.info(f"🏁 Total profiling time: {total_time:.2f}s")
        logger.info("📊 TIMING BREAKDOWN:")
        
        # Sort by time
        sorted_timings = sorted(self.timings.items(), key=lambda x: x[1], reverse=True)
        for step, duration in sorted_timings:
            percentage = (duration / total_time) * 100
            logger.info(f"   {step}: {duration:.2f}s ({percentage:.1f}%)")
        
        # Recommendations
        logger.info("💡 RECOMMENDATIONS:")
        slow_steps = [(k, v) for k, v in sorted_timings if v > 1.0]
        if slow_steps:
            for step, duration in slow_steps:
                logger.warning(f"   ⚠️ Optimize {step} (currently {duration:.2f}s)")
        else:
            logger.info("   ✅ All components loading efficiently!")

async def main():
    """Main profiling entry point"""
    profiler = StartupProfiler()
    
    try:
        await profiler.run_full_profile()
        return 0
    except Exception as e:
        logger.error(f"❌ Profiling failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    print("🔍 TRADING SYSTEM STARTUP PROFILER")
    print("=" * 40)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)