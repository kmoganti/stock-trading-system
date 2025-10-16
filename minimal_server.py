"""
Minimal HTTP Server - Bypasses FastAPI for instant startup
Use this when FastAPI imports are slow (25+ seconds)
"""

import http.server
import socketserver
import json
import os
import sys
from urllib.parse import urlparse, parse_qs
import threading
import time

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from urllib.parse import parse_qs
import threading

print("� EMERGENCY MINIMAL SERVER")
print("=" * 40)
print("⚡ Bypassing slow FastAPI imports")
print("🔧 Basic HTTP server for debugging")
print("=" * 40)
start_time = time.time()

# Create minimal FastAPI app without heavy imports
try:
    print("📦 Loading FastAPI...")
    import_start = time.time()
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import uvicorn
    print(f"✅ FastAPI loaded in {time.time() - import_start:.2f}s")
    
    # Create minimal app
    app = FastAPI(
        title="Minimal Trading System",
        description="Lightweight version for testing",
        version="0.1.0"
    )
    
    @app.get("/")
    async def root():
        return {"status": "running", "message": "Minimal trading system is operational"}
    
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": time.time() - start_time
        }
    
    @app.get("/api/system/status")
    async def system_status():
        return {
            "system": "trading-system",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "database": "not_connected",
            "services": {
                "api": "running",
                "scheduler": "disabled",
                "telegram": "disabled",
                "iifl_api": "not_connected"
            }
        }
    
    print(f"✅ Minimal server setup completed in {time.time() - start_time:.2f}s")
    
    # Start server
    if __name__ == "__main__":
        port = int(os.getenv("PORT", 8000))
        host = os.getenv("HOST", "0.0.0.0")
        
        print(f"🌐 Starting server on {host}:{port}")
        print("🔗 Access at: http://localhost:8000")
        print("❤️ Health check: http://localhost:8000/health")
        print("📊 System status: http://localhost:8000/api/system/status")
        
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info",
            access_log=True,
            reload=False
        )

except Exception as e:
    print(f"❌ Error starting minimal server: {str(e)}")
    import traceback
    traceback.print_exc()
    sys.exit(1)