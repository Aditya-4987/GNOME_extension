# GNOME AI Assistant - Production Deployment Guide

## Overview

The GNOME AI Assistant is a production-ready AI-powered personal assistant integrated with the GNOME desktop environment. This guide covers deployment, configuration, and maintenance procedures for production use.

## System Requirements

### Hardware Requirements
- **CPU**: Intel/AMD x86_64 processor (2+ cores recommended)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 2GB free space minimum
- **Network**: Internet connection for LLM providers

### Software Requirements
- **OS**: Arch Linux (primary), Ubuntu 22.04+ (supported)
- **Desktop**: GNOME 45+ (required)
- **Python**: 3.11+ (required)
- **Node.js**: 18+ (for extension development)

## Installation

### 1. Automated Installation

```bash
# Clone the repository
git clone https://github.com/your-org/gnome-ai-assistant.git
cd gnome-ai-assistant

# Run the installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

### 2. Manual Installation

#### Step 1: Install System Dependencies

**Arch Linux:**
```bash
sudo pacman -S --needed python python-pip python-virtualenv \
    dbus glib2 gtk4 libadwaita webkit2gtk-4.1 \
    tesseract tesseract-data-eng speech-dispatcher \
    libnotify nodejs npm git
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv \
    dbus libglib2.0-dev libgtk-4-dev libadwaita-1-dev \
    libwebkit2gtk-4.1-dev tesseract-ocr tesseract-ocr-eng \
    speech-dispatcher libnotify-bin nodejs npm git
```

#### Step 2: Create Virtual Environment

```bash
# Create installation directory
mkdir -p ~/.local/share/gnome-ai-assistant
cd ~/.local/share/gnome-ai-assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

#### Step 3: Configure Service

```bash
# Copy configuration files
cp config/settings.json ~/.config/gnome-ai-assistant/
cp config/tools_config.json ~/.config/gnome-ai-assistant/

# Edit configuration
nano ~/.config/gnome-ai-assistant/settings.json
```

#### Step 4: Install Systemd Service

```bash
# Copy and configure systemd service
envsubst < config/systemd/gnome-ai-assistant.service > \
    ~/.config/systemd/user/gnome-ai-assistant.service

# Enable and start service
systemctl --user daemon-reload
systemctl --user enable gnome-ai-assistant.service
systemctl --user start gnome-ai-assistant.service
```

#### Step 5: Install GNOME Extension

```bash
# Install extension
./scripts/install_extension.sh

# Enable extension
gnome-extensions enable gnome-ai-assistant@example.com
```

## Configuration

### 1. LLM Provider Configuration

#### Ollama (Local)
```json
{
  "llm": {
    "provider": "ollama",
    "model": "llama2",
    "base_url": "http://localhost:11434",
    "max_tokens": 2048,
    "temperature": 0.7
  }
}
```

#### OpenAI
```json
{
  "llm": {
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "your-api-key-here",
    "max_tokens": 2048,
    "temperature": 0.7
  }
}
```

#### Anthropic Claude
```json
{
  "llm": {
    "provider": "anthropic",
    "model": "claude-3-sonnet-20240229",
    "api_key": "your-api-key-here",
    "max_tokens": 2048,
    "temperature": 0.7
  }
}
```

### 2. Security Configuration

```json
{
  "security": {
    "require_permissions": true,
    "default_permission_level": "deny",
    "session_timeout": 3600,
    "audit_log": true,
    "max_concurrent_requests": 10
  }
}
```

### 3. Database Configuration

```json
{
  "database": {
    "sqlite_path": "~/.local/share/gnome-ai-assistant/data/assistant.db",
    "chromadb_path": "~/.local/share/gnome-ai-assistant/data/chroma",
    "connection_pool_size": 10,
    "max_overflow": 20,
    "pool_timeout": 30
  }
}
```

### 4. Voice Configuration

```json
{
  "voice": {
    "enabled": true,
    "recognition_engine": "speech_recognition",
    "tts_engine": "piper",
    "wake_word": "hey assistant",
    "language": "en-US"
  }
}
```

## Service Management

### Systemd Commands

```bash
# Start service
systemctl --user start gnome-ai-assistant.service

# Stop service
systemctl --user stop gnome-ai-assistant.service

# Restart service
systemctl --user restart gnome-ai-assistant.service

# Check status
systemctl --user status gnome-ai-assistant.service

# View logs
journalctl --user -u gnome-ai-assistant.service -f
```

### Extension Management

```bash
# List extensions
gnome-extensions list

# Enable extension
gnome-extensions enable gnome-ai-assistant@example.com

# Disable extension
gnome-extensions disable gnome-ai-assistant@example.com

# Check extension status
gnome-extensions info gnome-ai-assistant@example.com
```

## Monitoring and Logging

### Log Locations

- **Service logs**: `journalctl --user -u gnome-ai-assistant.service`
- **Application logs**: `~/.local/share/gnome-ai-assistant/logs/`
- **Extension logs**: `journalctl /usr/bin/gnome-shell`

### Health Checks

```bash
# Check service health
curl --unix-socket /tmp/gnome-ai-assistant.sock http://localhost/health

# Check service status
curl --unix-socket /tmp/gnome-ai-assistant.sock http://localhost/status

# List available tools
curl --unix-socket /tmp/gnome-ai-assistant.sock http://localhost/tools
```

