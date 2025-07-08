# GNOME AI Assistant - Uninstall Guide

This guide provides step-by-step instructions to completely remove and clean up the GNOME AI Assistant from your system.

## ⚠️ Warning

This will permanently remove:
- The AI Assistant service and all its data
- GNOME Shell extension
- Configuration files and user data
- Permissions database
- Memory and conversation history
- All logs and cached data

**Please backup any important data before proceeding.**

## Quick Uninstall

For a quick removal, you can use the automated uninstall script:

```bash
chmod +x scripts/uninstall.sh
./scripts/uninstall.sh
```

## Manual Uninstall Steps

Follow these steps if you prefer manual removal or if the automated script doesn't work:

### 1. Stop and Disable the Service

```bash
# Stop the running service
systemctl --user stop gnome-ai-assistant

# Disable auto-start
systemctl --user disable gnome-ai-assistant

# Check service status (should show inactive/dead)
systemctl --user status gnome-ai-assistant
```

### 2. Remove GNOME Shell Extension

```bash
# Disable the extension
gnome-extensions disable gnome-ai-assistant@example.com

# Remove extension files
rm -rf ~/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com/

# Restart GNOME Shell (Alt+F2, type 'r', press Enter)
# Or log out and log back in
```

### 3. Remove Systemd Service Files

```bash
# Remove user service file
rm -f ~/.config/systemd/user/gnome-ai-assistant.service

# Remove any system-wide service files (if installed)
sudo rm -f /etc/systemd/system/gnome-ai-assistant.service
sudo rm -f /usr/lib/systemd/user/gnome-ai-assistant.service

# Reload systemd daemon
systemctl --user daemon-reload
sudo systemctl daemon-reload
```

### 4. Remove Configuration Files

```bash
# Remove configuration directory
rm -rf ~/.config/gnome-ai-assistant/

# Remove any system-wide configuration
sudo rm -rf /etc/gnome-ai-assistant/
```

### 5. Remove Data and Database Files

```bash
# Remove user data directory
rm -rf ~/.local/share/gnome-ai-assistant/

# Remove any cache files
rm -rf ~/.cache/gnome-ai-assistant/

# Remove temporary files and sockets
rm -f /tmp/gnome-ai-assistant.sock
rm -f /tmp/gnome-ai-assistant-*.sock
```

### 6. Remove Application Files

```bash
# If installed in user directory
rm -rf ~/.local/bin/gnome-ai-assistant
rm -rf ~/.local/lib/gnome-ai-assistant/

# If installed system-wide (requires sudo)
sudo rm -rf /usr/local/bin/gnome-ai-assistant
sudo rm -rf /usr/local/lib/gnome-ai-assistant/
sudo rm -rf /opt/gnome-ai-assistant/

# Remove desktop entry
rm -f ~/.local/share/applications/gnome-ai-assistant.desktop
sudo rm -f /usr/share/applications/gnome-ai-assistant.desktop
```

### 7. Remove Python Virtual Environment (if created)

```bash
# If you created a virtual environment for the project
rm -rf ~/.local/share/gnome-ai-assistant-venv/
# or wherever you created the virtual environment
```

### 8. Remove Project Directory

```bash
# Remove the cloned repository (adjust path as needed)
rm -rf ~/GNOME_extension/
# or wherever you cloned the repository
```

### 9. Clean Up System Logs

```bash
# Clear systemd logs for the service
sudo journalctl --vacuum-time=1d --user-unit=gnome-ai-assistant
journalctl --user --vacuum-time=1d --user-unit=gnome-ai-assistant

# Remove any application-specific log files
sudo rm -rf /var/log/gnome-ai-assistant/
rm -rf ~/.local/share/gnome-ai-assistant/logs/
```

### 10. Remove Python Dependencies (Optional)

If you want to remove Python packages that were installed specifically for this project:

```bash
# Uninstall main dependencies
pip uninstall -y fastapi uvicorn aiofiles anthropic ollama openai
pip uninstall -y chromadb numpy pydantic sqlalchemy structlog
pip uninstall -y websockets aiohttp httpx cryptography psutil
pip uninstall -y pytesseract pillow netifaces ping3 distro

# Remove all packages from requirements.txt
pip uninstall -r requirements.txt -y
```

