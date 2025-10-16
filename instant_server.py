#!/usr/bin/env python3
"""
INSTANT HTTP SERVER - No dependencies, starts in seconds
For emergency access to your trading system when FastAPI is broken
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from urllib.parse import parse_qs, urlparse
import webbrowser
import time

class TradingHandler(SimpleHTTPRequestHandler):
    """Minimal HTTP handler for trading system access"""
    
    def do_GET(self):
        """Handle GET requests"""
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.send_dashboard()
        elif parsed.path == '/health':
            self.send_health()
        elif parsed.path == '/status':
            self.send_status()
        elif parsed.path.startswith('/api/'):
            self.send_api_response()
        else:
            # Serve static files
            super().do_GET()
    
    def send_dashboard(self):
        """Send a simple dashboard"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Trading System - Emergency Access</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; }}
        .status {{ background: #27ae60; color: white; padding: 10px; margin: 10px 0; border-radius: 3px; }}
        .warning {{ background: #f39c12; color: white; padding: 10px; margin: 10px 0; border-radius: 3px; }}
        .card {{ background: white; padding: 20px; margin: 10px 0; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .btn {{ background: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 3px; display: inline-block; margin: 5px; }}
        .btn:hover {{ background: #2980b9; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Stock Trading System - Emergency Access</h1>
        <p>Server Time: {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="status">
        ✅ Emergency server running successfully!
    </div>
    
    <div class="warning">
        ⚠️ This is a minimal server. Full FastAPI server has startup issues.
    </div>
    
    <div class="card">
        <h2>🔧 Quick Actions</h2>
        <a href="/health" class="btn">Health Check</a>
        <a href="/status" class="btn">System Status</a>
        <a href="#" onclick="location.reload()" class="btn">Refresh</a>
    </div>
    
    <div class="card">
        <h2>📊 System Information</h2>
        <ul>
            <li><strong>Environment:</strong> {os.getenv('ENVIRONMENT', 'development')}</li>
            <li><strong>Database:</strong> {os.path.exists('trading_system.db') and 'Connected' or 'Not Found'}</li>
            <li><strong>Port:</strong> 8080</li>
            <li><strong>Status:</strong> Emergency Mode</li>
        </ul>
    </div>
    
    <div class="card">
        <h2>🛠️ Fix FastAPI Issue</h2>
        <p>To fix the slow FastAPI startup, run these commands in order:</p>
        <pre style="background: #f8f9fa; padding: 15px; border-radius: 3px;">
pip uninstall fastapi uvicorn -y
pip install --no-cache-dir fastapi uvicorn
python -c "import fastapi; print('FastAPI OK')"
        </pre>
    </div>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def send_health(self):
        """Send health check response"""
        health_data = {
            "status": "ok",
            "timestamp": time.time(),
            "server": "emergency",
            "database": os.path.exists('trading_system.db'),
            "environment": os.getenv('ENVIRONMENT', 'development')
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(health_data, indent=2).encode())
    
    def send_status(self):
        """Send system status"""
        try:
            db_size = os.path.getsize('trading_system.db') if os.path.exists('trading_system.db') else 0
        except:
            db_size = 0
            
        status_data = {
            "system": "trading_system",
            "version": "emergency_mode",
            "uptime": time.time() - start_time,
            "database_size_bytes": db_size,
            "log_files": len([f for f in os.listdir('logs') if f.endswith('.log')]) if os.path.exists('logs') else 0,
            "message": "FastAPI server has startup issues. Using emergency HTTP server."
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(status_data, indent=2).encode())
    
    def send_api_response(self):
        """Send API response"""
        api_response = {
            "error": "FastAPI server unavailable",
            "message": "API endpoints require full server restart",
            "suggestion": "Please fix FastAPI installation and restart main server"
        }
        
        self.send_response(503)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(api_response, indent=2).encode())

def main():
    """Start the instant server"""
    global start_time
    start_time = time.time()
    
    port = 8080
    server = HTTPServer(('localhost', port), TradingHandler)
    
    print(f"🚀 INSTANT TRADING SYSTEM SERVER")
    print(f"⚡ Started in {time.time() - start_time:.2f} seconds")
    print(f"🌐 Open: http://localhost:{port}")
    print(f"📊 Health: http://localhost:{port}/health")
    print(f"🔧 Status: http://localhost:{port}/status")
    print("=" * 50)
    print("Press Ctrl+C to stop")
    
    # Auto-open browser
    try:
        webbrowser.open(f'http://localhost:{port}')
    except:
        pass
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        server.server_close()

if __name__ == "__main__":
    main()