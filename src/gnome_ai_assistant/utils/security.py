"""
Security utilities for GNOME AI Assistant.

This module provides security-related functionality including
input validation, sanitization, and security checks.
"""

import hashlib
import hmac
import os
import re
import secrets
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
import logging
import json

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SecurityError(Exception):
    """Custom exception for security-related errors."""
    pass


class InputValidator:
    """Validates and sanitizes user inputs."""
    
    # Patterns for common input validation
    FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')
    PATH_PATTERN = re.compile(r'^[a-zA-Z0-9/._-]+$')
    COMMAND_PATTERN = re.compile(r'^[a-zA-Z0-9\s._-]+$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    URL_PATTERN = re.compile(r'^https?://[a-zA-Z0-9.-]+[a-zA-Z0-9._/-]*$')
    
    # Dangerous patterns to block
    DANGEROUS_PATTERNS = [
        re.compile(r'[;&|`$()]'),  # Shell metacharacters
        re.compile(r'\.\./'),      # Directory traversal
        re.compile(r'<script'),    # Script tags
        re.compile(r'javascript:'), # JavaScript protocol
        re.compile(r'file://'),    # File protocol
    ]
    
    # Maximum lengths for different input types
    MAX_LENGTHS = {
        'filename': 255,
        'path': 4096,
        'command': 1024,
        'message': 10000,
        'url': 2048,
        'email': 254
    }
    
    @classmethod
    def validate_filename(cls, filename: str) -> bool:
        """Validate a filename."""
        if not filename or len(filename) > cls.MAX_LENGTHS['filename']:
            return False
        
        if not cls.FILENAME_PATTERN.match(filename):
            return False
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(filename):
                return False
        
        # Check for reserved names (Windows/Unix)
        reserved = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                   'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3',
                   'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9', '.', '..'}
        
        if filename.upper() in reserved:
            return False
        
        return True
    
    @classmethod
    def validate_path(cls, path: str, allow_absolute: bool = False) -> bool:
        """Validate a file path."""
        if not path or len(path) > cls.MAX_LENGTHS['path']:
            return False
        
        # Check if absolute path is allowed
        if not allow_absolute and os.path.isabs(path):
            return False
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(path):
                return False
        
        # Normalize and check path
        try:
            normalized_path = os.path.normpath(path)
            
            # Ensure path doesn't escape allowed directories
            if '..' in normalized_path:
                return False
            
            # Check individual path components
            for component in Path(normalized_path).parts:
                if not cls.validate_filename(component):
                    return False
            
            return True
            
        except (ValueError, OSError):
            return False
    
    @classmethod
    def validate_command(cls, command: str) -> bool:
        """Validate a command string."""
        if not command or len(command) > cls.MAX_LENGTHS['command']:
            return False
        
        # Check for dangerous shell metacharacters
        dangerous_chars = set(';&|`$(){}[]<>*?~')
        if any(char in command for char in dangerous_chars):
            return False
        
        return True
    
    @classmethod
    def validate_url(cls, url: str) -> bool:
        """Validate a URL."""
        if not url or len(url) > cls.MAX_LENGTHS['url']:
            return False
        
        return cls.URL_PATTERN.match(url) is not None
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate an email address."""
        if not email or len(email) > cls.MAX_LENGTHS['email']:
            return False
        
        return cls.EMAIL_PATTERN.match(email) is not None
    
    @classmethod
    def sanitize_string(cls, input_str: str, max_length: Optional[int] = None) -> str:
        """Sanitize a string by removing dangerous characters."""
        if not input_str:
            return ""
        
        # Remove null bytes and control characters
        sanitized = ''.join(char for char in input_str if ord(char) >= 32 or char in '\t\n\r')
        
        # Limit length
        if max_length:
            sanitized = sanitized[:max_length]
        
        return sanitized
    
    @classmethod
    def sanitize_html(cls, html_str: str) -> str:
        """Basic HTML sanitization."""
        if not html_str:
            return ""
        
        # Remove script tags and their content
        html_str = re.sub(r'<script[^>]*>.*?</script>', '', html_str, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove dangerous attributes
        html_str = re.sub(r'\son\w+\s*=\s*["\'][^"\']*["\']', '', html_str, flags=re.IGNORECASE)
        
        # Remove javascript: protocol
        html_str = re.sub(r'javascript:', '', html_str, flags=re.IGNORECASE)
        
        return html_str


class SecureFileHandler:
    """Handles file operations securely."""
    
    def __init__(self, allowed_directories: Optional[List[str]] = None,
                 max_file_size: int = 100 * 1024 * 1024):  # 100MB default
        self.allowed_directories = allowed_directories or []
        self.max_file_size = max_file_size
        
        # Convert to absolute paths
        self.allowed_directories = [os.path.abspath(d) for d in self.allowed_directories]
    
    def _is_path_allowed(self, file_path: str) -> bool:
        """Check if a file path is in allowed directories."""
        if not self.allowed_directories:
            return True
        
        abs_path = os.path.abspath(file_path)
        
        for allowed_dir in self.allowed_directories:
            if abs_path.startswith(allowed_dir):
                return True
        
        return False
    
    def _check_file_size(self, file_path: str) -> bool:
        """Check if file size is within limits."""
        try:
            size = os.path.getsize(file_path)
            return size <= self.max_file_size
        except OSError:
            return False
    
    async def read_file_safely(self, file_path: str) -> Optional[str]:
        """Read a file safely with security checks."""
        try:
            # Validate path
            if not InputValidator.validate_path(file_path, allow_absolute=True):
                raise SecurityError(f"Invalid file path: {file_path}")
            
            # Check if path is allowed
            if not self._is_path_allowed(file_path):
                raise SecurityError(f"File path not in allowed directories: {file_path}")
            
            # Check file size
            if not self._check_file_size(file_path):
                raise SecurityError(f"File too large: {file_path}")
            
            # Check if file exists and is readable
            if not os.path.isfile(file_path):
                raise SecurityError(f"File does not exist: {file_path}")
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            return content
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return None
    
    async def write_file_safely(self, file_path: str, content: str) -> bool:
        """Write a file safely with security checks."""
        try:
            # Validate path
            if not InputValidator.validate_path(file_path, allow_absolute=True):
                raise SecurityError(f"Invalid file path: {file_path}")
            
            # Check if path is allowed
            if not self._is_path_allowed(file_path):
                raise SecurityError(f"File path not in allowed directories: {file_path}")
            
            # Check content size
            content_size = len(content.encode('utf-8'))
            if content_size > self.max_file_size:
                raise SecurityError(f"Content too large: {content_size} bytes")
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_path = file_path + '.tmp'
            
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Atomic rename
            os.rename(temp_path, file_path)
            
            return True
            
        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return False
    
    def create_secure_temp_file(self, suffix: str = "", prefix: str = "gnome_ai_") -> str:
        """Create a secure temporary file."""
        try:
            # Create temporary file with secure permissions
            fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
            
            # Set secure permissions (readable/writable by owner only)
            os.chmod(temp_path, 0o600)
            
            # Close the file descriptor (we just need the path)
            os.close(fd)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error creating temporary file: {e}")
            raise SecurityError(f"Failed to create secure temporary file: {e}")


class TokenManager:
    """Manages secure tokens and sessions."""
    
    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or self._generate_secret_key()
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._token_expiry = 3600  # 1 hour default
    
    def _generate_secret_key(self) -> str:
        """Generate a secure secret key."""
        return secrets.token_urlsafe(32)
    
    def generate_token(self, user_id: str, permissions: Optional[List[str]] = None,
                      expires_in: Optional[int] = None) -> str:
        """Generate a secure token."""
        try:
            # Generate random token
            token = secrets.token_urlsafe(32)
            
            # Set expiration time
            expires_at = time.time() + (expires_in or self._token_expiry)
            
            # Store token info
            self._tokens[token] = {
                'user_id': user_id,
                'permissions': permissions or [],
                'created_at': time.time(),
                'expires_at': expires_at
            }
            
            return token
            
        except Exception as e:
            logger.error(f"Error generating token: {e}")
            raise SecurityError(f"Failed to generate token: {e}")
    
    def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate a token and return its info."""
        try:
            if token not in self._tokens:
                return None
            
            token_info = self._tokens[token]
            
            # Check if token has expired
            if time.time() > token_info['expires_at']:
                del self._tokens[token]
                return None
            
            return token_info
            
        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return None
    
    def revoke_token(self, token: str) -> bool:
        """Revoke a token."""
        try:
            if token in self._tokens:
                del self._tokens[token]
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens."""
        try:
            current_time = time.time()
            expired_tokens = [
                token for token, info in self._tokens.items()
                if current_time > info['expires_at']
            ]
            
            for token in expired_tokens:
                del self._tokens[token]
            
            logger.info(f"Cleaned up {len(expired_tokens)} expired tokens")
            
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")
    
    def generate_hmac(self, data: str) -> str:
        """Generate HMAC for data integrity."""
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def verify_hmac(self, data: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self.generate_hmac(data)
        return hmac.compare_digest(expected, signature)


class RateLimiter:
    """Simple rate limiter for API endpoints."""
    
    def __init__(self, max_requests: int = 100, time_window: int = 3600):
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, List[float]] = {}
    
    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed."""
        current_time = time.time()
        
        # Get or create request history for identifier
        if identifier not in self._requests:
            self._requests[identifier] = []
        
        request_times = self._requests[identifier]
        
        # Remove old requests outside the time window
        cutoff_time = current_time - self.time_window
        request_times[:] = [t for t in request_times if t > cutoff_time]
        
        # Check if under limit
        if len(request_times) < self.max_requests:
            request_times.append(current_time)
            return True
        
        return False
    
    def get_remaining_requests(self, identifier: str) -> int:
        """Get remaining requests for an identifier."""
        if identifier not in self._requests:
            return self.max_requests
        
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        recent_requests = [
            t for t in self._requests[identifier]
            if t > cutoff_time
        ]
        
        return max(0, self.max_requests - len(recent_requests))


