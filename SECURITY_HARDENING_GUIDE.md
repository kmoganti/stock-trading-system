# 🔒 SECURITY HARDENING GUIDE FOR PRODUCTION DEPLOYMENT

## 🚨 CRITICAL SECURITY MEASURES

This document outlines all security hardening steps required before production deployment of your algorithmic trading system.

---

## 1. 🔐 CRYPTOGRAPHIC SECURITY

### **A. Secure Key Generation**
```bash
# Generated cryptographically secure keys (REPLACE THESE IN PRODUCTION):
SECRET_KEY=cKJXQppexMjDOkx30qSJt0_SnkoPNIF5OFxdJwBUivU
API_SECRET_KEY=l8t-LwUEC7US2x6PdCPzhEdrYPBuEQJaYN1w7zfIVY8

# Add to your .env.production file:
echo "SECRET_KEY=cKJXQppexMjDOkx30qSJt0_SnkoPNIF5OFxdJwBUivU" >> .env.production
echo "API_SECRET_KEY=l8t-LwUEC7US2x6PdCPzhEdrYPBuEQJaYN1w7zfIVY8" >> .env.production
```

### **B. Key Rotation Policy**
- **Rotate keys every 90 days** for maximum security
- **Store backup keys** securely for emergency access
- **Use environment variables** - never hardcode in source

---

## 2. 🌐 HTTPS & SSL/TLS CONFIGURATION

### **A. SSL Certificate Setup**
```nginx
# nginx SSL configuration (included in docker-compose.yml)
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_private_key /etc/nginx/ssl/private.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    
    location / {
        proxy_pass http://trading-system:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Force HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

### **B. Generate SSL Certificate**
```bash
# Option 1: Let's Encrypt (FREE - Recommended)
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com

# Option 2: Self-signed for testing
openssl req -x509 -newkey rsa:4096 -keyout private.key -out cert.pem -days 365 -nodes
```

---

## 3. 🚪 ACCESS CONTROL & AUTHENTICATION

### **A. API Key Authentication**
```python
# Secure API endpoints with X-API-Key header
from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    settings = get_settings()
    if settings.api_secret_key and api_key_header == settings.api_secret_key:
        return api_key_header
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key"
        )

# Usage in endpoints:
@app.get("/api/protected-endpoint")
async def protected_endpoint(api_key: str = Depends(get_api_key)):
    return {"message": "Access granted"}
```

### **B. Session Management**
```python
# Secure session configuration
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site='strict',
    https_only=True,  # HTTPS only in production
    max_age=1800     # 30 minutes session timeout
)
```

---

## 4. 🛡️ RATE LIMITING & DOS PROTECTION

### **A. Request Rate Limiting**
```python
# Add to main.py - Rate limiting middleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply rate limits to sensitive endpoints
@app.post("/api/auth/login")
@limiter.limit("5/minute")  # 5 attempts per minute
async def login(request: Request):
    pass

@app.get("/api/signals/generate")  
@limiter.limit("10/minute")  # 10 signal requests per minute
async def generate_signals(request: Request):
    pass

@app.post("/api/orders/place")
@limiter.limit("60/minute")  # 60 orders per minute max
async def place_order(request: Request):
    pass
```

### **B. NGINX Rate Limiting**
```nginx
# Add to nginx.conf
http {
    # Rate limiting zones
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/m;
    limit_req_zone $binary_remote_addr zone=api:10m rate=100r/m;
    limit_req_zone $binary_remote_addr zone=orders:10m rate=60r/m;
    
    server {
        # Apply rate limits
        location /api/auth/ {
            limit_req zone=auth burst=2 nodelay;
            proxy_pass http://trading-system:8000;
        }
        
        location /api/orders/ {
            limit_req zone=orders burst=10 nodelay;
            proxy_pass http://trading-system:8000;
        }
        
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://trading-system:8000;
        }
    }
}
```

---

## 5. 🌍 CORS & ORIGIN RESTRICTIONS

### **A. Production CORS Configuration**
```python
# Restrict CORS to specific domains in production
from fastapi.middleware.cors import CORSMiddleware

