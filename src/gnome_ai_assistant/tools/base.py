"""Base classes and registry for the tool system."""

import asyncio
import importlib
import inspect
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, get_type_hints
from dataclasses import dataclass
import json
import logging
from pathlib import Path

from ..utils.logger import get_logger
from ..core.permissions import PermissionRequest, RiskLevel

logger = get_logger("tools")


@dataclass
class ToolResponse:
    """Response from tool execution."""
    success: bool
    result: Any
    error: Optional[str] = None
    requires_permission: bool = False
    permission_request: Optional[PermissionRequest] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "requires_permission": self.requires_permission,
            "permission_request": self.permission_request.__dict__ if self.permission_request else None,
            "metadata": self.metadata
        }


@dataclass
class ToolParameter:
    """Represents a tool parameter definition."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any = None
    enum_values: Optional[List[str]] = None
    
    def to_json_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format for function calling."""
        schema = {
            "type": self.type,
            "description": self.description
        }
        
        if self.enum_values:
            schema["enum"] = self.enum_values
        
        if self.default is not None:
            schema["default"] = self.default
            
        return schema


class BaseTool(ABC):
    """Base class for all tools."""
    
    def __init__(self):
        """Initialize the tool."""
        self.name = self.__class__.__name__.lower().replace("tool", "")
        self.description = ""
        self.required_permissions = []
        self.risk_level = RiskLevel.LOW
        self.category = "general"
        self.enabled = True
        self.parameters: List[ToolParameter] = []
        
        # Auto-discover parameters from execute method signature
        self._discover_parameters()
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResponse:
        """
        Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool parameters
            
        Returns:
            Tool execution response
        """
        pass
    
    def _discover_parameters(self) -> None:
        """Automatically discover parameters from execute method signature."""
        try:
            sig = inspect.signature(self.execute)
            type_hints = get_type_hints(self.execute)
            
            for param_name, param in sig.parameters.items():
                if param_name == "kwargs":
                    continue
                    
                # Get parameter type
                param_type = type_hints.get(param_name, str)
                type_name = self._get_json_type(param_type)
                
                # Check if required
                required = param.default == inspect.Parameter.empty
                default = None if required else param.default
                
                # Create parameter definition
                tool_param = ToolParameter(
                    name=param_name,
                    type=type_name,
                    description=f"Parameter {param_name}",
                    required=required,
                    default=default
                )
                
                self.parameters.append(tool_param)
                
        except Exception as e:
            logger.warning(f"Failed to auto-discover parameters for {self.name}: {e}")
    
    def _get_json_type(self, python_type) -> str:
        """Convert Python type to JSON schema type."""
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        # Handle Union types (e.g., Optional[str])
        if hasattr(python_type, "__origin__"):
            if python_type.__origin__ is list:
                return "array"
            elif python_type.__origin__ is dict:
                return "object"
            else:
                # For Union types, use the first non-None type
                args = getattr(python_type, "__args__", ())
                for arg in args:
                    if arg is not type(None):
                        return self._get_json_type(arg)
        
        return type_mapping.get(python_type, "string")
    
    def to_function_schema(self) -> Dict[str, Any]:
        """
        Convert tool to OpenAI function calling schema.
        
        Returns:
            Function schema dictionary
        """
        properties = {}
        required = []
        
        for param in self.parameters:
            properties[param.name] = param.to_json_schema()
            if param.required:
                required.append(param.name)
        
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            },
            "metadata": {
                "category": self.category,
                "risk_level": self.risk_level.value,
                "required_permissions": self.required_permissions
            }
        }
    
    def validate_parameters(self, **kwargs) -> List[str]:
        """
        Validate parameters against tool schema.
        
        Args:
            **kwargs: Parameters to validate
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required parameters
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                errors.append(f"Missing required parameter: {param.name}")
        
        # Check parameter types (basic validation)
        for param_name, value in kwargs.items():
            param = next((p for p in self.parameters if p.name == param_name), None)
            if param:
                if not self._validate_type(value, param.type):
                    errors.append(f"Invalid type for {param_name}: expected {param.type}")
                
                if param.enum_values and value not in param.enum_values:
                    errors.append(f"Invalid value for {param_name}: must be one of {param.enum_values}")
        
        return errors
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type."""
        type_checks = {
            "string": lambda v: isinstance(v, str),
            "integer": lambda v: isinstance(v, int),
            "number": lambda v: isinstance(v, (int, float)),
            "boolean": lambda v: isinstance(v, bool),
            "array": lambda v: isinstance(v, list),
            "object": lambda v: isinstance(v, dict)
        }
        
        check_func = type_checks.get(expected_type, lambda v: True)
        return check_func(value)
    
    async def check_permissions(self, permission_manager, **kwargs) -> Optional[PermissionRequest]:
        """
        Check if tool execution requires permissions.
        
        Args:
            permission_manager: Permission manager instance
            **kwargs: Tool parameters
            
        Returns:
            Permission request if needed, None otherwise
        """
        if not self.required_permissions:
            return None
        
        # Create permission request
        request = PermissionRequest(
            tool_name=self.name,
            action=f"execute_{self.name}",
            description=f"Execute {self.description}",
            risk_level=self.risk_level,
            required_capabilities=self.required_permissions,
            parameters={k: str(v) for k, v in kwargs.items()}
        )
        
        return request
    
    def get_help(self) -> str:
        """Get help text for the tool."""
        help_text = f"Tool: {self.name}\n"
        help_text += f"Description: {self.description}\n"
        help_text += f"Category: {self.category}\n"
        help_text += f"Risk Level: {self.risk_level.value}\n"
        
        if self.parameters:
            help_text += "\nParameters:\n"
            for param in self.parameters:
                required_str = " (required)" if param.required else " (optional)"
                help_text += f"  - {param.name} ({param.type}){required_str}: {param.description}\n"
        
        if self.required_permissions:
            help_text += f"\nRequired Permissions: {', '.join(self.required_permissions)}\n"
        
        return help_text