class SecurityAuditor:
    """Audits security events and maintains logs."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file
        self._events: List[Dict[str, Any]] = []
    
    def log_security_event(self, event_type: str, details: Dict[str, Any],
                          severity: str = "info"):
        """Log a security event."""
        event = {
            'timestamp': time.time(),
            'event_type': event_type,
            'severity': severity,
            'details': details
        }
        
        self._events.append(event)
        
        # Log to file if configured
        if self.log_file:
            try:
                with open(self.log_file, 'a') as f:
                    f.write(f"{event}\n")
            except Exception as e:
                logger.error(f"Error writing to security log: {e}")
        
        # Log to standard logger
        log_level = getattr(logging, severity.upper(), logging.INFO)
        logger.log(log_level, f"Security event: {event_type} - {details}")
    
    def get_recent_events(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent security events."""
        cutoff_time = time.time() - (hours * 3600)
        return [
            event for event in self._events
            if event['timestamp'] > cutoff_time
        ]
    
    def get_events_by_type(self, event_type: str) -> List[Dict[str, Any]]:
        """Get events by type."""
        return [
            event for event in self._events
            if event['event_type'] == event_type
        ]


# Global instances
input_validator = InputValidator()
security_auditor = SecurityAuditor()
rate_limiter = RateLimiter()
token_manager = TokenManager()