if settings.environment == "production":
    allowed_origins = [
        "https://yourdomain.com",
        "https://trading.yourdomain.com"
    ]
else:
    allowed_origins = ["http://localhost:8000", "http://127.0.0.1:8000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 6. 🔍 DEBUG & DOCUMENTATION SECURITY

### **A. Disable Debug Features in Production**
```python
# Add to main.py - Disable debug endpoints
if settings.environment == "production":
    app.docs_url = None        # Disable /docs
    app.redoc_url = None       # Disable /redoc  
    app.openapi_url = None     # Disable /openapi.json
    
# Also set in .env.production:
DEBUG=false
LOG_LEVEL=INFO
LOG_CONSOLE_ENABLED=false
```

### **B. Remove Development Tools**
```python
# Remove or secure development endpoints
# Comment out or remove these in production:

# @app.get("/debug/auth")  # Remove debug endpoints
# @app.get("/debug/market-data")  # Remove debug endpoints

# Or secure them with authentication:
@app.get("/debug/system", dependencies=[Depends(get_api_key)])
async def debug_system_info():
    if settings.environment != "production":
        return {"system": "debug info"}
    else:
        raise HTTPException(404, "Not Found")
```

---

## 7. 📁 FILE SYSTEM SECURITY

### **A. Secure File Permissions**
```bash
# Set secure file permissions
chmod 600 .env.production      # Only owner can read/write
chmod 600 trading_system.db    # Secure database file
chmod 755 logs/                # Directory readable, files protected
chmod 644 logs/*.log           # Log files readable by owner and group
chmod 700 /app/ssl/            # SSL directory - owner only
chmod 600 /app/ssl/*.key       # Private keys - owner only
```

### **B. Environment File Security**
```bash
# Never commit .env files to version control
echo ".env*" >> .gitignore
echo "*.key" >> .gitignore
echo "*.pem" >> .gitignore

# Secure environment file location
sudo mkdir -p /etc/trading-system
sudo cp .env.production /etc/trading-system/.env
sudo chown root:trading-group /etc/trading-system/.env
sudo chmod 640 /etc/trading-system/.env
```

---

## 8. 🛡️ INPUT VALIDATION & SANITIZATION

### **A. Pydantic Model Validation**
```python
# Strict input validation for trading parameters
from pydantic import BaseModel, validator, Field
from decimal import Decimal

class TradingOrderRequest(BaseModel):
    symbol: str = Field(..., regex="^[A-Z]{1,12}$")  # Valid stock symbols only
    quantity: int = Field(..., gt=0, le=10000)       # Positive, max 10K shares
    price: Decimal = Field(..., gt=0, le=100000)     # Positive, reasonable price
    order_type: str = Field(..., regex="^(BUY|SELL)$")
    
    @validator('symbol')
    def validate_symbol(cls, v):
        # Additional symbol validation
        if len(v) < 2:
            raise ValueError('Symbol too short')
        return v.upper()
```

### **B. SQL Injection Prevention**
```python
# Use SQLAlchemy parameterized queries (already implemented)
# Never use string formatting for SQL queries

# Good (already in your code):
query = select(Signal).where(Signal.symbol == symbol)

# Bad (never do this):
# query = f"SELECT * FROM signals WHERE symbol = '{symbol}'"
```

---

## 9. 🔐 DATABASE SECURITY

### **A. Database Connection Security**
```python
# Secure database configuration
DATABASE_URL = "sqlite+aiosqlite:///./trading_system.db"

# For PostgreSQL in production:
# DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/trading_db?sslmode=require"

# Connection pool security
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Disable SQL logging in production
    pool_pre_ping=True,
    pool_recycle=3600,  # Recycle connections hourly
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
```

### **B. Database Encryption**
```bash
# Enable SQLite encryption (if using SQLCipher)
pip install sqlcipher3-binary

# Set encryption key
PRAGMA key = 'your-encryption-key';

# For sensitive production data, consider PostgreSQL with TDE
```

---

## 10. 📊 SECURITY MONITORING

### **A. Security Event Logging**
```python
# Enhanced security logging
import logging

security_logger = logging.getLogger("security")

async def log_security_event(event_type: str, details: dict, request: Request):
    security_logger.warning({
        "event": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "ip_address": request.client.host,
        "user_agent": request.headers.get("user-agent"),
        "details": details
    })

# Log failed authentication attempts
@app.post("/api/auth/login")
async def login(request: Request, credentials: LoginRequest):
    try:
        # Authentication logic
        pass
    except AuthenticationError:
        await log_security_event("AUTH_FAILURE", {
            "username": credentials.username,
            "reason": "invalid_credentials"
        }, request)
        raise HTTPException(401, "Authentication failed")
```

### **B. Intrusion Detection**
```python
# Monitor suspicious activity
from collections import defaultdict
from datetime import datetime, timedelta

failed_attempts = defaultdict(list)

async def check_brute_force(ip_address: str):
    now = datetime.utcnow()
    # Clean old attempts
    failed_attempts[ip_address] = [
        attempt for attempt in failed_attempts[ip_address]
        if now - attempt < timedelta(minutes=15)
    ]
    
    # Check if too many recent failures
    if len(failed_attempts[ip_address]) >= 5:
        await log_security_event("BRUTE_FORCE_DETECTED", {
            "ip_address": ip_address,
            "attempts": len(failed_attempts[ip_address])
        })
        return True
    return False
```

---

## 11. 🔄 SECURE DEPLOYMENT PRACTICES

### **A. Container Security**
```dockerfile
# Secure Dockerfile practices
FROM python:3.11-slim

# Create non-root user
RUN groupadd -r trading && useradd -r -g trading trading

# Set working directory
WORKDIR /app

# Install dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .
RUN chown -R trading:trading /app

# Switch to non-root user
USER trading

# Remove unnecessary packages
RUN apt-get remove -y gcc g++ && apt-get autoremove -y

# Set security options
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000
CMD ["python", "run.py"]
```

### **B. Docker Security Configuration**
```yaml
# Secure docker-compose.yml
version: '3.8'
services:
  trading-system:
    build: .
    ports:
      - "127.0.0.1:8000:8000"  # Bind to localhost only
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./trading.db
      - ENVIRONMENT=production
    volumes:
      - ./data:/app/data:rw
      - ./logs:/app/logs:rw
    restart: unless-stopped
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - SETUID
      - SETGID
    read_only: true
    tmpfs:
      - /tmp:rw,size=100M
```

---

## 12. ⚠️ CRITICAL SECURITY CHECKLIST

### **Before Production Deployment:**

- [ ] **✅ Strong secrets generated** and stored securely
- [ ] **✅ HTTPS configured** with valid SSL certificate  
- [ ] **✅ API key authentication** enabled on all endpoints
- [ ] **✅ Rate limiting** configured for all public endpoints
- [ ] **✅ CORS restricted** to specific production domains
- [ ] **✅ Debug endpoints disabled** in production
- [ ] **✅ File permissions** set securely (600/644/755)
- [ ] **✅ Database connections** secured and encrypted
- [ ] **✅ Security logging** enabled for all auth events
- [ ] **✅ Container security** configured with non-root user
- [ ] **✅ Environment variables** secured and not in git
- [ ] **✅ Input validation** implemented for all endpoints

---

## 🚨 EMERGENCY SECURITY PROCEDURES

### **A. Security Incident Response**
```bash
# 1. Immediate response
sudo systemctl stop trading-system  # Stop the service
sudo iptables -A INPUT -s MALICIOUS_IP -j DROP  # Block IP

# 2. Assessment
grep "MALICIOUS_IP" /var/log/nginx/access.log
grep "AUTH_FAILURE" logs/security.log

# 3. Recovery
# Rotate all keys
# Update firewall rules
# Patch vulnerabilities
# Restart service
```

### **B. Key Rotation Procedure**
```bash
# Generate new keys
python -c "import secrets; print(f'SECRET_KEY={secrets.token_urlsafe(32)}')"
python -c "import secrets; print(f'API_SECRET_KEY={secrets.token_urlsafe(32)}')"

# Update .env.production
# Restart services
sudo systemctl restart trading-system
```

---

This comprehensive security hardening guide ensures your algorithmic trading system is **production-ready** with **enterprise-grade security** measures! 🔒✅