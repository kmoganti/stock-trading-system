#!/usr/bin/env python3
"""
Simple server startup for debugging - bypasses complex initialization
"""

import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app with minimal configuration
app = FastAPI(
    title="Stock Trading System - Simple Mode",
    description="Simplified version for debugging",
    version="1.0.0-simple"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories if they don't exist
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Root endpoint"""
    return """
    <html>
        <head>
            <title>Stock Trading System - Simple Mode</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; }
                .container { max-width: 800px; margin: 0 auto; }
                .status { background: #e8f5e8; padding: 20px; border-radius: 5px; margin: 20px 0; }
                .endpoints { background: #f0f0f0; padding: 20px; border-radius: 5px; }
                h1 { color: #2c3e50; }
                h2 { color: #34495e; }
                ul { line-height: 1.6; }
                .success { color: #27ae60; font-weight: bold; }
                a { color: #3498db; text-decoration: none; }
                a:hover { text-decoration: underline; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🚀 Stock Trading System</h1>
                <div class="status">
                    <h2>✅ Server Status</h2>
                    <p class="success">Server is running successfully in simple mode!</p>
                    <p>This is a simplified version that bypasses complex initialization to help with debugging.</p>
                </div>
                
                <div class="endpoints">
                    <h2>📋 Available Endpoints</h2>
                    <ul>
                        <li><a href="/health">🔍 Health Check</a></li>
                        <li><a href="/docs">📚 API Documentation (Swagger)</a></li>
                        <li><a href="/redoc">📖 API Documentation (ReDoc)</a></li>
                        <li><a href="/system/status">⚙️ System Status</a></li>
                    </ul>
                </div>
                
                <div class="endpoints">
                    <h2>🛠️ Debug Information</h2>
                    <ul>
                        <li><strong>Mode:</strong> Simple/Debug</li>
                        <li><strong>Environment:</strong> Development</li>
                        <li><strong>Host:</strong> 0.0.0.0</li>
                        <li><strong>Port:</strong> 8000</li>
                    </ul>
                </div>
            </div>
        </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "mode": "simple",
        "message": "Server is running in simple mode",
        "timestamp": "2025-10-16T06:10:00Z"
    }

@app.get("/system/status")
async def system_status():
    """System status endpoint"""
    return {
        "server": "running",
        "mode": "simple",
        "version": "1.0.0-simple",
        "environment": "development",
        "debug": True,
        "features": {
            "database": "disabled",
            "iifl_api": "disabled", 
            "telegram": "disabled",
            "scheduler": "disabled",
            "market_stream": "disabled"
        }
    }

@app.get("/dashboard")
async def dashboard_redirect():
    """Redirect dashboard to root"""
    return {"message": "Dashboard available at /", "redirect": "/"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Stock Trading System in Simple Mode...")
    print("📍 Server will be available at: http://localhost:8000")
    print("📚 API Documentation at: http://localhost:8000/docs")
    print("=" * 60)
    
    uvicorn.run(
        "simple_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True
    )