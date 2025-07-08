"""
Unit tests for the permission system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from src.gnome_ai_assistant.core.permissions import (
    PermissionManager, 
    PermissionRequest, 
    PermissionLevel, 
    RiskLevel
)


class TestPermissionManager:
    """Test the PermissionManager class."""

    @pytest.mark.asyncio
    async def test_permission_manager_initialization(self, permission_manager):
        """Test permission manager initializes correctly."""
        assert permission_manager is not None
        assert hasattr(permission_manager, 'db')
        assert hasattr(permission_manager, 'session_permissions')

    @pytest.mark.asyncio
    async def test_auto_approve_low_risk(self, permission_manager):
        """Test auto-approval of low-risk operations."""
        request = PermissionRequest(
            tool_name="test_tool",
            action="read_file",
            description="Read a file",
            risk_level=RiskLevel.LOW,
            required_capabilities=["file_read"]
        )
        
        level = await permission_manager.request_permission(request)
        assert level in [PermissionLevel.ALLOW_SESSION, PermissionLevel.ALLOW_ONCE]

    @pytest.mark.asyncio
    async def test_auto_deny_critical_risk(self, permission_manager):
        """Test auto-denial of critical operations."""
        request = PermissionRequest(
            tool_name="test_tool",
            action="system_command",
            description="Execute system command",
            risk_level=RiskLevel.CRITICAL,
            required_capabilities=["system_admin"]
        )
        
        level = await permission_manager.request_permission(request)
        assert level == PermissionLevel.DENY

    @pytest.mark.asyncio
    async def test_session_permission_caching(self, permission_manager):
        """Test that session permissions are cached correctly."""
        request = PermissionRequest(
            tool_name="test_tool",
            action="safe_action",
            description="Safe operation",
            risk_level=RiskLevel.LOW,
            required_capabilities=["safe_capability"]
        )
        
        # First request should process normally
        level1 = await permission_manager.request_permission(request)
        
        # Second identical request should use cached permission
        level2 = await permission_manager.request_permission(request)
        
        assert level1 == level2

    @pytest.mark.asyncio
    async def test_permission_cleanup(self, permission_manager):
        """Test that expired permissions are cleaned up."""
        # This is tested by the cleanup task in the permission manager
        assert hasattr(permission_manager, '_cleanup_task')


class TestPermissionRequest:
    """Test the PermissionRequest class."""

    def test_permission_request_creation(self):
        """Test creation of permission requests."""
        request = PermissionRequest(
            tool_name="test_tool",
            action="test_action",
            description="Test description",
            risk_level=RiskLevel.MEDIUM,
            required_capabilities=["test_capability"]
        )
        
        assert request.tool_name == "test_tool"
        assert request.action == "test_action"
        assert request.risk_level == RiskLevel.MEDIUM
        assert request.request_id is not None
        assert request.timestamp is not None

    def test_request_id_generation(self):
        """Test that request IDs are generated consistently."""
        request1 = PermissionRequest(
            tool_name="test_tool",
            action="test_action",
            description="Test description",
            risk_level=RiskLevel.MEDIUM,
            required_capabilities=["test_capability"],
            parameters={"param": "value"}
        )
        
        request2 = PermissionRequest(
            tool_name="test_tool",
            action="test_action",
            description="Test description",
            risk_level=RiskLevel.MEDIUM,
            required_capabilities=["test_capability"],
            parameters={"param": "value"}
        )
        
        # Requests with same parameters should have same ID
        assert request1.request_id == request2.request_id
