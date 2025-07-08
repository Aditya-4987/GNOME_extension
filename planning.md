# AI GNOME Assistant - LLM Code Generation Specification

## Project Overview for Code Generation

You are tasked with generating code for a production-ready AI personal assistant integrated with GNOME desktop environment on Arch Linux. This system uses a service-first architecture where the core intelligence runs as a systemd user service, with minimal UI components in GNOME Shell extension.

## Critical Architecture Constraints

### MANDATORY Design Principles
1. **Service-First Architecture**: All core logic in Python systemd service, NOT in GNOME Shell extension
2. **Minimal Extension**: Extension only handles UI rendering and basic system integration
3. **Security-Gated Operations**: Every system operation requires explicit user permission
4. **Modular Tool System**: Tools are separate, registerable modules with clear interfaces
5. **Multi-Modal Interface**: CLI, web UI, voice, and extension interfaces all supported

### Technology Stack Requirements
- **Backend Service**: Python 3.11+ with FastAPI, running as systemd user service
- **Extension**: GJS (GNOME JavaScript) with GTK4/Adwaita
- **Communication**: Unix domain sockets (primary), WebSocket (fallback)
- **Database**: SQLite for structured data, ChromaDB for vector embeddings
- **LLM Integration**: Abstract interface supporting Ollama, OpenAI, Anthropic APIs
- **Voice**: SpeechRecognition + Piper TTS
- **System Integration**: DBus, AT-SPI, limited X11/Wayland automation

## Directory Structure Template

```
gnome-ai-assistant/
├── src/
│   ├── gnome_ai_assistant/
│   │   ├── __init__.py
│   │   ├── main.py                 # Service entry point
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── service.py          # Main FastAPI service
│   │   │   ├── config.py           # Configuration management
│   │   │   ├── permissions.py      # Security permission system
│   │   │   ├── memory.py           # Memory and context management
│   │   │   └── agentic_engine.py   # OODA loop implementation
│   │   ├── llm/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Abstract LLM interface
│   │   │   ├── ollama.py           # Ollama integration
│   │   │   ├── openai.py           # OpenAI API integration
│   │   │   └── prompt_manager.py   # Prompt templates and management
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Tool registration system
│   │   │   ├── file_manager.py     # File operations
│   │   │   ├── window_manager.py   # Window control via AT-SPI
│   │   │   ├── spotify.py          # Spotify DBus integration
│   │   │   ├── package_manager.py  # Arch Linux package management
│   │   │   └── system_control.py   # System administration
│   │   ├── interfaces/
│   │   │   ├── __init__.py
│   │   │   ├── cli.py              # Command-line interface
│   │   │   ├── web.py              # Web interface (fallback)
│   │   │   ├── voice.py            # Voice interface
│   │   │   └── notifications.py    # GNOME notifications
│   │   ├── perception/
│   │   │   ├── __init__.py
│   │   │   ├── screen_reader.py    # OCR and AT-SPI integration
│   │   │   ├── context_manager.py  # Context awareness
│   │   │   └── clipboard_monitor.py # Clipboard integration
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── dbus_helper.py      # DBus utilities
│   │       ├── security.py         # Security utilities
│   │       └── logger.py           # Logging configuration
│   └── extension/
│       ├── extension.js            # Main extension file
│       ├── metadata.json           # Extension metadata
│       ├── prefs.js                # Extension preferences
│       └── ui/
│           ├── main.js             # Main UI components
│           ├── chat_window.js      # Chat interface
│           └── permission_dialog.js # Permission prompts
├── config/
│   ├── systemd/
│   │   └── gnome-ai-assistant.service
│   ├── settings.json               # Default configuration
│   └── tools_config.json          # Tool configurations
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── docs/
├── scripts/
│   ├── install.sh                  # Installation script
│   ├── setup_systemd.sh           # Systemd service setup
│   └── install_extension.sh       # Extension installation
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Core Service Implementation Requirements

### 1. Service Entry Point (main.py)
```python
# MANDATORY: Service must be startable as systemd user service
# Must handle SIGTERM gracefully
# Must provide health check endpoint
# Must initialize all subsystems in correct order

import asyncio
import signal
import sys
from gnome_ai_assistant.core.service import AssistantService

async def main():
    service = AssistantService()
    # Setup signal handlers for graceful shutdown
    # Initialize all subsystems
    # Start FastAPI server on Unix socket
    # Handle service lifecycle
```

### 2. Core Service Class (core/service.py)
```python
# MANDATORY: FastAPI application with Unix socket support
# Must provide these endpoints:
# - POST /chat - Main chat interface
# - POST /execute_tool - Tool execution
# - GET /status - Service status
# - GET /tools - Available tools
# - POST /permissions - Permission management

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import asyncio

