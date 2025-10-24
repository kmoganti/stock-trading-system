#!/usr/bin/env python3
"""
Comprehensive Test Suite Runner for Stock Trading System
Run all tests including IIFL authentication, API tests, and system tests
"""

import asyncio
import logging
import sys
import os
import subprocess
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, '/workspaces/stock-trading-system')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_runner")

class TestRunner:
    def __init__(self):
        self.project_root = Path('/workspaces/stock-trading-system')
        self.results = {}
        
    def run_command(self, command, description, timeout=60):
        """Run a command with timeout and capture results"""
        logger.info(f"🧪 Running: {description}")
        logger.info(f"Command: {command}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.project_root,
                timeout=timeout,
                capture_output=True,
                text=True
            )
            
            success = result.returncode == 0
            self.results[description] = {
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            if success:
                logger.info(f"✅ {description} - PASSED")
            else:
                logger.error(f"❌ {description} - FAILED (exit code: {result.returncode})")
                if result.stderr:
                    logger.error(f"Error output: {result.stderr[:500]}...")
                    
            return success
            
        except subprocess.TimeoutExpired:
            logger.error(f"⏰ {description} - TIMEOUT after {timeout}s")
            self.results[description] = {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Timeout expired'
            }
            return False
        except Exception as e:
            logger.error(f"❌ {description} - ERROR: {e}")
            self.results[description] = {
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': str(e)
            }
            return False

    def run_iifl_auth_test(self):
        """Test IIFL authentication"""
        return self.run_command(
            "python -c \"import asyncio; import sys; sys.path.insert(0, '.'); from services.iifl_api import IIFLAPIService; asyncio.run(IIFLAPIService().authenticate())\"",
            "IIFL Authentication Test",
            timeout=30
        )

    def run_pytest_tests(self):
        """Run pytest test suite with organized structure"""
        logger.info("Running organized test suite...")
        
        # Run tests in logical order
        test_suites = [
            ("Unit Tests - Diagnostics", "python -m pytest tests/unit/test_diagnostics.py -v --tb=short"),
            ("Unit Tests - Database Models", "python -m pytest tests/unit/test_database_models.py -v --tb=short"),
            ("Unit Tests - Services", "python -m pytest tests/unit/test_*_service*.py -v --tb=short"),
            ("Unit Tests - API", "python -m pytest tests/unit/test_api*.py -v --tb=short"),
            ("Integration Tests", "python -m pytest tests/integration/ -v --tb=short"),
            ("Functional Tests", "python -m pytest tests/functional/ -v --tb=short"),
        ]
        
        overall_success = True
        for suite_name, command in test_suites:
            success = self.run_command(command, suite_name, timeout=120)
            if not success:
                overall_success = False
                logger.warning(f"⚠️  {suite_name} failed, continuing with other tests...")
        
        return overall_success
        
    def run_basic_import_tests(self):
        """Test basic imports"""
        return self.run_command(
            "python -c \"from config.settings import get_settings; from services.iifl_api import IIFLAPIService; from models.database import init_db; print('✅ All basic imports successful')\"",
            "Basic Import Test",
            timeout=15
        )
        
    def run_database_test(self):
        """Test database initialization"""
        return self.run_command(
            "python -c \"import asyncio; import sys; sys.path.insert(0, '.'); from models.database import init_db; asyncio.run(init_db()); print('✅ Database initialized successfully')\"",
            "Database Initialization Test",
            timeout=30
        )
        
    def run_server_startup_test(self):
        """Test server can start without hanging"""
        return self.run_command(
            "timeout 20 python -c \"import sys; sys.path.insert(0, '.'); from main import app; print('✅ Server app created successfully')\"",
            "Server Startup Test",
            timeout=25
        )
        
    def run_api_endpoint_test(self):
        """Test API endpoints if server is running"""
        # First try to start a test server
        logger.info("🚀 Starting test server...")
        server_process = None
        
        try:
            server_process = subprocess.Popen(
                ["python", "simple_server.py"],
                cwd=self.project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait a bit for server to start
            import time
            time.sleep(5)
            
            # Test health endpoint
            success = self.run_command(
                "curl -s -f http://localhost:8000/health",
                "API Health Endpoint Test",
                timeout=10
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error starting test server: {e}")
            return False
        finally:
            if server_process:
                try:
                    server_process.terminate()
                    server_process.wait(timeout=5)
                except:
                    server_process.kill()
                    
    def run_signal_generation_test(self):
        """Test signal generation"""
        return self.run_command(
            "python tests/functional/test_real_signals.py",
            "Signal Generation Test",
            timeout=30
        )
        
    def run_environment_check(self):
        """Check environment setup"""
        return self.run_command(
            "python -c \"import os; from config.settings import get_settings; s=get_settings(); print(f'Environment: {s.environment}'); print(f'IIFL Client ID: {s.iifl_client_id[:8]}...' if s.iifl_client_id else 'No IIFL Client ID'); print('✅ Environment check complete')\"",
            "Environment Configuration Check",
            timeout=10
        )
        
    def print_summary(self):
        """Print test results summary"""
        logger.info("\n" + "="*60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("="*60)
        
        passed = 0
        failed = 0
        
        for test_name, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            logger.info(f"{test_name:35} {status}")
            
            if result['success']:
                passed += 1
            else:
                failed += 1
                
        logger.info("-"*60)
        logger.info(f"Total Tests: {passed + failed}")
        logger.info(f"✅ Passed: {passed}")
        logger.info(f"❌ Failed: {failed}")
        logger.info(f"Success Rate: {(passed/(passed+failed)*100):.1f}%" if passed+failed > 0 else "0%")
        logger.info("="*60)
        
        # Print failed test details
        if failed > 0:
            logger.info("\n🔍 FAILED TEST DETAILS:")
            logger.info("-"*60)
            for test_name, result in self.results.items():
                if not result['success']:
                    logger.info(f"\n❌ {test_name}")
                    logger.info(f"   Exit Code: {result['returncode']}")
                    if result['stderr']:
                        logger.info(f"   Error: {result['stderr'][:300]}...")
                    if result['stdout']:
                        logger.info(f"   Output: {result['stdout'][:300]}...")

    def run_all_tests(self):
        """Run all tests in sequence"""
        logger.info("🚀 Starting Comprehensive Test Suite")
        logger.info("="*60)
        
        # Test sequence - ordered by dependency
        tests = [
            ("environment_check", self.run_environment_check),
            ("basic_imports", self.run_basic_import_tests),
            ("database_init", self.run_database_test),
            ("iifl_auth", self.run_iifl_auth_test),
            ("server_startup", self.run_server_startup_test),
            ("api_endpoints", self.run_api_endpoint_test),
            ("signal_generation", self.run_signal_generation_test),
            ("pytest_suite", self.run_pytest_tests),
        ]
        
        for test_id, test_func in tests:
            logger.info(f"\n🔄 Running {test_id}...")
            try:
                test_func()
            except Exception as e:
                logger.error(f"Test {test_id} crashed: {e}")
                self.results[test_id] = {
                    'success': False,
                    'returncode': -1,
                    'stdout': '',
                    'stderr': f"Test crashed: {e}"
                }
        
        self.print_summary()
        
        # Return overall success
        return all(result['success'] for result in self.results.values())

def main():
    """Main test runner function"""
    runner = TestRunner()
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "iifl":
            success = runner.run_iifl_auth_test()
        elif test_type == "pytest":
            success = runner.run_pytest_tests()
        elif test_type == "quick":
            runner.run_environment_check()
            runner.run_basic_import_tests()
            runner.run_iifl_auth_test()
            success = len([r for r in runner.results.values() if r['success']]) >= 2
        elif test_type == "api":
            success = runner.run_api_endpoint_test()
        elif test_type == "signals":
            success = runner.run_signal_generation_test()
        else:
            logger.error(f"Unknown test type: {test_type}")
            logger.info("Available test types: iifl, pytest, quick, api, signals, all")
            return 1
    else:
        # Run all tests
        success = runner.run_all_tests()
    
    runner.print_summary()
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)