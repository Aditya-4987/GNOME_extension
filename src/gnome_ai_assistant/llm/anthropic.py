"""
Anthropic Claude API integration for GNOME AI Assistant.

This module provides integration with Anthropic's Claude API
for advanced language model capabilities.
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, AsyncIterator, Union
import httpx
from anthropic import AsyncAnthropic
from anthropic.types import Message, MessageParam, ToolParam

from .base import BaseLLM, Message as BaseMessage, LLMResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AnthropicLLM(BaseLLM):
    """Anthropic Claude API integration."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Anthropic LLM.
        
        Args:
            config: LLM configuration including API key and model settings
        """
        super().__init__(config)
        
        self.api_key = config.get("api_key", "")
        self.model = config.get("model", "claude-3-sonnet-20240229")
        self.max_tokens = config.get("max_tokens", 4096)
        self.temperature = config.get("temperature", 0.7)
        self.timeout = config.get("timeout", 30)
        
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        # Initialize client
        self.client = AsyncAnthropic(
            api_key=self.api_key,
            timeout=self.timeout
        )
        
        logger.info(f"Initialized Anthropic LLM with model: {self.model}")
    
    async def test_connection(self) -> bool:
        """Test connection to Anthropic API."""
        try:
            # Simple test message
            test_messages = [
                {"role": "user", "content": "Hello"}
            ]
            
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=test_messages
            )
            
            logger.info("Anthropic API connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Anthropic API connection test failed: {e}")
            return False
    
    def _convert_messages(self, messages: List[BaseMessage]) -> List[MessageParam]:
        """Convert base messages to Anthropic format."""
        converted = []
        
        for msg in messages:
            if msg.role == "system":
                # Anthropic handles system messages differently
                # Add as first user message with system prefix
                content = f"System: {msg.content}"
                if converted and converted[0]["role"] == "user":
                    converted[0]["content"] = content + "\n\n" + converted[0]["content"]
                else:
                    converted.insert(0, {"role": "user", "content": content})
            else:
                # Handle function calls
                if msg.function_call:
                    # Convert function call to tool use format
                    tool_use = {
                        "type": "tool_use",
                        "id": f"call_{len(converted)}",
                        "name": msg.function_call.get("name", ""),
                        "input": json.loads(msg.function_call.get("arguments", "{}"))
                    }
                    converted.append({
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": msg.content or ""},
                            tool_use
                        ]
                    })
                else:
                    converted.append({
                        "role": msg.role,
                        "content": msg.content
                    })
        
        return converted
    
    def _convert_functions_to_tools(self, functions: Optional[List[Dict[str, Any]]]) -> Optional[List[ToolParam]]:
        """Convert OpenAI function format to Anthropic tools format."""
        if not functions:
            return None
        
        tools = []
        for func in functions:
            tool = {
                "name": func["name"],
                "description": func["description"],
                "input_schema": func["parameters"]
            }
            tools.append(tool)
        
        return tools
    
    async def generate_response(
        self, 
        messages: List[BaseMessage], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using Anthropic API.
        
        Args:
            messages: List of conversation messages
            functions: Optional list of available functions
            **kwargs: Additional parameters
            
        Returns:
            LLM response with content and metadata
        """
        try:
            # Convert messages
            anthropic_messages = self._convert_messages(messages)
            
            # Convert functions to tools
            tools = self._convert_functions_to_tools(functions)
            
            # Prepare request parameters
            request_params = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "messages": anthropic_messages
            }
            
            if tools:
                request_params["tools"] = tools
            
            # Make API request
            response = await self.client.messages.create(**request_params)
            
            # Process response
            content = ""
            function_calls = []
            
            for content_block in response.content:
                if content_block.type == "text":
                    content += content_block.text
                elif content_block.type == "tool_use":
                    function_calls.append({
                        "name": content_block.name,
                        "arguments": json.dumps(content_block.input),
                        "id": content_block.id
                    })
            
            # Calculate usage
            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            }
            
            return LLMResponse(
                content=content.strip(),
                function_calls=function_calls,
                finish_reason=response.stop_reason or "stop",
                usage=usage
            )
            
        except Exception as e:
            logger.error(f"Error generating Anthropic response: {e}")
            raise
    
    async def stream_response(
        self, 
        messages: List[BaseMessage], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        Stream response from Anthropic API.
        
        Args:
            messages: List of conversation messages
            functions: Optional list of available functions
            **kwargs: Additional parameters
            
        Yields:
            Response content chunks
        """
        try:
            # Convert messages
            anthropic_messages = self._convert_messages(messages)
            
            # Convert functions to tools
            tools = self._convert_functions_to_tools(functions)
            
            # Prepare request parameters
            request_params = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", self.max_tokens),
                "temperature": kwargs.get("temperature", self.temperature),
                "messages": anthropic_messages,
                "stream": True
            }
            
            if tools:
                request_params["tools"] = tools
            
            # Stream response
            async with self.client.messages.stream(**request_params) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_delta":
                        if chunk.delta.type == "text_delta":
                            yield chunk.delta.text
            
        except Exception as e:
            logger.error(f"Error streaming Anthropic response: {e}")
            raise
    
    async def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for texts.
        Note: Anthropic doesn't provide embeddings API, 
        this is a placeholder for compatibility.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        logger.warning("Anthropic doesn't provide embeddings API")
        raise NotImplementedError("Anthropic doesn't provide embeddings API")
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model."""
        return {
            "provider": "anthropic",
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "supports_functions": True,
            "supports_streaming": True,
            "supports_embeddings": False
        }
    
    async def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Note: This is an approximation since Anthropic doesn't provide
        a public tokenizer.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters
        return len(text) // 4
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        if hasattr(self.client, 'close'):
            await self.client.close()
        logger.info("Anthropic LLM cleanup completed")


class AnthropicFunctionHandler:
    """Handle function calling with Anthropic API."""
    
    def __init__(self, llm: AnthropicLLM):
        """Initialize function handler."""
        self.llm = llm
    
    async def execute_function_call(
        self, 
        function_call: Dict[str, Any], 
        available_functions: Dict[str, callable]
    ) -> Dict[str, Any]:
        """
        Execute a function call and return the result.
        
        Args:
            function_call: Function call details
            available_functions: Map of function names to callables
            
        Returns:
            Function execution result
        """
        function_name = function_call.get("name")
        arguments = json.loads(function_call.get("arguments", "{}"))
        
        if function_name not in available_functions:
            return {
                "error": f"Function {function_name} not found",
                "function_name": function_name
            }
        
        try:
            # Execute function
            func = available_functions[function_name]
            if asyncio.iscoroutinefunction(func):
                result = await func(**arguments)
            else:
                result = func(**arguments)
            
            return {
                "result": result,
                "function_name": function_name,
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return {
                "error": str(e),
                "function_name": function_name,
                "success": False
            }
    
    async def process_tool_results(
        self, 
        messages: List[BaseMessage],
        tool_results: List[Dict[str, Any]]
    ) -> List[BaseMessage]:
        """
        Process tool results and add them to message history.
        
        Args:
            messages: Current message history
            tool_results: Results from tool execution
            
        Returns:
            Updated message history
        """
        updated_messages = messages.copy()
        
        # Add tool results as user messages
        for result in tool_results:
            result_message = BaseMessage(
                role="user",
                content=f"Tool {result['function_name']} result: {json.dumps(result)}"
            )
            updated_messages.append(result_message)
        
        return updated_messages