def hash_permission_request(request_data: Dict[str, Any]) -> str:
    """
    Create a hash of a permission request for caching and deduplication.
    
    Args:
        request_data: Dictionary containing permission request data
        
    Returns:
        Hexadecimal hash string
    """
    # Create a canonical string representation
    sorted_data = json.dumps(request_data, sort_keys=True, separators=(',', ':'))
    
    # Create SHA-256 hash
    hash_obj = hashlib.sha256(sorted_data.encode('utf-8'))
    return hash_obj.hexdigest()


def encrypt_data(data: str, key: Optional[str] = None) -> str:
    """
    Encrypt sensitive data using Fernet encryption.
    
    Args:
        data: String data to encrypt
        key: Optional encryption key (generates one if not provided)
        
    Returns:
        Base64-encoded encrypted data
    """
    try:
        from cryptography.fernet import Fernet
        
        if key is None:
            key = Fernet.generate_key()
        elif isinstance(key, str):
            key = key.encode('utf-8')
        
        f = Fernet(key)
        encrypted_data = f.encrypt(data.encode('utf-8'))
        return encrypted_data.decode('utf-8')
        
    except ImportError:
        logger.warning("cryptography not available, using base64 encoding")
        import base64
        return base64.b64encode(data.encode('utf-8')).decode('utf-8')


def decrypt_data(encrypted_data: str, key: str) -> str:
    """
    Decrypt data encrypted with encrypt_data.
    
    Args:
        encrypted_data: Base64-encoded encrypted data
        key: Encryption key
        
    Returns:
        Decrypted string data
    """
    try:
        from cryptography.fernet import Fernet
        
        if isinstance(key, str):
            key = key.encode('utf-8')
        
        f = Fernet(key)
        decrypted_data = f.decrypt(encrypted_data.encode('utf-8'))
        return decrypted_data.decode('utf-8')
        
    except ImportError:
        logger.warning("cryptography not available, using base64 decoding")
        import base64
        return base64.b64decode(encrypted_data.encode('utf-8')).decode('utf-8')