### Performance Monitoring

```bash
# Monitor resource usage
systemctl --user status gnome-ai-assistant.service

# Monitor memory usage
ps aux | grep gnome-ai-assistant

# Monitor network connections
netstat -tlpn | grep gnome-ai-assistant
```

## Backup and Recovery

### Backup Data

```bash
# Create backup directory
mkdir -p ~/backups/gnome-ai-assistant/$(date +%Y%m%d)

# Backup database
cp ~/.local/share/gnome-ai-assistant/data/assistant.db \
   ~/backups/gnome-ai-assistant/$(date +%Y%m%d)/

# Backup vector database
cp -r ~/.local/share/gnome-ai-assistant/data/chroma \
      ~/backups/gnome-ai-assistant/$(date +%Y%m%d)/

# Backup configuration
cp -r ~/.config/gnome-ai-assistant \
      ~/backups/gnome-ai-assistant/$(date +%Y%m%d)/
```

### Restore Data

```bash
# Stop service
systemctl --user stop gnome-ai-assistant.service

# Restore database
cp ~/backups/gnome-ai-assistant/YYYYMMDD/assistant.db \
   ~/.local/share/gnome-ai-assistant/data/

# Restore vector database
rm -rf ~/.local/share/gnome-ai-assistant/data/chroma
cp -r ~/backups/gnome-ai-assistant/YYYYMMDD/chroma \
      ~/.local/share/gnome-ai-assistant/data/

# Restore configuration
cp -r ~/backups/gnome-ai-assistant/YYYYMMDD/gnome-ai-assistant \
      ~/.config/

# Start service
systemctl --user start gnome-ai-assistant.service
```

## Security Considerations

### 1. API Key Management

- Store API keys in environment variables or secure files
- Use proper file permissions (600) for configuration files
- Rotate API keys regularly

### 2. Network Security

- Use Unix domain sockets for local communication
- Restrict network access to required services only
- Consider using VPN for remote LLM providers

### 3. Permission System

- Review and audit granted permissions regularly
- Use least-privilege principle for tool access
- Enable audit logging for security monitoring

### 4. Data Protection

- Encrypt sensitive data at rest
- Use secure communication channels
- Regular security updates

## Troubleshooting

### Common Issues

#### Service Won't Start

```bash
# Check logs
journalctl --user -u gnome-ai-assistant.service -n 50

# Check configuration
python -c "from gnome_ai_assistant.core.config import get_config; get_config()"

# Check dependencies
source ~/.local/share/gnome-ai-assistant/venv/bin/activate
pip check
```

#### Extension Not Loading

```bash
# Check extension installation
ls ~/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com/

# Check GNOME version compatibility
gnome-shell --version

# Restart GNOME Shell (X11 only)
Alt+F2 -> r -> Enter
```

#### Permission Denied Errors

```bash
# Check file permissions
ls -la ~/.local/share/gnome-ai-assistant/
ls -la ~/.config/gnome-ai-assistant/

# Fix permissions
chmod 755 ~/.local/share/gnome-ai-assistant/
chmod 600 ~/.config/gnome-ai-assistant/settings.json
```

#### Database Connection Issues

```bash
# Check database file
ls -la ~/.local/share/gnome-ai-assistant/data/assistant.db

# Recreate database
rm ~/.local/share/gnome-ai-assistant/data/assistant.db
systemctl --user restart gnome-ai-assistant.service
```

### Performance Issues

#### High CPU Usage

- Check for infinite loops in logs
- Reduce LLM request frequency
- Optimize database queries
- Consider using lighter LLM models

#### High Memory Usage

- Monitor vector database size
- Clean up old conversations
- Reduce context window size
- Restart service periodically

#### Slow Response Times

- Check network latency to LLM provider
- Optimize tool execution
- Use local LLM providers when possible
- Enable caching for frequent requests

## Updates and Maintenance

### Update Process

```bash
# Stop service
systemctl --user stop gnome-ai-assistant.service

# Backup current installation
cp -r ~/.local/share/gnome-ai-assistant \
      ~/.local/share/gnome-ai-assistant.backup.$(date +%Y%m%d)

# Update code
cd ~/gnome-ai-assistant
git pull origin main

# Update dependencies
source ~/.local/share/gnome-ai-assistant/venv/bin/activate
pip install -r requirements.txt --upgrade

# Update configuration if needed
# (Check release notes for breaking changes)

# Start service
systemctl --user start gnome-ai-assistant.service
```

### Maintenance Tasks

#### Daily
- Check service status
- Review error logs
- Monitor resource usage

#### Weekly
- Update LLM models
- Clean up old logs
- Review permissions audit

#### Monthly
- Backup data
- Update system dependencies
- Security audit
- Performance optimization

## Support and Resources

### Documentation
- [User Guide](docs/user-guide.md)
- [API Reference](docs/api-reference.md)
- [Extension Development](docs/extension-development.md)

### Community
- [GitHub Issues](https://github.com/your-org/gnome-ai-assistant/issues)
- [Discussion Forum](https://github.com/your-org/gnome-ai-assistant/discussions)
- [Matrix Chat](https://matrix.to/#/#gnome-ai-assistant:matrix.org)

### Commercial Support
- Enterprise support available
- Custom development services
- Training and consultation

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.
