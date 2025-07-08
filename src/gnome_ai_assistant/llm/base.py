"""Base classes for LLM integration."""

import asyncio
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

from ..utils.logger import get_logger

logger = get_logger("llm")


class MessageRole(Enum):
    """Message roles in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    FUNCTION = "function"


@dataclass
class Message:
    """Represents a message in the conversation."""
    role: MessageRole
    content: str
    function_call: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Ensure role is MessageRole enum."""
        if isinstance(self.role, str):
            self.role = MessageRole(self.role)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API calls."""
        result = {
            "role": self.role.value,
            "content": self.content
        }
        
        if self.function_call:
            result["function_call"] = self.function_call
        
        if self.function_name:
            result["name"] = self.function_name
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message from dictionary."""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            function_call=data.get("function_call"),
            function_name=data.get("name"),
            metadata=data.get("metadata")
        )


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: str
    function_calls: List[Dict[str, Any]]
    finish_reason: str
    usage: Dict[str, int]
    model: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class LLMConfig:
    """Configuration for LLM providers."""
    provider: str
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: int = 30
    stream: bool = False
    extra_params: Optional[Dict[str, Any]] = None


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""
    
    def __init__(self, config: Union[LLMConfig, Dict[str, Any]]):
        """
        Initialize LLM provider.
        
        Args:
            config: LLM configuration
        """
        if isinstance(config, dict):
            self.config = LLMConfig(**config)
        else:
            self.config = config
        
        self.provider_name = self.config.provider
        self.model_name = self.config.model
        self.is_initialized = False
    
    async def initialize(self) -> None:
        """Initialize the LLM provider."""
        try:
            await self.test_connection()
            self.is_initialized = True
            logger.info(f"Initialized {self.provider_name} LLM with model {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to initialize {self.provider_name} LLM: {e}")
            raise
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response from messages.
        
        Args:
            messages: Conversation messages
            functions: Available functions for function calling
            **kwargs: Additional parameters
            
        Returns:
            LLM response
        """
        pass
    
    @abstractmethod
    async def stream_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response from messages.
        
        Args:
            messages: Conversation messages
            functions: Available functions for function calling
            **kwargs: Additional parameters
            
        Yields:
            Response chunks
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """
        Test connection to LLM provider.
        
        Returns:
            True if connection successful
        """
        pass
    
    def prepare_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Prepare messages for API call.
        
        Args:
            messages: List of Message objects
            
        Returns:
            List of message dictionaries
        """
        return [msg.to_dict() for msg in messages]
    
    def create_system_message(self, content: str) -> Message:
        """Create a system message."""
        return Message(
            role=MessageRole.SYSTEM,
            content=content
        )
    
    def create_user_message(self, content: str) -> Message:
        """Create a user message."""
        return Message(
            role=MessageRole.USER,
            content=content
        )
    
    def create_assistant_message(self, content: str, function_call: Optional[Dict[str, Any]] = None) -> Message:
        """Create an assistant message."""
        return Message(
            role=MessageRole.ASSISTANT,
            content=content,
            function_call=function_call
        )
    
    def create_function_message(self, name: str, content: str) -> Message:
        """Create a function result message."""
        return Message(
            role=MessageRole.FUNCTION,
            content=content,
            function_name=name
        )
    
    def get_conversation_context(self, messages: List[Message], max_tokens: Optional[int] = None) -> List[Message]:
        """
        Get conversation context within token limit.
        
        Args:
            messages: All conversation messages
            max_tokens: Maximum context tokens (optional)
            
        Returns:
            Filtered messages within token limit
        """
        if max_tokens is None:
            return messages
        
        # Simple implementation - estimate tokens and truncate if needed
        # Real implementation would use actual tokenizer
        estimated_tokens = sum(len(msg.content.split()) * 1.3 for msg in messages)
        
        if estimated_tokens <= max_tokens:
            return messages
        
        # Keep system message and recent messages
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        other_messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        
        # Take recent messages that fit in remaining context
        result = system_messages.copy()
        remaining_tokens = max_tokens - sum(len(msg.content.split()) * 1.3 for msg in system_messages)
        
        for msg in reversed(other_messages):
            msg_tokens = len(msg.content.split()) * 1.3
            if msg_tokens <= remaining_tokens:
                result.append(msg)
                remaining_tokens -= msg_tokens
            else:
                break
        
        # Maintain chronological order (except system messages at start)
        return system_messages + list(reversed([msg for msg in result if msg.role != MessageRole.SYSTEM]))
    
    def extract_function_calls(self, response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract function calls from response.
        
        Args:
            response_data: Raw response data
            
        Returns:
            List of function calls
        """
        function_calls = []
        
        # Check for function_call in message
        if "function_call" in response_data:
            function_calls.append(response_data["function_call"])
        
        # Check for tool_calls (newer format)
        if "tool_calls" in response_data:
            for tool_call in response_data["tool_calls"]:
                if tool_call.get("type") == "function":
                    function_calls.append(tool_call["function"])
        
        return function_calls
    
    def format_functions_for_api(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format functions for API call.
        
        Args:
            functions: Tool function schemas
            
        Returns:
            Formatted functions for API
        """
        # Default implementation - override in specific providers if needed
        return functions
    
    async def cleanup(self) -> None:
        """Cleanup LLM provider resources."""
        try:
            logger.info(f"Cleaning up {self.provider_name} LLM provider")
            # Override in specific providers if needed
        except Exception as e:
            logger.error(f"Error cleaning up {self.provider_name} LLM: {e}")


class LLMManager:
    """Manages multiple LLM providers and provides unified interface."""
    
    def __init__(self):
        """Initialize LLM manager."""
        self.providers: Dict[str, BaseLLM] = {}
        self.active_provider: Optional[str] = None
        self.fallback_providers: List[str] = []
    
    def add_provider(self, name: str, provider: BaseLLM) -> None:
        """
        Add LLM provider.
        
        Args:
            name: Provider name
            provider: LLM provider instance
        """
        self.providers[name] = provider
        logger.info(f"Added LLM provider: {name}")
    
    def set_active_provider(self, name: str) -> bool:
        """
        Set active LLM provider.
        
        Args:
            name: Provider name
            
        Returns:
            True if provider exists and was set
        """
        if name in self.providers:
            self.active_provider = name
            logger.info(f"Set active LLM provider: {name}")
            return True
        return False
    
    def get_active_provider(self) -> Optional[BaseLLM]:
        """Get the active LLM provider."""
        if self.active_provider:
            return self.providers.get(self.active_provider)
        return None
    
    async def generate_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using active provider with fallback.
        
        Args:
            messages: Conversation messages
            functions: Available functions
            **kwargs: Additional parameters
            
        Returns:
            LLM response
        """
        provider = self.get_active_provider()
        if not provider:
            raise ValueError("No active LLM provider")
        
        try:
            return await provider.generate_response(messages, functions, **kwargs)
        except Exception as e:
            logger.error(f"Error with active provider {self.active_provider}: {e}")
            
            # Try fallback providers
            for fallback_name in self.fallback_providers:
                if fallback_name in self.providers and fallback_name != self.active_provider:
                    try:
                        logger.info(f"Trying fallback provider: {fallback_name}")
                        fallback_provider = self.providers[fallback_name]
                        return await fallback_provider.generate_response(messages, functions, **kwargs)
                    except Exception as fallback_error:
                        logger.error(f"Fallback provider {fallback_name} also failed: {fallback_error}")
                        continue
            
            # All providers failed
            raise e
    
    async def stream_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response using active provider.
        
        Args:
            messages: Conversation messages
            functions: Available functions
            **kwargs: Additional parameters
            
        Yields:
            Response chunks
        """
        provider = self.get_active_provider()
        if not provider:
            raise ValueError("No active LLM provider")
        
        async for chunk in provider.stream_response(messages, functions, **kwargs):
            yield chunk
    
    async def test_all_providers(self) -> Dict[str, bool]:
        """
        Test all providers.
        
        Returns:
            Dictionary of provider names and their status
        """
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.test_connection()
            except Exception as e:
                logger.error(f"Provider {name} test failed: {e}")
                results[name] = False
        
        return results
    
    async def cleanup(self) -> None:
        """Cleanup all providers."""
        for provider in self.providers.values():
            try:
                await provider.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up provider: {e}")


# Utility functions

def create_message(role: str, content: str, **kwargs) -> Message:
    """Create a message with specified role and content."""
    return Message(
        role=MessageRole(role),
        content=content,
        **kwargs
    )


def messages_to_dict(messages: List[Message]) -> List[Dict[str, Any]]:
    """Convert list of messages to list of dictionaries."""
    return [msg.to_dict() for msg in messages]


def messages_from_dict(data: List[Dict[str, Any]]) -> List[Message]:
    """Convert list of dictionaries to list of messages."""
    return [Message.from_dict(msg_data) for msg_data in data]
