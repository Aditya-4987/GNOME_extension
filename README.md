# GNOME AI Assistant

A powerful AI-powered personal assistant for the GNOME desktop environment, featuring service-first architecture and comprehensive system integration.

## 🚀 Project Status

**Current Version**: 1.0.0 (Production Ready)

✅ **Completed Features**:
- Core service architecture with FastAPI
- Multiple LLM provider support (OpenAI, Anthropic, Ollama)
- Comprehensive tool system with security permissions
- GNOME Shell extension with chat interface
- Memory management with vector embeddings
- Complete installation and deployment scripts
- Full test coverage

🔧 **Working Tools**:
- File Manager - Complete file operations
- Web Browser Control - URL handling and navigation
- Network Management - WiFi and connection tools
- System Control - Service and process management
- Spotify Integration - Music playback control
- Package Manager - System package operations
- Window Manager - Desktop window control

## Features

- **Service-First Architecture**: Core intelligence runs as a systemd user service
- **Multiple Interfaces**: CLI, web UI, voice commands, and GNOME Shell extension
- **Security-Gated Operations**: Explicit user permission required for all system operations
- **Modular Tool System**: Extensible tools for file management, system control, and more
- **LLM Integration**: Support for Ollama, OpenAI, and Anthropic APIs
- **Voice Interface**: Speech recognition and text-to-speech capabilities
- **Context Awareness**: Screen reading, clipboard monitoring, and context management
- **Memory Management**: Long-term memory with vector embeddings

## Quick Start

### Prerequisites

- Linux (tested on Ubuntu/Debian, should work on other distributions)
- Python 3.11 or higher
- GNOME Shell 45+ 
- Ollama (for local LLM) or API keys for cloud providers (OpenAI, Anthropic)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Aditya-4987/GNOME_extension.git
cd GNOME_extension
```

2. Run the installation script:
```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

3. Install the GNOME Shell extension:
```bash
chmod +x scripts/install_extension.sh
./scripts/install_extension.sh
```

4. Start the service:
```bash
systemctl --user start gnome-ai-assistant
```

5. Enable the GNOME Shell extension:
```bash
gnome-extensions enable gnome-ai-assistant@example.com
```

## Uninstallation

To completely remove GNOME AI Assistant from your system, see the detailed [Uninstall Guide](UNINSTALL.md).

Quick uninstall:
```bash
chmod +x scripts/uninstall.sh
./scripts/uninstall.sh
```

## Architecture

### Core Components

- **Service (`src/gnome_ai_assistant/core/service.py`)**: Main FastAPI service
- **Permission System (`src/gnome_ai_assistant/core/permissions.py`)**: Security and access control
- **LLM Integration (`src/gnome_ai_assistant/llm/`)**: Abstract LLM interface with multiple providers
- **Tool System (`src/gnome_ai_assistant/tools/`)**: Modular system tools
- **Agentic Engine (`src/gnome_ai_assistant/core/agentic_engine.py`)**: OODA loop implementation
- **Extension (`src/extension/`)**: GNOME Shell UI integration

### Communication

- **Primary**: Unix domain sockets (`/tmp/gnome-ai-assistant.sock`)
- **Fallback**: WebSocket connections
- **API**: RESTful HTTP endpoints

## Configuration

Configuration is managed through JSON files located at:
- `~/.config/gnome-ai-assistant/settings.json`
- Default settings in `config/settings.json`

### Key Configuration Sections

#### LLM Provider
```json
{
  "llm": {
    "provider": "ollama",
    "model": "llama2",
    "api_key": null,
    "base_url": "http://localhost:11434",
    "temperature": 0.7,
    "max_tokens": 2048
  }
}
```

#### Security Settings
```json
{
  "security": {
    "require_permissions": true,
    "session_timeout": 3600,
    "audit_log": true,
    "enable_encryption": true
  }
}
```

#### Tool Configuration
```json
{
  "tools": {
    "enabled_tools": [
      "file_manager",
      "window_manager",
      "spotify",
      "system_control"
    ],
    "require_confirmation": [
      "system_control",
      "package_manager"
    ]
  }
}
```

## Usage

### Command Line Interface

```bash
# Start interactive session
gnome-ai-assistant

# Single command
gnome-ai-assistant "What files are in my Downloads folder?"

# With specific tool
gnome-ai-assistant --tool file_manager "List files in ~/Documents"
```

### GNOME Shell Extension

Click the AI Assistant icon in the top panel to:
- Open chat interface
- View active permissions
- Check service status
- Access settings

### API Endpoints

