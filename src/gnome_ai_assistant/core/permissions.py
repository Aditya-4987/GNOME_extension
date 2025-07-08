"""Security and permission management for GNOME AI Assistant."""

import sqlite3
import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import logging
from pathlib import Path
import hashlib

from ..utils.logger import get_logger

logger = get_logger("permissions")


class PermissionLevel(Enum):
    """Permission levels for operations."""
    DENY = "deny"
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    ALLOW_PERMANENT = "allow_permanent"


class RiskLevel(Enum):
    """Risk levels for operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PermissionRequest:
    """Represents a permission request for a specific operation."""
    tool_name: str
    action: str
    description: str
    risk_level: RiskLevel
    required_capabilities: List[str]
    parameters: Optional[Dict[str, str]] = None
    user_context: Optional[str] = None
    
    def __post_init__(self):
        """Ensure risk_level is a RiskLevel enum."""
        if isinstance(self.risk_level, str):
            self.risk_level = RiskLevel(self.risk_level)
    
    def get_signature(self) -> str:
        """Get a unique signature for this permission request."""
        data = f"{self.tool_name}:{self.action}:{self.risk_level.value}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class PermissionGrant:
    """Represents a granted permission."""
    request_signature: str
    level: PermissionLevel
    granted_at: datetime
    expires_at: Optional[datetime]
    granted_by: str = "user"
    metadata: Optional[Dict[str, str]] = None
    
    def is_expired(self) -> bool:
        """Check if this permission grant has expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if this permission grant is valid."""
        return not self.is_expired() and self.level != PermissionLevel.DENY


class PermissionManager:
    """Manages security permissions for all system operations."""
    
    def __init__(self, db_path: str):
        """
        Initialize permission manager.
        
        Args:
            db_path: Path to SQLite database for storing permissions
        """
        self.db_path = db_path
        self.session_permissions: Dict[str, PermissionGrant] = {}
        self.pending_requests: Dict[str, PermissionRequest] = {}
        self.notification_callbacks: List = []
        self.audit_log: List[Dict] = []
        
        # Ensure database directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize the permission manager."""
        try:
            await self._initialize_database()
            await self._load_permanent_permissions()
            logger.info("Permission manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize permission manager: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup permission manager resources."""
        try:
            # Save any pending session permissions
            await self._save_session_permissions()
            logger.info("Permission manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during permission manager cleanup: {e}")
    
    async def _initialize_database(self) -> None:
        """Initialize the SQLite database for permissions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create permissions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_signature TEXT UNIQUE NOT NULL,
                    tool_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    level TEXT NOT NULL,
                    granted_at TIMESTAMP NOT NULL,
                    expires_at TIMESTAMP,
                    granted_by TEXT DEFAULT 'user',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS permission_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_signature TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_context TEXT
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_permissions_signature ON permissions(request_signature)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON permission_audit(timestamp)")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            raise
    
    async def _load_permanent_permissions(self) -> None:
        """Load permanent permissions from database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT request_signature, level, granted_at, expires_at, granted_by, metadata
                FROM permissions
                WHERE level = 'allow_permanent'
                AND (expires_at IS NULL OR expires_at > datetime('now'))
            """)
            
            for row in cursor.fetchall():
                signature, level, granted_at, expires_at, granted_by, metadata = row
                
                grant = PermissionGrant(
                    request_signature=signature,
                    level=PermissionLevel(level),
                    granted_at=datetime.fromisoformat(granted_at),
                    expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
                    granted_by=granted_by,
                    metadata=json.loads(metadata) if metadata else None
                )
                
                self.session_permissions[signature] = grant
            
            conn.close()
            logger.info(f"Loaded {len(self.session_permissions)} permanent permissions")
            
        except Exception as e:
            logger.error(f"Error loading permanent permissions: {e}")
    
    async def request_permission(self, request: PermissionRequest) -> PermissionLevel:
        """
        Request permission for an operation.
        
        Args:
            request: Permission request details
            
        Returns:
            Permission level granted
        """
        try:
            signature = request.get_signature()
            
            # Check existing permissions
            existing_grant = await self._check_existing_permission(signature)
            if existing_grant and existing_grant.is_valid():
                await self._log_audit_event(request, existing_grant.level.value, "cached")
                return existing_grant.level
            
            # For critical operations, always prompt
            if request.risk_level == RiskLevel.CRITICAL:
                level = await self._prompt_user_permission(request)
            else:
                # Check default policies
                level = await self._evaluate_permission_policy(request)
                
                # If policy is to prompt, show user dialog
                if level == PermissionLevel.DENY and request.risk_level in [RiskLevel.HIGH, RiskLevel.MEDIUM]:
                    level = await self._prompt_user_permission(request)
            
            # Grant the permission if approved
            if level != PermissionLevel.DENY:
                await self.grant_permission(request, level)
            
            await self._log_audit_event(request, level.value, "evaluated")
            return level
            
        except Exception as e:
            logger.error(f"Error processing permission request: {e}")
            await self._log_audit_event(request, "error", str(e))
            return PermissionLevel.DENY
    
    async def grant_permission(self, request: PermissionRequest, level: PermissionLevel) -> None:
        """
        Grant permission for a request.
        
        Args:
            request: Permission request
            level: Permission level to grant
        """
        try:
            signature = request.get_signature()
            
            # Calculate expiration based on level
            expires_at = None
            if level == PermissionLevel.ALLOW_SESSION:
                expires_at = datetime.now() + timedelta(hours=8)  # Session expires in 8 hours
            elif level == PermissionLevel.ALLOW_ONCE:
                expires_at = datetime.now() + timedelta(minutes=5)  # One-time use expires in 5 minutes
            
            grant = PermissionGrant(
                request_signature=signature,
                level=level,
                granted_at=datetime.now(),
                expires_at=expires_at,
                metadata={
                    "tool_name": request.tool_name,
                    "action": request.action,
                    "risk_level": request.risk_level.value
                }
            )
            
            # Store in session
            self.session_permissions[signature] = grant
            
            # Store permanent permissions in database
            if level == PermissionLevel.ALLOW_PERMANENT:
                await self._save_permanent_permission(grant)
            
            logger.info(f"Granted {level.value} permission for {request.tool_name}:{request.action}")
            
        except Exception as e:
            logger.error(f"Error granting permission: {e}")
            raise
    
    async def revoke_permission(self, signature: str) -> bool:
        """
        Revoke a permission.
        
        Args:
            signature: Permission signature to revoke
            
        Returns:
            True if revoked successfully
        """
        try:
            # Remove from session
            if signature in self.session_permissions:
                del self.session_permissions[signature]
            
            # Remove from database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM permissions WHERE request_signature = ?", (signature,))
            conn.commit()
            conn.close()
            
            logger.info(f"Revoked permission: {signature}")
            return True
            
        except Exception as e:
            logger.error(f"Error revoking permission: {e}")
            return False
    
    async def list_permissions(self) -> List[Dict]:
        """List all active permissions."""
        try:
            permissions = []
            
            for signature, grant in self.session_permissions.items():
                if grant.is_valid():
                    permissions.append({
                        "signature": signature,
                        "level": grant.level.value,
                        "granted_at": grant.granted_at.isoformat(),
                        "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
                        "metadata": grant.metadata
                    })
            
            return permissions
            
        except Exception as e:
            logger.error(f"Error listing permissions: {e}")
            return []
    
    async def _check_existing_permission(self, signature: str) -> Optional[PermissionGrant]:
        """Check if permission already exists and is valid."""
        grant = self.session_permissions.get(signature)
        if grant and grant.is_valid():
            return grant
        
        # Clean up expired permissions
        if grant and grant.is_expired():
            del self.session_permissions[signature]
        
        return None
    
    async def _evaluate_permission_policy(self, request: PermissionRequest) -> PermissionLevel:
        """Evaluate permission based on policies."""
        # Default policy: deny high-risk operations, allow low-risk
        if request.risk_level == RiskLevel.LOW:
            return PermissionLevel.ALLOW_SESSION
        elif request.risk_level == RiskLevel.MEDIUM:
            # Check if this is a commonly used operation
            if request.tool_name in ["file_manager", "window_manager"]:
                return PermissionLevel.ALLOW_SESSION
        
        # Default to deny for high-risk operations
        return PermissionLevel.DENY
    
    async def _prompt_user_permission(self, request: PermissionRequest) -> PermissionLevel:
        """Prompt user for permission via notification."""
        try:
            # Store pending request
            request_id = f"perm_{int(time.time())}"
            self.pending_requests[request_id] = request
            
            # Send notification to user
            await self._send_permission_notification(request, request_id)
            
            # Wait for user response (with timeout)
            timeout = 30  # 30 seconds
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if request_id not in self.pending_requests:
                    # User responded
                    break
                await asyncio.sleep(0.5)
            
            # Check if we got a response
            if request_id in self.pending_requests:
                # Timeout - remove pending request and deny
                del self.pending_requests[request_id]
                return PermissionLevel.DENY
            
            # Get the response from session (stored by notification callback)
            signature = request.get_signature()
            grant = self.session_permissions.get(signature)
            if grant:
                return grant.level
            
            return PermissionLevel.DENY
            
        except Exception as e:
            logger.error(f"Error prompting user for permission: {e}")
            return PermissionLevel.DENY
    
    async def _send_permission_notification(self, request: PermissionRequest, request_id: str) -> None:
        """Send permission request notification to user."""
        try:
            # Import here to avoid circular imports
            from ..interfaces.notifications import send_permission_notification
            
            await send_permission_notification(
                title="Permission Request",
                message=f"{request.tool_name} wants to {request.description}",
                risk_level=request.risk_level.value,
                request_id=request_id,
                callback=self._handle_permission_response
            )
            
        except Exception as e:
            logger.error(f"Error sending permission notification: {e}")
    
    async def _handle_permission_response(self, request_id: str, response: str) -> None:
        """Handle user response to permission request."""
        try:
            if request_id not in self.pending_requests:
                logger.warning(f"Received response for unknown request: {request_id}")
                return
            
            request = self.pending_requests[request_id]
            del self.pending_requests[request_id]
            
            # Map response to permission level
            level_map = {
                "allow_once": PermissionLevel.ALLOW_ONCE,
                "allow_session": PermissionLevel.ALLOW_SESSION,
                "allow_permanent": PermissionLevel.ALLOW_PERMANENT,
                "deny": PermissionLevel.DENY
            }
            
            level = level_map.get(response, PermissionLevel.DENY)
            
            # Grant the permission
            if level != PermissionLevel.DENY:
                await self.grant_permission(request, level)
            
            logger.info(f"User responded to permission request: {response}")
            
        except Exception as e:
            logger.error(f"Error handling permission response: {e}")
    
    async def _save_permanent_permission(self, grant: PermissionGrant) -> None:
        """Save permanent permission to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO permissions 
                (request_signature, tool_name, action, level, granted_at, expires_at, granted_by, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                grant.request_signature,
                grant.metadata.get("tool_name", ""),
                grant.metadata.get("action", ""),
                grant.level.value,
                grant.granted_at.isoformat(),
                grant.expires_at.isoformat() if grant.expires_at else None,
                grant.granted_by,
                json.dumps(grant.metadata) if grant.metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving permanent permission: {e}")
            raise
    
    async def _save_session_permissions(self) -> None:
        """Save session permissions that should persist."""
        # Currently, only permanent permissions are saved
        # Session permissions are lost on restart by design
        pass
    
    async def _log_audit_event(self, request: PermissionRequest, decision: str, reason: str) -> None:
        """Log permission audit event."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO permission_audit 
                (request_signature, tool_name, action, risk_level, decision, reason, user_context)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                request.get_signature(),
                request.tool_name,
                request.action,
                request.risk_level.value,
                decision,
                reason,
                request.user_context
            ))
            
            conn.commit()
            conn.close()
            
            # Also keep in-memory audit log (limited size)
            self.audit_log.append({
                "timestamp": datetime.now().isoformat(),
                "tool_name": request.tool_name,
                "action": request.action,
                "risk_level": request.risk_level.value,
                "decision": decision,
                "reason": reason
            })
            
            # Keep only last 1000 entries
            if len(self.audit_log) > 1000:
                self.audit_log = self.audit_log[-1000:]
            
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
    
    def get_audit_log(self, limit: int = 100) -> List[Dict]:
        """Get recent audit log entries."""
        return self.audit_log[-limit:]
    
    def add_notification_callback(self, callback) -> None:
        """Add callback for permission notifications."""
        self.notification_callbacks.append(callback)
    
    def remove_notification_callback(self, callback) -> None:
        """Remove permission notification callback."""
        if callback in self.notification_callbacks:
            self.notification_callbacks.remove(callback)
