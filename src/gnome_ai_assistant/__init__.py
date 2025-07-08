"""
GNOME AI Assistant - AI-powered personal assistant for GNOME desktop

This package provides a service-first architecture AI assistant that integrates
with the GNOME desktop environment through a systemd user service and optional
GNOME Shell extension.
"""

__version__ = "1.0.0"
__author__ = "GNOME AI Assistant Team"

# Import main components for easier access
from .core.service import AssistantService
from .core.config import AssistantConfig
from .core.permissions import PermissionManager, PermissionLevel
from .tools.base import BaseTool, ToolRegistry
from .llm.base import BaseLLM, Message, LLMResponse

__all__ = [
    "AssistantService",
    "AssistantConfig",
    "PermissionManager",
    "PermissionLevel",
    "BaseTool",
    "ToolRegistry",
    "BaseLLM",
    "Message",
    "LLMResponse",
]