- `POST /chat` - Main chat interface
- `POST /execute_tool` - Direct tool execution
- `GET /status` - Service status
- `GET /tools` - Available tools
- `POST /permissions` - Permission management

### Available Tools

### File Manager
- List directory contents
- Read/write files
- File operations (copy, move, delete)
- Search files

### Window Manager
- List open windows
- Focus/close windows
- Window positioning
- Application launching

### System Control
- Service management
- Process control
- System information
- Resource monitoring

### Spotify Integration
- Playback control
- Playlist management
- Track information
- Volume control

### Package Manager
- Package installation/removal
- System updates
- Package information
- Dependency management

### Web Browser Control
- Open URLs
- Navigate web pages
- Manage bookmarks
- Browser automation

### Network Management
- Network diagnostics
- WiFi management
- Connection monitoring
- Speed testing

## Security Features

### Permission System
- **Deny by Default**: All operations require explicit permission
- **Risk Levels**: Operations categorized by risk (low, medium, high, critical)
- **Permission Scopes**: One-time, session-based, or permanent permissions
- **Audit Trail**: Complete logging of all permission requests and grants

### Input Validation
- All user inputs sanitized
- Path traversal protection
- File access restrictions
- Command injection prevention

## Development

### Project Structure
```
GNOME_extension/
├── src/
│   ├── gnome_ai_assistant/     # Python service
│   └── extension/              # GNOME Shell extension
├── config/                     # Configuration files
├── scripts/                    # Installation scripts
├── tests/                      # Test suites
├── docs/                       # Documentation
└── requirements.txt            # Python dependencies
```

### Adding New Tools

1. Create tool class inheriting from `BaseTool`:
```python
from gnome_ai_assistant.tools.base import BaseTool, ToolResponse

class MyTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.name = "my_tool"
        self.description = "Description of my tool"
        self.required_permissions = ["my_capability"]
    
    async def execute(self, **kwargs) -> ToolResponse:
        # Implementation
        return ToolResponse(success=True, result="Done")
```

2. Register in tool registry:
```python
from gnome_ai_assistant.tools.base import get_tool_registry

registry = get_tool_registry()
registry.register_tool(MyTool())
```

### Testing

```bash
# Install test dependencies
pip install -r requirements.txt

# Run unit tests
python -m pytest tests/unit/ -v

# Run integration tests
python -m pytest tests/integration/ -v

# Run specific test
python -m pytest tests/unit/test_permissions.py -v

# Run all tests with coverage
python -m pytest tests/ --cov=src/gnome_ai_assistant
```

## Troubleshooting

### Service Won't Start
```bash
# Check service status
systemctl --user status gnome-ai-assistant

# View logs
journalctl --user -u gnome-ai-assistant -f

# Restart service
systemctl --user restart gnome-ai-assistant
```

### Extension Not Loading
```bash
# Check GNOME Shell logs
journalctl /usr/bin/gnome-shell -f

# Reload extension
gnome-extensions disable gnome-ai-assistant@example.com
gnome-extensions enable gnome-ai-assistant@example.com
```

### Permission Issues
```bash
# Reset permissions database
rm ~/.local/share/gnome-ai-assistant/assistant.db

# Check socket permissions
ls -la /tmp/gnome-ai-assistant.sock
```

### LLM Connection Issues
```bash
# Test Ollama connection
curl http://localhost:11434/api/tags

# Check configuration
cat ~/.config/gnome-ai-assistant/settings.json

# Test OpenAI connection (if using OpenAI)
python -c "from openai import OpenAI; print('OpenAI client works')"

# Test Anthropic connection (if using Anthropic)
python -c "from anthropic import Anthropic; print('Anthropic client works')"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request

### Code Style
- Python: Follow PEP 8, use Black formatter
- JavaScript: Use ESLint configuration
- Type hints required for all Python functions
- Comprehensive docstrings for all classes and methods

## License

MIT License - see LICENSE file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/Aditya-4987/GNOME_extension/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Aditya-4987/GNOME_extension/discussions)
- **Documentation**: [Project Wiki](https://github.com/Aditya-4987/GNOME_extension/wiki)

## Roadmap

- [x] Core service architecture
- [x] LLM integration (OpenAI, Anthropic, Ollama)
- [x] Tool system with permissions
- [x] GNOME Shell extension
- [x] Web browser control
- [x] Network management tools
- [ ] Voice interface improvements
- [ ] Additional LLM providers (Claude, Gemini)
- [ ] Mobile companion app
- [ ] Plugin marketplace
- [ ] Multi-user support
- [ ] Cloud synchronization
