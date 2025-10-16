"""
Security Middleware for Production Deployment

This module provides comprehensive security middleware including:
- Rate limiting
- API key authentication  
- Security headers
- Request validation
- CORS protection
"""

from fastapi import FastAPI, Request, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import time
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# API Key Security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key for secure endpoints."""
    if settings.api_secret_key and api_key_header == settings.api_secret_key:
        return api_key_header
    else:
        logger.warning(f"Invalid API key attempt from {api_key_header[:8]}...")
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API Key"
        )

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        if settings.environment == "production":
            response.headers["Strict-Transport-Security"] = f"max-age={settings.hsts_max_age}; includeSubDomains"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["X-XSS-Protection"] = "1; mode=block"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            
            if hasattr(settings, 'content_security_policy'):
                response.headers["Content-Security-Policy"] = settings.content_security_policy
        
        return response

class BruteForceProtectionMiddleware(BaseHTTPMiddleware):
    """Protect against brute force attacks."""
    
    def __init__(self, app, max_attempts: int = 5, window_minutes: int = 15):
        super().__init__(app)
        self.max_attempts = max_attempts
        self.window_minutes = window_minutes
        self.failed_attempts = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next):
        client_ip = get_remote_address(request)
        
        # Check if IP is blocked
        if self._is_blocked(client_ip):
            logger.warning(f"Blocked request from {client_ip} - too many failed attempts")
            raise HTTPException(
                status_code=429,
                detail="Too many failed attempts. Please try again later."
            )
        
        response = await call_next(request)
        
        # Track failed authentication attempts
        if response.status_code == 401 and request.url.path.startswith("/api/auth/"):
            self._record_failed_attempt(client_ip)
        
        return response
    
    def _is_blocked(self, ip: str) -> bool:
        """Check if IP should be blocked due to too many failed attempts."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=self.window_minutes)
        
        # Clean old attempts
        self.failed_attempts[ip] = [
            attempt for attempt in self.failed_attempts[ip]
            if attempt > cutoff
        ]
        
        return len(self.failed_attempts[ip]) >= self.max_attempts
    
    def _record_failed_attempt(self, ip: str) -> None:
        """Record a failed authentication attempt."""
        self.failed_attempts[ip].append(datetime.utcnow())

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests for security monitoring."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = get_remote_address(request)
        user_agent = request.headers.get("user-agent", "Unknown")
        
        # Log sensitive endpoint access
        sensitive_paths = ["/api/auth/", "/api/orders/", "/api/admin/"]
        is_sensitive = any(request.url.path.startswith(path) for path in sensitive_paths)
        
        if is_sensitive:
            logger.info(f"Sensitive endpoint access: {request.method} {request.url.path} from {client_ip}")
        
        response = await call_next(request)
        
        # Log response details
        process_time = time.time() - start_time
        
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
            "user_agent": user_agent,
            "process_time": round(process_time, 3),
            "is_sensitive": is_sensitive
        }
        
        if response.status_code >= 400:
            logger.warning(f"HTTP {response.status_code}: {log_data}")
        elif is_sensitive:
            logger.info(f"Sensitive request completed: {log_data}")
        
        return response

def setup_security_middleware(app: FastAPI) -> None:
    """Configure all security middleware for the application."""
    
    # Session middleware with secure settings
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        same_site='strict' if settings.environment == "production" else 'lax',
        https_only=settings.environment == "production",
        max_age=getattr(settings, 'session_max_age', 1800)
    )
    
    # CORS middleware with restricted origins
    allowed_origins = getattr(settings, 'allowed_origins', [])
    if isinstance(allowed_origins, str):
        allowed_origins = [origin.strip() for origin in allowed_origins.split(',')]
    
    if settings.environment != "production":
        allowed_origins.extend(["http://localhost:8000", "http://127.0.0.1:8000"])
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=getattr(settings, 'cors_allow_credentials', True),
        allow_methods=getattr(settings, 'cors_allow_methods', "GET,POST,PUT,DELETE").split(','),
        allow_headers=["*"],
        max_age=getattr(settings, 'cors_max_age', 3600)
    )
    
    # Trusted host middleware
    if settings.environment == "production" and allowed_origins:
        trusted_hosts = [origin.replace("https://", "").replace("http://", "") 
                        for origin in allowed_origins]
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
    
    # Custom security middleware
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    
    if getattr(settings, 'brute_force_protection_enabled', True):
        app.add_middleware(BruteForceProtectionMiddleware)
    
    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    logger.info("🛡️ Security middleware configured successfully")

# Rate limiting decorators for specific endpoints
def rate_limit_auth(func):
    """Rate limit authentication endpoints."""
    return limiter.limit("5/minute")(func)

def rate_limit_api(func):
    """Rate limit general API endpoints.""" 
    return limiter.limit("100/minute")(func)

def rate_limit_orders(func):
    """Rate limit order placement endpoints."""
    return limiter.limit("60/minute")(func)

# Security dependencies
async def require_api_key(api_key: str = Depends(get_api_key)) -> str:
    """Dependency that requires valid API key."""
    return api_key

async def require_admin_key(request: Request) -> None:
    """Dependency that requires admin-level access."""
    api_key = request.headers.get("X-Admin-Key")
    if not api_key or api_key != getattr(settings, 'admin_api_key', ''):
        logger.warning(f"Unauthorized admin access attempt from {get_remote_address(request)}")
        raise HTTPException(403, "Admin access required")
