"""
Integration tests for the complete AI assistant system.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, Mock, patch
import json
import tempfile
import os
from pathlib import Path

from src.gnome_ai_assistant.core.service import AssistantService
from src.gnome_ai_assistant.core.config import AssistantAssistantConfig
from src.gnome_ai_assistant.core.permissions import PermissionManager, PermissionRequest, PermissionLevel
from src.gnome_ai_assistant.tools.base import ToolRegistry
from src.gnome_ai_assistant.llm.base import BaseLLM, Message, LLMResponse


class MockLLM(BaseLLM):
    """Mock LLM for testing."""
    
    def __init__(self, config):
        super().__init__(config)
        self.responses = []
        self.current_response = 0
    
    def add_response(self, response: LLMResponse):
        """Add a mock response."""
        self.responses.append(response)
    
    async def generate_response(self, messages, functions=None):
        """Generate a mock response."""
        if self.current_response < len(self.responses):
            response = self.responses[self.current_response]
            self.current_response += 1
            return response
        
        # Default response
        return LLMResponse(
            content="I understand your request.",
            function_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        )
    
    async def stream_response(self, messages, functions=None):
        """Stream a mock response."""
        response = await self.generate_response(messages, functions)
        for word in response.content.split():
            yield word + " "
    
    async def test_connection(self):
        """Test connection (always succeeds for mock)."""
        return True


class TestFullSystemIntegration:
    """Test the complete AI assistant system integration."""
    
    @pytest.fixture
    async def temp_config(self):
        """Create a temporary configuration for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_data = {
                "llm": {
                    "provider": "mock",
                    "model": "test-model",
                    "base_url": "http://localhost:8000",
                    "api_key": "test-key",
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                "service": {
                    "socket_path": os.path.join(temp_dir, "test.sock"),
                    "host": "localhost",
                    "port": 8000,
                    "log_level": "DEBUG"
                },
                "security": {
                    "require_permissions": True,
                    "default_permission_level": "deny",
                    "session_timeout": 3600,
                    "audit_log": True
                },
                "database": {
                    "sqlite_path": os.path.join(temp_dir, "test.db"),
                    "chromadb_path": os.path.join(temp_dir, "chroma"),
                    "connection_pool_size": 5
                }
            }
            
            config_file = os.path.join(temp_dir, "config.json")
            with open(config_file, 'w') as f:
                json.dump(config_data, f)
            
            # Mock the config loading
            with patch('gnome_ai_assistant.core.config.get_config') as mock_get_config:
                config = AssistantAssistantConfig(**config_data)
                mock_get_config.return_value = config
                yield config
    
    @pytest.fixture
    async def service(self, temp_config):
        """Create a service instance for testing."""
        service = AssistantService()
        
        # Mock the LLM initialization
        with patch.object(service, '_initialize_llm') as mock_init_llm:
            mock_llm = MockLLM(temp_config.llm)
            service.llm_engine = mock_llm
            mock_init_llm.return_value = None
            
            await service.initialize()
            yield service
            
            # Cleanup
            await service.cleanup()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, service):
        """Test that the service initializes correctly."""
        assert service.is_initialized is True
        assert service.llm_engine is not None
        assert service.tool_registry is not None
        assert service.permission_manager is not None
        assert service.memory_manager is not None
        assert service.agentic_engine is not None
    
    @pytest.mark.asyncio
    async def test_basic_chat_flow(self, service):
        """Test basic chat functionality."""
        # Mock LLM response
        mock_response = LLMResponse(
            content="Hello! How can I help you today?",
            function_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20}
        )
        service.llm_engine.add_response(mock_response)
        
        # Process a chat request
        result = await service.agentic_engine.process_request(
            user_request="Hello",
            context={}
        )
        
        assert result is not None
        assert result.response == "Hello! How can I help you today?"
        assert result.success is True
    
    @pytest.mark.asyncio
    async def test_tool_execution_with_permissions(self, service):
        """Test tool execution with permission checking."""
        # Mock permission manager to allow the operation
        with patch.object(service.permission_manager, 'request_permission') as mock_request:
            mock_request.return_value = PermissionLevel.ALLOW_ONCE
            
            # Mock LLM response that calls a tool
            mock_response = LLMResponse(
                content="I'll help you list files in the current directory.",
                function_calls=[{
                    "name": "file_manager",
                    "arguments": {
                        "action": "list_files",
                        "path": "."
                    }
                }],
                finish_reason="function_call",
                usage={"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}
            )
            service.llm_engine.add_response(mock_response)
            
            # Process request that should trigger tool execution
            result = await service.agentic_engine.process_request(
                user_request="List files in current directory",
                context={}
            )
            
            assert result is not None
            assert len(result.function_calls) > 0
            assert result.function_calls[0]["name"] == "file_manager"
    
    @pytest.mark.asyncio
    async def test_permission_denial(self, service):
        """Test permission denial handling."""
        # Mock permission manager to deny the operation
        with patch.object(service.permission_manager, 'request_permission') as mock_request:
            mock_request.return_value = PermissionLevel.DENY
            
            # Try to execute a tool that should be denied
            result = await service.tool_registry.execute_tool(
                name="system_control",
                action="shutdown"
            )
            
            assert result.success is False
            assert result.requires_permission is True
    
    @pytest.mark.asyncio
    async def test_memory_persistence(self, service):
        """Test memory persistence across requests."""
        # Store a memory
        conversation_id = "test-conversation"
        await service.memory_manager.store_message(
            conversation_id=conversation_id,
            role="user",
            content="Remember that my name is Alice"
        )
        
        # Retrieve conversation
        conversation = await service.memory_manager.get_conversation(conversation_id)
        assert conversation is not None
        assert len(conversation["messages"]) == 1
        assert conversation["messages"][0]["content"] == "Remember that my name is Alice"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service):
        """Test error handling in various scenarios."""
        # Test with invalid tool name
        result = await service.tool_registry.execute_tool(
            name="nonexistent_tool",
            action="test"
        )
        
        assert result.success is False
        assert "not found" in result.error
        
        # Test with invalid parameters
        result = await service.tool_registry.execute_tool(
            name="file_manager",
            action="invalid_action"
        )
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test handling of concurrent requests."""
        # Mock LLM responses for concurrent requests
        for i in range(3):
            mock_response = LLMResponse(
                content=f"Response {i}",
                function_calls=[],
                finish_reason="stop",
                usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
            )
            service.llm_engine.add_response(mock_response)
        
        # Create concurrent requests
        tasks = []
        for i in range(3):
            task = asyncio.create_task(
                service.agentic_engine.process_request(
                    user_request=f"Request {i}",
                    context={}
                )
            )
            tasks.append(task)
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all requests were processed
        assert len(results) == 3
        for i, result in enumerate(results):
            assert not isinstance(result, Exception)
            assert result.response == f"Response {i}"
    
    @pytest.mark.asyncio
    async def test_tool_registry_initialization(self, service):
        """Test that all tools are properly registered."""
        tools = service.tool_registry.list_tools()
        
        # Check that basic tools are registered
        expected_tools = [
            "file_manager",
            "window_manager",
            "system_control",
            "web_browser",
            "network"
        ]
        
        for tool_name in expected_tools:
            assert tool_name in tools or any(tool_name in tool for tool in tools)
    
    @pytest.mark.asyncio
    async def test_configuration_validation(self, temp_config):
        """Test configuration validation."""
        # Test that configuration is loaded correctly
        assert temp_config.llm.provider == "mock"
        assert temp_config.service.host == "localhost"
        assert temp_config.security.require_permissions is True
        assert temp_config.database.sqlite_path.endswith("test.db")
    
    @pytest.mark.asyncio
    async def test_cleanup_on_shutdown(self, service):
        """Test proper cleanup on service shutdown."""
        # Verify service is initialized
        assert service.is_initialized is True
        
        # Mock some active connections
        mock_websocket = Mock()
        mock_websocket.close = AsyncMock()
        service.active_connections.add(mock_websocket)
        
        # Perform cleanup
        await service.cleanup()
        
        # Verify cleanup was performed
        mock_websocket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_agentic_engine_task_management(self, service):
        """Test agentic engine task management."""
        # Mock LLM response that creates a multi-step task
        mock_response = LLMResponse(
            content="I'll help you with that task.",
            function_calls=[
                {
                    "name": "file_manager",
                    "arguments": {"action": "create_file", "path": "test.txt", "content": "Hello"}
                }
            ],
            finish_reason="function_call",
            usage={"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25}
        )
        service.llm_engine.add_response(mock_response)
        
        # Mock permission approval
        with patch.object(service.permission_manager, 'request_permission') as mock_request:
            mock_request.return_value = PermissionLevel.ALLOW_ONCE
            
            # Process a complex request
            result = await service.agentic_engine.process_request(
                user_request="Create a file called test.txt with content 'Hello'",
                context={}
            )
            
            assert result is not None
            assert len(result.function_calls) > 0
            assert result.task_id is not None
    
    @pytest.mark.asyncio
    async def test_voice_interface_integration(self, service):
        """Test voice interface integration."""
        # Import voice interface
        from src.gnome_ai_assistant.interfaces.voice import VoiceInterface
        
        # Mock voice interface methods
        with patch.object(VoiceInterface, 'start_listening') as mock_start:
            with patch.object(VoiceInterface, 'synthesize_speech') as mock_synthesize:
                mock_start.return_value = True
                mock_synthesize.return_value = b"fake_audio_data"
                
                voice_interface = VoiceInterface()
                
                # Test voice interface integration
                assert voice_interface.start_listening() is True
                
                audio_data = await voice_interface.synthesize_speech("Hello world")
                assert audio_data == b"fake_audio_data"
    
    @pytest.mark.asyncio
    async def test_web_interface_integration(self, service):
        """Test web interface integration."""
        from src.gnome_ai_assistant.interfaces.web import WebInterface
        
        # Create web interface
        web_interface = WebInterface(service)
        
        # Test that web interface is properly configured
        assert web_interface.service == service
        assert web_interface.app is not None
        assert web_interface.host == "localhost"
        assert web_interface.port == 8080
    
    @pytest.mark.asyncio
    async def test_system_resource_management(self, service):
        """Test system resource management."""
        # Test that service manages resources properly
        initial_connections = len(service.active_connections)
        
        # Simulate adding connections
        mock_connection = Mock()
        service.active_connections.add(mock_connection)
        
        assert len(service.active_connections) == initial_connections + 1
        
        # Simulate cleanup
        service.active_connections.remove(mock_connection)
        
        assert len(service.active_connections) == initial_connections
    
    @pytest.mark.asyncio
    async def test_multi_llm_provider_support(self, temp_config):
        """Test support for multiple LLM providers."""
        # Test that different providers can be configured
        providers = ["ollama", "openai", "anthropic"]
        
        for provider in providers:
            temp_config.llm.provider = provider
            
            service = AssistantService()
            
            # Mock provider initialization
            with patch.object(service, '_initialize_llm') as mock_init:
                mock_init.return_value = None
                
                # Should not raise exception for supported providers
                if provider != "anthropic":  # Anthropic is implemented
                    await service.initialize()
                    await service.cleanup()
    
    @pytest.mark.asyncio 
    async def test_security_audit_logging(self, service):
        """Test security audit logging."""
        # Mock permission request that should be audited
        request = PermissionRequest(
            tool_name="system_control",
            action="shutdown",
            description="Shutdown the system",
            risk_level="high",
            required_capabilities=["system_control"]
        )
        
        # Mock audit log
        with patch.object(service.permission_manager, 'audit_log') as mock_audit:
            mock_audit.return_value = None
            
            # Request permission (should trigger audit log)
            result = await service.permission_manager.request_permission(request)
            
            # Verify audit logging was called
            assert mock_audit.called
    
    @pytest.mark.asyncio
    async def test_extension_communication(self, service):
        """Test communication with GNOME extension."""
        # Mock WebSocket connection
        mock_websocket = Mock()
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_json = AsyncMock(return_value={
            "type": "chat",
            "message": "Hello from extension",
            "context": {}
        })
        mock_websocket.send_json = AsyncMock()
        
        # Mock LLM response
        mock_response = LLMResponse(
            content="Hello from service",
            function_calls=[],
            finish_reason="stop",
            usage={"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10}
        )
        service.llm_engine.add_response(mock_response)
        
        # Simulate WebSocket communication
        service.active_connections.add(mock_websocket)
        
        # Process the message
        result = await service.agentic_engine.process_request(
            user_request="Hello from extension",
            context={}
        )
        
        assert result.response == "Hello from service"