class ToolRegistry:
    """Registry for managing and executing tools."""
    
    def __init__(self):
        """Initialize the tool registry."""
        self.tools: Dict[str, BaseTool] = {}
        self.categories: Dict[str, List[str]] = {}
        self.tool_modules: List[str] = []
        self.permission_manager = None
    
    async def initialize(self) -> None:
        """Initialize the tool registry."""
        try:
            # Auto-discover and load tools
            await self._discover_tools()
            logger.info(f"Tool registry initialized with {len(self.tools)} tools")
        except Exception as e:
            logger.error(f"Failed to initialize tool registry: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup tool registry resources."""
        try:
            # Cleanup individual tools if they have cleanup methods
            for tool in self.tools.values():
                if hasattr(tool, "cleanup"):
                    try:
                        await tool.cleanup()
                    except Exception as e:
                        logger.error(f"Error cleaning up tool {tool.name}: {e}")
            
            logger.info("Tool registry cleanup completed")
        except Exception as e:
            logger.error(f"Error during tool registry cleanup: {e}")
    
    def register_tool(self, tool: BaseTool) -> None:
        """
        Register a tool in the registry.
        
        Args:
            tool: Tool instance to register
        """
        self.tools[tool.name] = tool
        
        # Add to category
        if tool.category not in self.categories:
            self.categories[tool.category] = []
        
        if tool.name not in self.categories[tool.category]:
            self.categories[tool.category].append(tool.name)
        
        logger.info(f"Registered tool: {tool.name}")
    
    def unregister_tool(self, name: str) -> bool:
        """
        Unregister a tool from the registry.
        
        Args:
            name: Tool name to unregister
            
        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self.tools:
            tool = self.tools[name]
            del self.tools[name]
            
            # Remove from category
            if tool.category in self.categories:
                if name in self.categories[tool.category]:
                    self.categories[tool.category].remove(name)
                
                # Remove empty categories
                if not self.categories[tool.category]:
                    del self.categories[tool.category]
            
            logger.info(f"Unregistered tool: {name}")
            return True
        
        return False
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        return self.tools.get(name)
    
    def list_tools(self, category: Optional[str] = None, enabled_only: bool = True) -> List[str]:
        """
        List available tools.
        
        Args:
            category: Filter by category (optional)
            enabled_only: Only return enabled tools
            
        Returns:
            List of tool names
        """
        tools = []
        
        if category:
            tools = self.categories.get(category, [])
        else:
            tools = list(self.tools.keys())
        
        if enabled_only:
            tools = [name for name in tools if self.tools[name].enabled]
        
        return tools
    
    def get_tool_schemas(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get tool schemas for function calling.
        
        Args:
            category: Filter by category (optional)
            
        Returns:
            List of tool function schemas
        """
        tool_names = self.list_tools(category=category)
        return [self.tools[name].to_function_schema() for name in tool_names]
    
    async def execute_tool(self, name: str, permission_manager=None, **kwargs) -> ToolResponse:
        """
        Execute a tool with given parameters.
        
        Args:
            name: Tool name
            permission_manager: Permission manager for checking permissions
            **kwargs: Tool parameters
            
        Returns:
            Tool execution response
        """
        try:
            # Check if tool exists
            if name not in self.tools:
                return ToolResponse(
                    success=False,
                    error=f"Tool '{name}' not found"
                )
            
            tool = self.tools[name]
            
            # Check if tool is enabled
            if not tool.enabled:
                return ToolResponse(
                    success=False,
                    error=f"Tool '{name}' is disabled"
                )
            
            # Validate parameters
            validation_errors = tool.validate_parameters(**kwargs)
            if validation_errors:
                return ToolResponse(
                    success=False,
                    error=f"Parameter validation failed: {', '.join(validation_errors)}"
                )
            
            # Check permissions
            if permission_manager and tool.required_permissions:
                permission_request = await tool.check_permissions(permission_manager, **kwargs)
                if permission_request:
                    from ..core.permissions import PermissionLevel
                    
                    level = await permission_manager.request_permission(permission_request)
                    if level == PermissionLevel.DENY:
                        return ToolResponse(
                            success=False,
                            error="Permission denied",
                            requires_permission=True,
                            permission_request=permission_request
                        )
            
            # Execute the tool
            logger.info(f"Executing tool: {name} with parameters: {kwargs}")
            result = await tool.execute(**kwargs)
            
            logger.info(f"Tool {name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            return ToolResponse(
                success=False,
                error=f"Tool execution failed: {str(e)}"
            )
    
    async def _discover_tools(self) -> None:
        """Automatically discover and load tools from the tools package."""
        try:
            tools_package = "gnome_ai_assistant.tools"
            tools_dir = Path(__file__).parent.parent / "tools"
            
            # Get all Python files in tools directory
            tool_files = [f.stem for f in tools_dir.glob("*.py") if f.stem != "__init__" and f.stem != "base"]
            
            for tool_file in tool_files:
                try:
                    module_name = f"{tools_package}.{tool_file}"
                    module = importlib.import_module(module_name)
                    
                    # Find tool classes in module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseTool) and 
                            obj != BaseTool):
                            
                            # Instantiate and register tool
                            tool_instance = obj()
                            self.register_tool(tool_instance)
                            
                            logger.info(f"Loaded tool from {module_name}: {tool_instance.name}")
                
                except Exception as e:
                    logger.error(f"Failed to load tool from {tool_file}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to discover tools: {e}")
    
    def get_categories(self) -> List[str]:
        """Get list of tool categories."""
        return list(self.categories.keys())
    
    def get_tools_by_category(self, category: str) -> List[BaseTool]:
        """
        Get all tools in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of tool instances
        """
        tool_names = self.categories.get(category, [])
        return [self.tools[name] for name in tool_names if name in self.tools]
    
    def search_tools(self, query: str) -> List[BaseTool]:
        """
        Search tools by name or description.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tools
        """
        query_lower = query.lower()
        matching_tools = []
        
        for tool in self.tools.values():
            if (query_lower in tool.name.lower() or 
                query_lower in tool.description.lower() or
                query_lower in tool.category.lower()):
                matching_tools.append(tool)
        
        return matching_tools
    
    def get_tool_help(self, name: str) -> Optional[str]:
        """
        Get help text for a tool.
        
        Args:
            name: Tool name
            
        Returns:
            Help text or None if tool not found
        """
        tool = self.get_tool(name)
        return tool.get_help() if tool else None
    
    def enable_tool(self, name: str) -> bool:
        """Enable a tool."""
        if name in self.tools:
            self.tools[name].enabled = True
            return True
        return False
    
    def disable_tool(self, name: str) -> bool:
        """Disable a tool."""
        if name in self.tools:
            self.tools[name].enabled = False
            return True
        return False