**Note**: Only do this if these packages are not used by other applications.

## Verification Steps

After completing the uninstall, verify that everything has been removed:

### 1. Check Service Status
```bash
systemctl --user status gnome-ai-assistant
# Should show "Unit gnome-ai-assistant.service could not be found"
```

### 2. Check Extension Status
```bash
gnome-extensions list | grep gnome-ai-assistant
# Should return nothing
```

### 3. Check for Remaining Files
```bash
# Search for any remaining files
find ~/ -name "*gnome-ai-assistant*" 2>/dev/null
find /tmp -name "*gnome-ai-assistant*" 2>/dev/null

# Check if any processes are still running
ps aux | grep gnome-ai-assistant
```

### 4. Check Socket Files
```bash
# Verify no socket files remain
ls -la /tmp/gnome-ai-assistant*
# Should show "No such file or directory"
```

## Troubleshooting Uninstall Issues

### Extension Won't Disable
```bash
# Force disable the extension
gsettings set org.gnome.shell disabled-extensions "$(gsettings get org.gnome.shell disabled-extensions | sed "s/'gnome-ai-assistant@example.com', //g" | sed "s/, 'gnome-ai-assistant@example.com'//g" | sed "s/'gnome-ai-assistant@example.com'//g")"

# Restart GNOME Shell
killall -HUP gnome-shell
```

### Service Won't Stop
```bash
# Force kill the service
pkill -f gnome-ai-assistant

# Remove any stuck socket files
sudo rm -f /tmp/gnome-ai-assistant*.sock
```

### Permission Denied Errors
```bash
# If you encounter permission errors, try with sudo
sudo systemctl stop gnome-ai-assistant
sudo systemctl disable gnome-ai-assistant

# For file removal
sudo rm -rf /path/to/stubborn/directory
```

### Files in Use
```bash
# Check what's using the files
lsof | grep gnome-ai-assistant

# Kill processes using the files
sudo fuser -k /path/to/file
```

## Automated Uninstall Script

Create and run this script for automated uninstall:

```bash
#!/bin/bash
# Save as scripts/uninstall.sh

echo "🗑️  GNOME AI Assistant Uninstall Script"
echo "======================================"

# Stop and disable service
echo "Stopping service..."
systemctl --user stop gnome-ai-assistant 2>/dev/null
systemctl --user disable gnome-ai-assistant 2>/dev/null

# Disable extension
echo "Disabling extension..."
gnome-extensions disable gnome-ai-assistant@example.com 2>/dev/null

# Remove files and directories
echo "Removing files..."
rm -rf ~/.config/gnome-ai-assistant/
rm -rf ~/.local/share/gnome-ai-assistant/
rm -rf ~/.cache/gnome-ai-assistant/
rm -rf ~/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com/
rm -f ~/.config/systemd/user/gnome-ai-assistant.service
rm -f ~/.local/share/applications/gnome-ai-assistant.desktop
rm -f /tmp/gnome-ai-assistant*.sock

# Reload systemd
systemctl --user daemon-reload

echo "✅ Uninstall completed!"
echo "⚠️  Please restart GNOME Shell (Alt+F2 -> 'r') or log out/in"
echo "ℹ️  Project directory and Python packages were not removed"
echo "   Remove them manually if desired"
```

## Post-Uninstall Cleanup

After uninstalling, you may want to:

1. **Restart GNOME Shell**: Press `Alt+F2`, type `r`, and press Enter
2. **Clear browser cache**: If you used the web interface
3. **Review logs**: Check system logs for any remaining references
4. **Clean package cache**: Run `pip cache purge` to clean pip cache

## Recovery

If you want to reinstall the GNOME AI Assistant later:

1. Re-clone the repository from GitHub
2. Follow the installation instructions in README.md
3. Your old configuration files have been removed, so you'll need to reconfigure

## Support

If you encounter issues during uninstall:

- **Check the logs**: `journalctl --user -u gnome-ai-assistant`
- **Report issues**: [GitHub Issues](https://github.com/Aditya-4987/GNOME_extension/issues)
- **Get help**: [GitHub Discussions](https://github.com/Aditya-4987/GNOME_extension/discussions)

---

**Note**: This guide assumes a standard installation. If you customized the installation paths or used different configuration options, adjust the paths accordingly.
