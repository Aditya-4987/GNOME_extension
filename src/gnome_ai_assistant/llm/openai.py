"""OpenAI LLM provider implementation."""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncIterator
import aiohttp
import logging

from .base import BaseLLM, Message, LLMResponse, LLMConfig
from ..utils.logger import get_logger

logger = get_logger("llm.openai")


class OpenAILLM(BaseLLM):
    """OpenAI LLM provider implementation."""
    
    def __init__(self, config: LLMConfig):
        """Initialize OpenAI LLM provider."""
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url or "https://api.openai.com/v1"
        self.session: Optional[aiohttp.ClientSession] = None
        
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
    
    async def initialize(self) -> None:
        """Initialize OpenAI provider."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        
        await super().initialize()
    
    async def cleanup(self) -> None:
        """Cleanup OpenAI provider."""
        if self.session:
            await self.session.close()
        await super().cleanup()
    
    async def test_connection(self) -> bool:
        """Test connection to OpenAI API."""
        try:
            if not self.session:
                await self.initialize()
            
            # Test with a simple completion
            test_messages = [{"role": "user", "content": "Hello"}]
            
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": test_messages,
                    "max_tokens": 1
                }
            ) as response:
                if response.status == 200:
                    return True
                elif response.status == 401:
                    logger.error("OpenAI API key is invalid")
                    return False
                else:
                    error_data = await response.json()
                    logger.error(f"OpenAI API error {response.status}: {error_data}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to connect to OpenAI: {e}")
            return False
    
    async def generate_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using OpenAI."""
        try:
            if not self.session:
                await self.initialize()
            
            # Prepare request data
            request_data = {
                "model": self.config.model,
                "messages": self.prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "stream": False
            }
            
            # Add functions if provided
            if functions:
                if self._supports_tools():
                    request_data["tools"] = self.format_functions_for_api(functions)
                    request_data["tool_choice"] = "auto"
                else:
                    request_data["functions"] = functions
                    request_data["function_call"] = "auto"
            
            # Add extra parameters
            if self.config.extra_params:
                request_data.update(self.config.extra_params)
            
            # Make request
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=request_data
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise Exception(f"OpenAI API error {response.status}: {error_data.get('error', {}).get('message', 'Unknown error')}")
                
                response_data = await response.json()
                
                # Extract response content
                choice = response_data["choices"][0]
                message = choice["message"]
                content = message.get("content") or ""
                
                # Extract function calls
                function_calls = self.extract_function_calls(message)
                
                # Get usage information
                usage = response_data.get("usage", {})
                
                return LLMResponse(
                    content=content,
                    function_calls=function_calls,
                    finish_reason=choice.get("finish_reason", "stop"),
                    usage=usage,
                    model=response_data.get("model", self.config.model),
                    metadata={
                        "id": response_data.get("id"),
                        "created": response_data.get("created"),
                        "system_fingerprint": response_data.get("system_fingerprint")
                    }
                )
        
        except Exception as e:
            logger.error(f"Error generating response with OpenAI: {e}")
            raise
    
    async def stream_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response using OpenAI."""
        try:
            if not self.session:
                await self.initialize()
            
            # Prepare request data
            request_data = {
                "model": self.config.model,
                "messages": self.prepare_messages(messages),
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "stream": True
            }
            
            # Add functions if provided
            if functions:
                if self._supports_tools():
                    request_data["tools"] = self.format_functions_for_api(functions)
                    request_data["tool_choice"] = "auto"
                else:
                    request_data["functions"] = functions
                    request_data["function_call"] = "auto"
            
            # Add extra parameters
            if self.config.extra_params:
                request_data.update(self.config.extra_params)
            
            # Make streaming request
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=request_data
            ) as response:
                if response.status != 200:
                    error_data = await response.json()
                    raise Exception(f"OpenAI API error {response.status}: {error_data.get('error', {}).get('message', 'Unknown error')}")
                
                # Read streaming response
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        line = line[6:]  # Remove 'data: ' prefix
                        
                        if line == '[DONE]':
                            break
                        
                        try:
                            chunk_data = json.loads(line)
                            choices = chunk_data.get("choices", [])
                            
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                
                                if content:
                                    yield content
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Error streaming response with OpenAI: {e}")
            raise
    
    def _supports_tools(self) -> bool:
        """Check if the model supports the newer tools format."""
        # GPT-3.5-turbo and GPT-4 models from late 2023 onwards support tools
        tools_supported_models = [
            "gpt-3.5-turbo-1106", "gpt-3.5-turbo-0125",
            "gpt-4-1106-preview", "gpt-4-0125-preview", "gpt-4-turbo-preview",
            "gpt-4", "gpt-4-turbo", "gpt-4o"
        ]
        
        return any(model in self.config.model for model in tools_supported_models)
    
    def format_functions_for_api(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format functions for OpenAI API."""
        if self._supports_tools():
            # Use newer tools format
            formatted_functions = []
            for func in functions:
                formatted_func = {
                    "type": "function",
                    "function": func
                }
                formatted_functions.append(formatted_func)
            return formatted_functions
        else:
            # Use legacy functions format
            return functions
    
    def extract_function_calls(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract function calls from OpenAI response."""
        function_calls = []
        
        # Check for legacy function_call
        if "function_call" in message:
            function_calls.append(message["function_call"])
        
        # Check for newer tool_calls
        if "tool_calls" in message:
            for tool_call in message["tool_calls"]:
                if tool_call.get("type") == "function":
                    function_calls.append(tool_call["function"])
        
        return function_calls
    
    async def list_models(self) -> List[str]:
        """List available models from OpenAI."""
        try:
            if not self.session:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["id"] for model in data.get("data", [])]
                    return sorted(models)
                else:
                    logger.error(f"Failed to list models: {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return []
    
    async def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """Get information about a model."""
        try:
            if not self.session:
                await self.initialize()
            
            model = model_name or self.config.model
            
            async with self.session.get(f"{self.base_url}/models/{model}") as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get model info: {response.status}")
                    return {}
        
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {}
    
    async def create_embedding(self, text: str, model: str = "text-embedding-ada-002") -> List[float]:
        """Create text embedding using OpenAI."""
        try:
            if not self.session:
                await self.initialize()
            
            async with self.session.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": model,
                    "input": text
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["data"][0]["embedding"]
                else:
                    error_data = await response.json()
                    raise Exception(f"Embedding error: {error_data}")
        
        except Exception as e:
            logger.error(f"Error creating embedding: {e}")
            raise
