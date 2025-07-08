"""Ollama LLM provider implementation."""

import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncIterator
import aiohttp
import logging

from .base import BaseLLM, Message, LLMResponse, LLMConfig
from ..utils.logger import get_logger

logger = get_logger("llm.ollama")


class OllamaLLM(BaseLLM):
    """Ollama LLM provider implementation."""
    
    def __init__(self, config: LLMConfig):
        """Initialize Ollama LLM provider."""
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> None:
        """Initialize Ollama provider."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.config.timeout)
        )
        await super().initialize()
    
    async def cleanup(self) -> None:
        """Cleanup Ollama provider."""
        if self.session:
            await self.session.close()
        await super().cleanup()
    
    async def test_connection(self) -> bool:
        """Test connection to Ollama server."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    
                    # Check if our model is available
                    model_available = any(self.config.model in model for model in models)
                    if not model_available:
                        logger.warning(f"Model {self.config.model} not found in Ollama. Available: {models}")
                        # Try to pull the model
                        await self._pull_model()
                    
                    return True
                else:
                    logger.error(f"Ollama server responded with status {response.status}")
                    return False
        
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False
    
    async def _pull_model(self) -> bool:
        """Pull model if not available."""
        try:
            logger.info(f"Pulling model {self.config.model} from Ollama...")
            
            async with self.session.post(
                f"{self.base_url}/api/pull",
                json={"name": self.config.model}
            ) as response:
                if response.status == 200:
                    # Read streaming response
                    async for line in response.content:
                        try:
                            status_data = json.loads(line.decode())
                            if status_data.get("status") == "success":
                                logger.info(f"Successfully pulled model {self.config.model}")
                                return True
                            elif "error" in status_data:
                                logger.error(f"Error pulling model: {status_data['error']}")
                                return False
                        except json.JSONDecodeError:
                            continue
                
                return False
        
        except Exception as e:
            logger.error(f"Failed to pull model: {e}")
            return False
    
    async def generate_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Ollama."""
        try:
            if not self.session:
                await self.initialize()
            
            # Prepare request data
            request_data = {
                "model": self.config.model,
                "messages": self.prepare_messages(messages),
                "stream": False,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens)
                }
            }
            
            # Add functions if provided (Ollama may not support this yet)
            if functions:
                request_data["tools"] = self.format_functions_for_api(functions)
            
            # Make request
            async with self.session.post(
                f"{self.base_url}/api/chat",
                json=request_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")
                
                response_data = await response.json()
                
                # Extract response content
                message = response_data.get("message", {})
                content = message.get("content", "")
                
                # Extract function calls (if supported)
                function_calls = self.extract_function_calls(message)
                
                # Get usage information
                usage = {
                    "prompt_tokens": response_data.get("prompt_eval_count", 0),
                    "completion_tokens": response_data.get("eval_count", 0),
                    "total_tokens": response_data.get("prompt_eval_count", 0) + response_data.get("eval_count", 0)
                }
                
                return LLMResponse(
                    content=content,
                    function_calls=function_calls,
                    finish_reason=response_data.get("done_reason", "stop"),
                    usage=usage,
                    model=self.config.model,
                    metadata={
                        "eval_duration": response_data.get("eval_duration"),
                        "load_duration": response_data.get("load_duration"),
                        "prompt_eval_duration": response_data.get("prompt_eval_duration")
                    }
                )
        
        except Exception as e:
            logger.error(f"Error generating response with Ollama: {e}")
            raise
    
    async def stream_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream response using Ollama."""
        try:
            if not self.session:
                await self.initialize()
            
            # Prepare request data
            request_data = {
                "model": self.config.model,
                "messages": self.prepare_messages(messages),
                "stream": True,
                "options": {
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "num_predict": kwargs.get("max_tokens", self.config.max_tokens)
                }
            }
            
            # Add functions if provided
            if functions:
                request_data["tools"] = self.format_functions_for_api(functions)
            
            # Make streaming request
            async with self.session.post(
                f"{self.base_url}/api/chat",
                json=request_data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")
                
                # Read streaming response
                async for line in response.content:
                    if line:
                        try:
                            chunk_data = json.loads(line.decode())
                            message = chunk_data.get("message", {})
                            content = message.get("content", "")
                            
                            if content:
                                yield content
                            
                            # Check if done
                            if chunk_data.get("done", False):
                                break
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Error streaming response with Ollama: {e}")
            raise
    
    def format_functions_for_api(self, functions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format functions for Ollama API."""
        # Ollama may use a different format for tools/functions
        # This is a basic implementation that may need adjustment
        formatted_functions = []
        
        for func in functions:
            formatted_func = {
                "type": "function",
                "function": {
                    "name": func["name"],
                    "description": func["description"],
                    "parameters": func.get("parameters", {})
                }
            }
            formatted_functions.append(formatted_func)
        
        return formatted_functions
    
    async def list_models(self) -> List[str]:
        """List available models in Ollama."""
        try:
            if not self.session:
                await self.initialize()
            
            async with self.session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    return [model["name"] for model in data.get("models", [])]
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
            
            async with self.session.post(
                f"{self.base_url}/api/show",
                json={"name": model}
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.error(f"Failed to get model info: {response.status}")
                    return {}
        
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return {}
    
    async def delete_model(self, model_name: str) -> bool:
        """Delete a model from Ollama."""
        try:
            if not self.session:
                await self.initialize()
            
            async with self.session.delete(
                f"{self.base_url}/api/delete",
                json={"name": model_name}
            ) as response:
                return response.status == 200
        
        except Exception as e:
            logger.error(f"Error deleting model: {e}")
            return False
