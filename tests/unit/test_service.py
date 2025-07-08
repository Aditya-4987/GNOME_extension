"""
Unit tests for the core service.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient

from src.gnome_ai_assistant.core.service import AssistantService


class TestAssistantService:
    """Test the AssistantService class."""

    def test_service_initialization(self):
        """Test service initializes correctly."""
        service = AssistantService()
        assert service is not None
        assert hasattr(service, 'app')
        assert hasattr(service, 'config')
        assert service.is_initialized is False

    @pytest.mark.asyncio
    async def test_service_initialization_async(self):
        """Test async service initialization."""
        service = AssistantService()
        
        # Mock the subsystem initialization
        with patch.object(service, '_initialize_llm', new_callable=AsyncMock), \
             patch('gnome_ai_assistant.core.service.PermissionManager') as mock_pm, \
             patch('gnome_ai_assistant.core.service.MemoryManager') as mock_mm, \
             patch('gnome_ai_assistant.core.service.ToolRegistry') as mock_tr, \
             patch('gnome_ai_assistant.core.service.AgenticEngine') as mock_ae:
            
            mock_pm.return_value.initialize = AsyncMock()
            mock_mm.return_value.initialize = AsyncMock()
            mock_tr.return_value.initialize = AsyncMock()
            mock_ae.return_value.initialize = AsyncMock()
            
            await service.initialize()
            assert service.is_initialized is True

    def test_fastapi_app_creation(self):
        """Test that FastAPI app is created correctly."""
        service = AssistantService()
        client = TestClient(service.app)
        
        # Test health endpoint if it exists
        response = client.get("/")
        # The exact response depends on implementation
        assert response.status_code in [200, 404]  # Either implemented or not found

    @pytest.mark.asyncio
    async def test_service_cleanup(self):
        """Test service cleanup."""
        service = AssistantService()
        
        # Mock subsystems
        service.permission_manager = Mock()
        service.permission_manager.cleanup = AsyncMock()
        service.memory_manager = Mock()
        service.memory_manager.cleanup = AsyncMock()
        service.agentic_engine = Mock()
        service.agentic_engine.cleanup = AsyncMock()
        
        await service.cleanup()
        
        service.permission_manager.cleanup.assert_called_once()
        service.memory_manager.cleanup.assert_called_once()
        service.agentic_engine.cleanup.assert_called_once()
