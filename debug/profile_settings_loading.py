#!/usr/bin/env python3
"""
Performance profiler for settings loading to identify bottlenecks
"""
import os
import time
import cProfile
import pstats
from io import StringIO

# Add the parent directory to path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def profile_settings_loading():
    """Profile the settings loading process"""
    print("🔍 Profiling settings loading...")
    
    # Create a profiler
    pr = cProfile.Profile()
    
    # Start profiling
    start_time = time.time()
    pr.enable()
    
    try:
        # Import and create settings
        from config.settings import get_settings
        settings = get_settings()
        
        # Stop profiling
        pr.disable()
        end_time = time.time()
        
        print(f"⏱️  Total loading time: {end_time - start_time:.3f} seconds")
        
        # Create a string buffer to capture stats
        s = StringIO()
        stats = pstats.Stats(pr, stream=s).sort_stats('cumulative')
        stats.print_stats()
        
        # Print the top time-consuming functions
        print("\n📊 Top time-consuming functions:")
        print("=" * 60)
        
        lines = s.getvalue().split('\n')
        for i, line in enumerate(lines):
            if 'cumulative' in line:
                # Print header and next 20 lines
                for j in range(i, min(i + 25, len(lines))):
                    print(lines[j])
                break
        
        # Analyze environment variable access
        print("\n🔧 Environment variable analysis:")
        print("=" * 60)
        
        env_vars_loaded = 0
        for key, value in os.environ.items():
            if any(prefix in key for prefix in [
                'IIFL_', 'LOG_', 'TELEGRAM_', 'TRADING_', 'RISK_',
                'MAX_', 'MIN_', 'ENABLE_', 'SECRET_', 'DATABASE_',
                'HOST', 'PORT', 'DEBUG', 'DRY_RUN', 'AUTO_TRADE'
            ]):
                env_vars_loaded += 1
        
        print(f"Trading-related environment variables found: {env_vars_loaded}")
        
        # Test individual components
        print("\n🧪 Testing individual components:")
        print("=" * 60)
        
        components = [
            ("Environment loading", lambda: os.getenv('SECRET_KEY')),
            ("Pydantic validation", lambda: settings.SECRET_KEY),
            ("Database URL", lambda: settings.DATABASE_URL),
            ("IIFL settings", lambda: settings.IIFL_CLIENT_ID),
        ]
        
        for name, func in components:
            start = time.time()
            try:
                result = func()
                end = time.time()
                print(f"{name:20} {end-start:8.3f}s - {'✅' if result else '❌'}")
            except Exception as e:
                end = time.time()
                print(f"{name:20} {end-start:8.3f}s - ❌ Error: {str(e)[:50]}")
        
    except Exception as e:
        pr.disable()
        print(f"❌ Error during profiling: {e}")
        import traceback
        traceback.print_exc()

def test_env_file_loading():
    """Test .env file loading specifically"""
    print("\n📁 Testing .env file loading:")
    print("=" * 60)
    
    env_file = ".env"
    if os.path.exists(env_file):
        start_time = time.time()
        
        # Count lines in .env file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        non_empty_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
        
        end_time = time.time()
        
        print(f"📄 .env file size: {len(lines)} total lines, {len(non_empty_lines)} config lines")
        print(f"⏱️  File read time: {end_time - start_time:.3f} seconds")
        
        # Test dotenv loading
        try:
            from dotenv import load_dotenv
            start_time = time.time()
            load_dotenv()
            end_time = time.time()
            print(f"⏱️  dotenv loading time: {end_time - start_time:.3f} seconds")
        except ImportError:
            print("❌ python-dotenv not available")
    else:
        print("❌ No .env file found")

def benchmark_alternative_approaches():
    """Benchmark different approaches to settings loading"""
    print("\n🏃 Benchmarking alternative approaches:")
    print("=" * 60)
    
    approaches = []
    
    # Standard approach
    def standard_approach():
        from config.settings import get_settings
        return get_settings()
    
    # Direct os.getenv approach
    def direct_getenv():
        config = {}
        config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default')
        config['HOST'] = os.getenv('HOST', '0.0.0.0')
        config['PORT'] = int(os.getenv('PORT', '8000'))
        config['DEBUG'] = os.getenv('DEBUG', 'false').lower() == 'true'
        return config
    
    approaches = [
        ("Standard settings.py", standard_approach),
        ("Direct os.getenv", direct_getenv),
    ]
    
    for name, func in approaches:
        times = []
        for _ in range(3):  # Run 3 times for average
            start = time.time()
            try:
                result = func()
                end = time.time()
                times.append(end - start)
            except Exception as e:
                print(f"{name:25} ❌ Error: {str(e)[:50]}")
                break
        else:
            avg_time = sum(times) / len(times)
            print(f"{name:25} {avg_time:8.3f}s (avg of {len(times)} runs)")

if __name__ == "__main__":
    print("🚀 Settings Loading Performance Analysis")
    print("=" * 80)
    
    test_env_file_loading()
    profile_settings_loading()
    benchmark_alternative_approaches()
    
    print("\n💡 Recommendations:")
    print("=" * 60)
    print("1. Check for large .env files or complex validation")
    print("2. Consider lazy loading for non-critical settings")
    print("3. Cache settings objects to avoid reloading")
    print("4. Use minimal settings for development")
    print("5. Profile with 'python -m cProfile your_script.py'")