class AssistantService:
    def __init__(self):
        self.app = FastAPI(title="GNOME AI Assistant")
        self.llm_engine = None
        self.tool_registry = None
        self.permission_manager = None
        self.memory_manager = None
        self.agentic_engine = None
        
    async def initialize(self):
        # Initialize all subsystems
        pass
        
    async def start(self):
        # Start FastAPI server on Unix socket
        config = uvicorn.Config(
            app=self.app,
            uds="/tmp/gnome-ai-assistant.sock",
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()
```

### 3. Permission System (core/permissions.py)
```python
# MANDATORY: All system operations must be gated by permissions
# Must support: one-time, session-based, and permanent permissions
# Must integrate with GNOME notifications for user prompts
# Must maintain audit log of all permission grants/denials

from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional
import json
import sqlite3

class PermissionLevel(Enum):
    DENY = "deny"
    ALLOW_ONCE = "allow_once"
    ALLOW_SESSION = "allow_session"
    ALLOW_PERMANENT = "allow_permanent"

@dataclass
class PermissionRequest:
    tool_name: str
    action: str
    description: str
    risk_level: str  # low, medium, high, critical
    required_capabilities: List[str]

class PermissionManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.session_permissions = {}
        self.initialize_database()
    
    async def request_permission(self, request: PermissionRequest) -> PermissionLevel:
        # Check existing permissions
        # Send notification to user if needed
        # Return permission level
        pass
    
    def grant_permission(self, request: PermissionRequest, level: PermissionLevel):
        # Store permission in appropriate scope
        pass
```

### 4. Tool System (tools/base.py)
```python
# MANDATORY: All tools must inherit from BaseTool
# Must provide: name, description, required_permissions, execute method
# Must support function calling format for LLM integration
# Must handle errors gracefully and return structured responses

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass
import json

@dataclass
class ToolResponse:
    success: bool
    result: Any
    error: Optional[str] = None
    requires_permission: bool = False
    permission_request: Optional[PermissionRequest] = None

class BaseTool(ABC):
    def __init__(self):
        self.name = self.__class__.__name__.lower()
        self.description = ""
        self.required_permissions = []
    
    @abstractmethod
    async def execute(self, **kwargs) -> ToolResponse:
        pass
    
    def to_function_schema(self) -> Dict[str, Any]:
        # Return OpenAI function calling format
        pass

class ToolRegistry:
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, tool: BaseTool):
        self.tools[tool.name] = tool
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        return [tool.to_function_schema() for tool in self.tools.values()]
    
    async def execute_tool(self, name: str, **kwargs) -> ToolResponse:
        if name not in self.tools:
            return ToolResponse(success=False, error=f"Tool {name} not found")
        return await self.tools[name].execute(**kwargs)
```

### 5. LLM Integration (llm/base.py)
```python
# MANDATORY: Abstract interface for LLM providers
# Must support function calling format
# Must handle streaming responses
# Must manage context and memory integration

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass

@dataclass
class Message:
    role: str  # user, assistant, system
    content: str
    function_call: Optional[Dict[str, Any]] = None

@dataclass
class LLMResponse:
    content: str
    function_calls: List[Dict[str, Any]]
    finish_reason: str
    usage: Dict[str, int]

class BaseLLM(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    @abstractmethod
    async def generate_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> LLMResponse:
        pass
    
    @abstractmethod
    async def stream_response(
        self, 
        messages: List[Message], 
        functions: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncIterator[str]:
        pass
```

### 6. Agentic Engine (core/agentic_engine.py)
```python
# MANDATORY: Implements Plan-Do-Check-Act (OODA) loop
# Must break down complex tasks into steps
# Must handle error recovery and replanning
# Must provide progress feedback to user

from typing import List, Dict, Any
from dataclasses import dataclass
from enum import Enum

class TaskStatus(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    CHECKING = "checking"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class TaskStep:
    tool_name: str
    action: str
    parameters: Dict[str, Any]
    description: str
    status: TaskStatus = TaskStatus.PLANNING

@dataclass
class Task:
    user_request: str
    steps: List[TaskStep]
    current_step: int = 0
    status: TaskStatus = TaskStatus.PLANNING
    context: Dict[str, Any] = None

class AgenticEngine:
    def __init__(self, llm_engine, tool_registry, permission_manager):
        self.llm_engine = llm_engine
        self.tool_registry = tool_registry
        self.permission_manager = permission_manager
        self.active_tasks = {}
    
    async def process_request(self, user_request: str, context: Dict[str, Any]) -> Task:
        # Generate plan using LLM
        # Execute steps with error handling
        # Provide progress updates
        # Handle permission requests
        pass
```

## GNOME Shell Extension Requirements

### Extension Metadata (metadata.json)
```json
{
  "uuid": "gnome-ai-assistant@example.com",
  "name": "AI Assistant",
  "description": "AI-powered personal assistant for GNOME",
  "shell-version": ["45", "46", "47", "48"],
  "version": 1,
  "settings-schema": "org.gnome.shell.extensions.ai-assistant"
}
```

### Main Extension (extension.js)
```javascript
// MANDATORY: Minimal extension that only handles UI
// Must connect to service via Unix socket
// Must gracefully handle service unavailability
// Must provide fallback to web interface

import GObject from 'gi://GObject';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';

const AIAssistantIndicator = GObject.registerClass(
class AIAssistantIndicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, _('AI Assistant'));
        
        // Create panel icon
        this.add_child(new St.Icon({
            icon_name: 'system-run-symbolic',
            style_class: 'system-status-icon',
        }));
        
        // Initialize connection to service
        this._initializeServiceConnection();
        
        // Create menu items
        this._createMenuItems();
    }
    
    _initializeServiceConnection() {
        // Connect to Unix socket
        // Handle connection errors gracefully
        // Implement reconnection logic
    }
    
    _createMenuItems() {
        // Chat interface
        // Settings
        // Service status
        // Emergency stop
    }
});

