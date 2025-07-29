# Authentication and authorization module
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
from dotenv import load_dotenv
import secrets
import hashlib
import time
import logging
from collections import defaultdict, deque

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

# Security configuration
def generate_secure_secret_key():
    """Generate a cryptographically secure secret key"""
    return secrets.token_urlsafe(32)

def validate_secret_key(key: str) -> bool:
    """Validate that the secret key meets security requirements"""
    if not key or len(key) < 32:
        return False
    # Check if it's the insecure default
    insecure_defaults = [
        "insecure-dev-key-change-in-production",
        "your-secret-key-here",
        "changeme",
        "secret",
        "password"
    ]
    return key not in insecure_defaults

# Configuration with enhanced security
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY or not validate_secret_key(SECRET_KEY):
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError(
            "Production environment requires a secure SECRET_KEY. "
            "Please set a strong SECRET_KEY environment variable (min 32 characters)."
        )
    else:
        # Generate a secure key for development and warn
        SECRET_KEY = generate_secure_secret_key()
        logger.warning(
            "Using auto-generated SECRET_KEY for development. "
            "Set SECRET_KEY environment variable for production!"
        )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Rate limiting configuration
RATE_LIMIT_CONFIG = {
    'MAX_ATTEMPTS': int(os.getenv('AUTH_MAX_ATTEMPTS', '5')),
    'WINDOW_MINUTES': int(os.getenv('AUTH_WINDOW_MINUTES', '15')),
    'LOCKOUT_MINUTES': int(os.getenv('AUTH_LOCKOUT_MINUTES', '30'))
}

# Rate limiting implementation
class RateLimiter:
    """Simple in-memory rate limiter for authentication attempts"""
    
    def __init__(self):
        self.attempts = defaultdict(deque)  # IP -> deque of attempt timestamps
        self.lockouts = {}  # IP -> lockout_until_timestamp
    
    def _clean_old_attempts(self, ip: str):
        """Remove attempts older than the window"""
        cutoff = time.time() - (RATE_LIMIT_CONFIG['WINDOW_MINUTES'] * 60)
        while self.attempts[ip] and self.attempts[ip][0] < cutoff:
            self.attempts[ip].popleft()
    
    def is_rate_limited(self, ip: str) -> bool:
        """Check if IP is currently rate limited"""
        # Check if IP is in lockout
        if ip in self.lockouts:
            if time.time() < self.lockouts[ip]:
                return True
            else:
                # Lockout expired, remove it
                del self.lockouts[ip]
        
        # Clean old attempts
        self._clean_old_attempts(ip)
        
        # Check if too many attempts
        if len(self.attempts[ip]) >= RATE_LIMIT_CONFIG['MAX_ATTEMPTS']:
            # Put IP in lockout
            self.lockouts[ip] = time.time() + (RATE_LIMIT_CONFIG['LOCKOUT_MINUTES'] * 60)
            logger.warning(f"Rate limit exceeded for IP {ip}, locked out for {RATE_LIMIT_CONFIG['LOCKOUT_MINUTES']} minutes")
            return True
        
        return False
    
    def record_attempt(self, ip: str):
        """Record a failed authentication attempt"""
        self.attempts[ip].append(time.time())
    
    def reset_attempts(self, ip: str):
        """Reset attempts for successful authentication"""
        if ip in self.attempts:
            del self.attempts[ip]
        if ip in self.lockouts:
            del self.lockouts[ip]

# Global rate limiter instance
rate_limiter = RateLimiter()

# Enhanced user management with secure password generation
def generate_secure_password(length: int = 16) -> str:
    """Generate a cryptographically secure password"""
    return secrets.token_urlsafe(length)

def load_users_from_env():
    """Load users from environment variables or create secure defaults"""
    users = {}
    
    # Try to load admin user from environment
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@memori.local")
    
    if not admin_password:
        if os.getenv("ENVIRONMENT") == "production":
            raise ValueError(
                "Production environment requires ADMIN_PASSWORD environment variable"
            )
        else:
            # Generate secure password for development
            admin_password = generate_secure_password()
            logger.warning(
                f"Generated admin password for development: {admin_password} "
                f"(Set ADMIN_PASSWORD environment variable for production)"
            )
    
    # Create admin user
    users[admin_username] = {
        "username": admin_username,
        "full_name": "Administrator",
        "email": admin_email,
        "hashed_password": pwd_context.hash(admin_password),
        "disabled": False,
        "permissions": ["read", "write", "admin"]
    }
    
    # Try to load regular user from environment
    user_username = os.getenv("USER_USERNAME", "user")
    user_password = os.getenv("USER_PASSWORD")
    user_email = os.getenv("USER_EMAIL", "user@memori.local")
    
    if not user_password:
        if os.getenv("ENVIRONMENT") == "production":
            logger.info("No USER_PASSWORD set, skipping default user creation in production")
        else:
            # Generate secure password for development
            user_password = generate_secure_password()
            logger.warning(
                f"Generated user password for development: {user_password} "
                f"(Set USER_PASSWORD environment variable for production)"
            )
            
            # Create regular user only in development
            users[user_username] = {
                "username": user_username,
                "full_name": "Regular User",
                "email": user_email,
                "hashed_password": pwd_context.hash(user_password),
                "disabled": False,
                "permissions": ["read"]
            }
    else:
        # Create regular user with environment password
        users[user_username] = {
            "username": user_username,
            "full_name": "Regular User", 
            "email": user_email,
            "hashed_password": pwd_context.hash(user_password),
            "disabled": False,
            "permissions": ["read"]
        }
    
    return users

