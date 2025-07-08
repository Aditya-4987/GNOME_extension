"""
Integration tests for the GNOME AI Assistant.

These tests verify that different components work together correctly.
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.gnome_ai_assistant.core.service import AssistantService
from src.gnome_ai_assistant.core.permissions import PermissionRequest, RiskLevel


class TestServiceIntegration:
    """Test integration between service components."""

    @pytest.mark.asyncio
    async def test_service_full_initialization(self):
        """Test that service can initialize all components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock external dependencies
            with patch('gnome_ai_assistant.core.service.BaseLLM'), \
                 patch('gnome_ai_assistant.llm.ollama.OllamaLLM') as mock_llm:
                
                mock_llm.return_value.initialize = AsyncMock()
                mock_llm.return_value.generate_response = AsyncMock()
                
                service = AssistantService()
                
                # Update config to use temp directory
                service.config.database.sqlite_path = str(Path(temp_dir) / "test.db")
                service.config.database.vector_db_path = str(Path(temp_dir) / "vector_db")
                
                try:
                    await service.initialize()
                    assert service.is_initialized
                    
                    # Verify all subsystems are initialized
                    assert service.permission_manager is not None
                    assert service.tool_registry is not None
                    assert service.llm_engine is not None
                    assert service.agentic_engine is not None
                    
                finally:
                    await service.cleanup()

    @pytest.mark.asyncio 
    async def test_permission_workflow(self):
        """Test permission request workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            from src.gnome_ai_assistant.core.permissions import PermissionManager
            
            db_path = str(Path(temp_dir) / "permissions.db")
            permission_manager = PermissionManager(db_path)
            
            try:
                # Test low-risk operation auto-approval
                request = PermissionRequest(
                    tool_name="file_manager",
                    action="list_files",
                    description="List files in directory",
                    risk_level=RiskLevel.LOW,
                    required_capabilities=["file_read"]
                )
                
                result = await permission_manager.request_permission(request)
                assert result.name in ["ALLOW_SESSION", "ALLOW_ONCE"]
                
                # Test that same request is cached
                result2 = await permission_manager.request_permission(request)
                assert result == result2
                
            finally:
                await permission_manager.cleanup()


class TestToolIntegration:
    """Test tool system integration."""

    @pytest.mark.asyncio
    async def test_tool_registry_loading(self):
        """Test that tools can be loaded and registered."""
        from src.gnome_ai_assistant.tools.base import ToolRegistry
        
        registry = ToolRegistry()
        await registry.initialize()
        
        # Should have some default tools loaded
        assert len(registry.tools) > 0
        
        # Test that we can get tool schemas
        schemas = registry.get_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) > 0
        
        # Each schema should have required fields
        for schema in schemas:
            assert "name" in schema
            assert "description" in schema


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_chat_workflow(self):
        """Test a complete chat workflow."""
        # This would test:
        # 1. User sends message
        # 2. Service processes with LLM
        # 3. LLM suggests tool usage
        # 4. Permission system validates
        # 5. Tool executes
        # 6. Response returned to user
        
        # For now, this is a placeholder as it requires mocking
        # external LLM services and system integration
        pass