export default class AIAssistantExtension extends Extension {
    enable() {
        this._indicator = new AIAssistantIndicator();
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }
    
    disable() {
        this._indicator?.destroy();
        this._indicator = null;
    }
}
```

## Installation and Configuration

### Systemd Service (config/systemd/gnome-ai-assistant.service)
```ini
[Unit]
Description=GNOME AI Assistant Service
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
ExecStart=%h/.local/share/gnome-ai-assistant/venv/bin/python -m gnome_ai_assistant.main
Restart=always
RestartSec=3
Environment=DISPLAY=:0
Environment=XDG_RUNTIME_DIR=%t
Environment=PATH=%h/.local/share/gnome-ai-assistant/venv/bin:/usr/bin:/bin
WorkingDirectory=%h/.local/share/gnome-ai-assistant

[Install]
WantedBy=default.target
```

### Installation Script (scripts/install.sh)
```bash
#!/bin/bash
# MANDATORY: Must handle Arch Linux package dependencies
# Must set up Python virtual environment
# Must install and enable systemd service
# Must install GNOME Shell extension
# Must configure permissions and security

set -e

# Check for Arch Linux
if ! command -v pacman &> /dev/null; then
    echo "Error: This installer is designed for Arch Linux"
    exit 1
fi

# Install system dependencies
sudo pacman -S --needed python python-pip git dbus glib2 gcc webkit2gtk-4.1 \
    tesseract tesseract-data-eng speech-dispatcher festival \
    libnotify libappindicator-gtk3 xdg-utils nodejs npm typescript

# Create installation directory
INSTALL_DIR="$HOME/.local/share/gnome-ai-assistant"
mkdir -p "$INSTALL_DIR"

# Set up Python virtual environment
python -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

# Install Python dependencies
pip install -r requirements.txt

# Copy source files
cp -r src/* "$INSTALL_DIR/"

# Install systemd service
mkdir -p "$HOME/.config/systemd/user"
envsubst < config/systemd/gnome-ai-assistant.service > "$HOME/.config/systemd/user/gnome-ai-assistant.service"

# Enable and start service
systemctl --user daemon-reload
systemctl --user enable gnome-ai-assistant.service
systemctl --user start gnome-ai-assistant.service

# Install GNOME Shell extension
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com"
mkdir -p "$EXTENSION_DIR"
cp -r src/extension/* "$EXTENSION_DIR/"

echo "Installation complete. Please log out and log back in to activate the extension."
```

## Code Generation Guidelines

### When generating code, ensure:

1. **Error Handling**: Every async function must have try-catch blocks
2. **Logging**: Use structured logging with appropriate log levels
3. **Type Hints**: All Python functions must have proper type hints
4. **Documentation**: All classes and functions must have docstrings
5. **Security**: All user inputs must be validated and sanitized
6. **Performance**: Use async/await patterns consistently
7. **Testing**: Generate corresponding test files for all modules

### Code Generation Order:
1. Core service infrastructure (service.py, config.py)
2. Permission system (permissions.py)
3. Tool system (base.py, then specific tools)
4. LLM integration (base.py, then specific providers)
5. Agentic engine (agentic_engine.py)
6. GNOME Shell extension (extension.js)
7. Installation and configuration scripts

### Critical Implementation Notes:
- Use Unix domain sockets for primary communication
- Implement proper signal handling for graceful shutdown
- Use SQLite with proper connection pooling
- Implement comprehensive error recovery
- Use DBus for system integration whenever possible
- Minimize X11/Wayland automation usage
- Implement proper resource cleanup
- Use async patterns throughout
- Handle GNOME Shell extension API changes gracefully

This specification provides the complete architectural blueprint for generating production-ready code for the AI GNOME assistant system.