# Models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    permissions: Optional[list] = None

class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    permissions: list = []

class UserInDB(User):
    hashed_password: str

# Authentication tools
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Load users with secure password management
users_db = load_users_from_env()

# Helper functions with rate limiting
def get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded IP first (behind proxy)
    forwarded_ip = request.headers.get("X-Forwarded-For")
    if forwarded_ip:
        # Take the first IP in case of multiple forwards
        return forwarded_ip.split(",")[0].strip()
    
    # Check for real IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fall back to client host
    return str(request.client.host) if request.client else "unknown"

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)

def authenticate_user_with_rate_limit(request: Request, username: str, password: str):
    """Authenticate user with rate limiting protection"""
    client_ip = get_client_ip(request)
    
    # Check rate limiting
    if rate_limiter.is_rate_limited(client_ip):
        logger.warning(f"Authentication blocked due to rate limiting for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed authentication attempts. Please try again in {RATE_LIMIT_CONFIG['LOCKOUT_MINUTES']} minutes."
        )
    
    user = get_user(users_db, username)
    if not user:
        rate_limiter.record_attempt(client_ip)
        logger.warning(f"Authentication failed: user not found - {username} from IP: {client_ip}")
        return False
    
    if not verify_password(password, user.hashed_password):
        rate_limiter.record_attempt(client_ip)
        logger.warning(f"Authentication failed: wrong password for {username} from IP: {client_ip}")
        return False
    
    # Successful authentication - reset rate limiting for this IP
    rate_limiter.reset_attempts(client_ip)
    logger.info(f"Successful authentication for user: {username} from IP: {client_ip}")
    return user

# Legacy function for backward compatibility (deprecated)
def authenticate_user(fake_db, username: str, password: str):
    """
    DEPRECATED: Use authenticate_user_with_rate_limit instead.
    This function is kept for backward compatibility but doesn't include rate limiting.
    """
    logger.warning("Using deprecated authenticate_user function without rate limiting")
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token with secure key validation"""
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY not configured")
        
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current user from JWT token with enhanced validation"""
    if not SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication system not properly configured"
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    
    if token_data.username is None:
        raise credentials_exception
        
    user = get_user(users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Get current active user, ensuring they are not disabled"""
    if current_user.disabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="User account is disabled"
        )
    return current_user

# Permission checking with enhanced logging
def has_permission(required_permission: str):
    """Create a permission checker dependency"""
    async def permission_checker(current_user: User = Depends(get_current_active_user)):
        if required_permission not in current_user.permissions:
            logger.warning(
                f"Permission denied: User {current_user.username} attempted to access "
                f"resource requiring '{required_permission}' permission"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {required_permission}"
            )
        return current_user
    return permission_checker

# Security utility functions
def get_rate_limit_status(request: Request) -> Dict[str, Any]:
    """Get current rate limit status for debugging/monitoring"""
    client_ip = get_client_ip(request)
    rate_limiter._clean_old_attempts(client_ip)
    
    return {
        "ip": client_ip,
        "attempts_in_window": len(rate_limiter.attempts[client_ip]),
        "max_attempts": RATE_LIMIT_CONFIG['MAX_ATTEMPTS'],
        "is_locked_out": client_ip in rate_limiter.lockouts,
        "lockout_until": rate_limiter.lockouts.get(client_ip),
        "window_minutes": RATE_LIMIT_CONFIG['WINDOW_MINUTES']
    }

def reset_rate_limit(request: Request, admin_user: User = Depends(has_permission("admin"))):
    """Admin function to reset rate limits for an IP (emergency use)"""
    client_ip = get_client_ip(request)
    rate_limiter.reset_attempts(client_ip)
    logger.info(f"Admin {admin_user.username} reset rate limits for IP: {client_ip}")
    return {"message": f"Rate limits reset for IP: {client_ip}"}

# Enhanced permission dependencies with specific roles
READ_PERMISSION = has_permission("read")
WRITE_PERMISSION = has_permission("write")
ADMIN_PERMISSION = has_permission("admin")

# Convenience function for creating users (admin only)
def create_user(username: str, password: str, email: str, permissions: list, full_name: Optional[str] = None):
    """Create a new user (for admin use)"""
    if username in users_db:
        raise ValueError(f"User {username} already exists")
    
    users_db[username] = {
        "username": username,
        "full_name": full_name or username.title(),
        "email": email,
        "hashed_password": pwd_context.hash(password),
        "disabled": False,
        "permissions": permissions
    }
    logger.info(f"Created new user: {username} with permissions: {permissions}")
    return username

# Security headers helper
def get_security_headers() -> Dict[str, str]:
    """Get recommended security headers"""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Referrer-Policy": "strict-origin-when-cross-origin"
    }
