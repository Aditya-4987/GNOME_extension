"""
LLM module for GNOME AI Assistant.

This module provides abstract interfaces and implementations for various
Large Language Model providers including Ollama, OpenAI, and Anthropic.
"""

from .base import BaseLLM, Message, LLMResponse
from .ollama import OllamaLLM
from .openai import OpenAILLM

__all__ = [
    "BaseLLM",
    "Message", 
    "LLMResponse",
    "OllamaLLM",
    "OpenAILLM",
]
