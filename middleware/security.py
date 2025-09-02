"""
Security middleware for DPAR (Dynamic Policy and Access Rules)
This module implements security policies and access control for the API.
"""

import time
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import hmac
import base64
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import structlog

logger = structlog.get_logger()

class RateLimiter:
    """Rate limiting implementation"""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.blocked_ips: set = set()
    
    def is_allowed(self, client_ip: str, endpoint: str, limit: int, window_seconds: int) -> bool:
        """Check if request is allowed based on rate limits"""
        key = f"{client_ip}:{endpoint}"
        now = time.time()
        
        # Clean old requests
        while self.requests[key] and self.requests[key][0] < now - window_seconds:
            self.requests[key].popleft()
        
        # Check if limit exceeded
        if len(self.requests[key]) >= limit:
            logger.warning(
                "Rate limit exceeded",
                client_ip=client_ip,
                endpoint=endpoint,
                limit=limit,
                window=window_seconds
            )
            return False
        
        # Add current request
        self.requests[key].append(now)
        return True
    
    def block_ip(self, ip: str, duration_minutes: int = 60):
        """Block an IP address temporarily"""
        self.blocked_ips.add(ip)
        logger.warning("IP blocked", ip=ip, duration_minutes=duration_minutes)
    
    def is_ip_blocked(self, ip: str) -> bool:
        """Check if IP is blocked"""
        return ip in self.blocked_ips

class APIKeyValidator:
    """API key validation"""
    
    def __init__(self, valid_keys: Dict[str, Dict]):
        self.valid_keys = valid_keys
    
    def validate_key(self, api_key: str) -> Tuple[bool, Optional[Dict]]:
        """Validate API key and return permissions"""
        if api_key in self.valid_keys:
            return True, self.valid_keys[api_key]
        return False, None
    
    def has_permission(self, api_key: str, permission: str) -> bool:
        """Check if API key has specific permission"""
        is_valid, key_info = self.validate_key(api_key)
        if not is_valid or not key_info:
            return False
        
        permissions = key_info.get('permissions', [])
        return permission in permissions

class SecurityMiddleware:
    """Main security middleware class"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.api_key_validator = APIKeyValidator(self._load_api_keys())
        self.policies = self._load_policies()
    
    def _load_api_keys(self) -> Dict[str, Dict]:
        """Load API keys from environment or configuration"""
        # In production, load from Azure Key Vault or secure storage
        return {
            "dev-api-key-123": {
                "permissions": ["events:create", "events:batch"],
                "rate_limits": {
                    "/events": {"limit": 100, "window": 60},
                    "/events/batch": {"limit": 10, "window": 60}
                }
            },
            "monitoring-key-456": {
                "permissions": ["health:read", "metrics:read"],
                "rate_limits": {
                    "/health": {"limit": 1000, "window": 60}
                }
            }
        }
    
    def _load_policies(self) -> Dict:
        """Load security policies"""
        return {
            "rate_limits": {
                "/events": {"limit": 100, "window": 60, "burst": 20},
                "/events/batch": {"limit": 10, "window": 60, "burst": 5},
                "/health": {"limit": 1000, "window": 60}
            },
            "auth_required": {
                "/events": True,
                "/events/batch": True,
                "/health": False
            },
            "max_payload_size": {
                "/events": 1024 * 1024,  # 1MB
                "/events/batch": 10 * 1024 * 1024  # 10MB
            }
        }
    
    async def validate_request(self, request: Request) -> Tuple[bool, Optional[str]]:
        """Validate incoming request against security policies"""
        client_ip = request.client.host
        path = request.url.path
        method = request.method
        
        # Check if IP is blocked
        if self.rate_limiter.is_ip_blocked(client_ip):
            logger.warning("Request from blocked IP", ip=client_ip, path=path)
            return False, "IP address is blocked"
        
        # Check rate limits
        rate_limit_config = self.policies["rate_limits"].get(path)
        if rate_limit_config:
            if not self.rate_limiter.is_allowed(
                client_ip, path, 
                rate_limit_config["limit"], 
                rate_limit_config["window"]
            ):
                # Block IP if rate limit exceeded multiple times
                self.rate_limiter.block_ip(client_ip, 60)
                return False, "Rate limit exceeded"
        
        # Check authentication
        auth_required = self.policies["auth_required"].get(path, False)
        if auth_required:
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
            if not api_key:
                logger.warning("Missing API key", ip=client_ip, path=path)
                return False, "API key required"
            
            # Remove "Bearer " prefix if present
            if api_key.startswith("Bearer "):
                api_key = api_key[7:]
            
            is_valid, key_info = self.api_key_validator.validate_key(api_key)
            if not is_valid:
                logger.warning("Invalid API key", ip=client_ip, path=path)
                return False, "Invalid API key"
            
            # Check endpoint-specific permissions
            if path == "/events" and not self.api_key_validator.has_permission(api_key, "events:create"):
                return False, "Insufficient permissions"
            elif path == "/events/batch" and not self.api_key_validator.has_permission(api_key, "events:batch"):
                return False, "Insufficient permissions"
        
        # Check payload size
        content_length = request.headers.get("content-length")
        if content_length:
            max_size = self.policies["max_payload_size"].get(path)
            if max_size and int(content_length) > max_size:
                logger.warning("Payload too large", ip=client_ip, path=path, size=content_length)
                return False, "Payload too large"
        
        return True, None
    
    def generate_api_key(self, permissions: List[str], expires_days: int = 365) -> str:
        """Generate a new API key"""
        timestamp = str(int(time.time()))
        data = f"{timestamp}:{':'.join(permissions)}"
        key = hmac.new(
            b"secret-key-change-in-production",  # Use secure key in production
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"api-{timestamp}-{key[:16]}"

# Global security middleware instance
security_middleware = SecurityMiddleware()

async def security_check(request: Request, call_next):
    """FastAPI middleware for security checks"""
    is_valid, error_message = await security_middleware.validate_request(request)
    
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS if "rate limit" in error_message.lower() 
                       else status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Security validation failed",
                "message": error_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    response = await call_next(request)
    
    # Add security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response
