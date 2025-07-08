#!/bin/bash
# GNOME AI Assistant - Automated Uninstall Script
# This script completely removes the GNOME AI Assistant from your system

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Banner
echo ""
echo "🗑️  GNOME AI Assistant Uninstall Script"
echo "======================================"
echo ""

# Warning prompt
print_warning "This will completely remove GNOME AI Assistant and ALL its data!"
print_warning "This includes:"
echo "  - Service and configuration files"
echo "  - GNOME Shell extension"
echo "  - User data and conversation history"
echo "  - Permissions database"
echo "  - All logs and cached data"
echo ""

read -p "Are you sure you want to continue? (y/N): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    print_status "Uninstall cancelled."
    exit 0
fi

echo ""
print_status "Starting uninstall process..."

# 1. Stop and disable the service
print_status "Stopping and disabling systemd service..."
if systemctl --user is-active --quiet gnome-ai-assistant 2>/dev/null; then
    systemctl --user stop gnome-ai-assistant
    print_success "Service stopped"
else
    print_warning "Service was not running"
fi

if systemctl --user is-enabled --quiet gnome-ai-assistant 2>/dev/null; then
    systemctl --user disable gnome-ai-assistant
    print_success "Service disabled"
else
    print_warning "Service was not enabled"
fi

# 2. Disable GNOME Shell extension
print_status "Disabling GNOME Shell extension..."
if command_exists gnome-extensions; then
    if gnome-extensions list | grep -q "gnome-ai-assistant@example.com"; then
        gnome-extensions disable gnome-ai-assistant@example.com 2>/dev/null || true
        print_success "Extension disabled"
    else
        print_warning "Extension was not installed or already disabled"
    fi
else
    print_warning "gnome-extensions command not found, skipping extension disable"
fi

# 3. Remove systemd service files
print_status "Removing systemd service files..."
files_removed=0

if [ -f ~/.config/systemd/user/gnome-ai-assistant.service ]; then
    rm -f ~/.config/systemd/user/gnome-ai-assistant.service
    ((files_removed++))
fi

if [ -f /etc/systemd/system/gnome-ai-assistant.service ]; then
    sudo rm -f /etc/systemd/system/gnome-ai-assistant.service 2>/dev/null || true
    ((files_removed++))
fi

if [ -f /usr/lib/systemd/user/gnome-ai-assistant.service ]; then
    sudo rm -f /usr/lib/systemd/user/gnome-ai-assistant.service 2>/dev/null || true
    ((files_removed++))
fi

if [ $files_removed -gt 0 ]; then
    print_success "Removed $files_removed systemd service file(s)"
    systemctl --user daemon-reload 2>/dev/null || true
    sudo systemctl daemon-reload 2>/dev/null || true
else
    print_warning "No systemd service files found"
fi

# 4. Remove configuration files
print_status "Removing configuration files..."
if [ -d ~/.config/gnome-ai-assistant ]; then
    rm -rf ~/.config/gnome-ai-assistant/
    print_success "Removed user configuration directory"
else
    print_warning "User configuration directory not found"
fi

if [ -d /etc/gnome-ai-assistant ]; then
    sudo rm -rf /etc/gnome-ai-assistant/ 2>/dev/null || true
    print_success "Removed system configuration directory"
fi

# 5. Remove data and database files
print_status "Removing data and database files..."
dirs_removed=0

if [ -d ~/.local/share/gnome-ai-assistant ]; then
    rm -rf ~/.local/share/gnome-ai-assistant/
    ((dirs_removed++))
fi

if [ -d ~/.cache/gnome-ai-assistant ]; then
    rm -rf ~/.cache/gnome-ai-assistant/
    ((dirs_removed++))
fi

if [ $dirs_removed -gt 0 ]; then
    print_success "Removed $dirs_removed data directory(ies)"
else
    print_warning "No data directories found"
fi

# 6. Remove extension files
print_status "Removing GNOME Shell extension files..."
if [ -d ~/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com ]; then
    rm -rf ~/.local/share/gnome-shell/extensions/gnome-ai-assistant@example.com/
    print_success "Removed extension directory"
else
    print_warning "Extension directory not found"
fi

# 7. Remove application files
print_status "Removing application files..."
app_files_removed=0

# User installation
if [ -f ~/.local/bin/gnome-ai-assistant ]; then
    rm -f ~/.local/bin/gnome-ai-assistant
    ((app_files_removed++))
fi

if [ -d ~/.local/lib/gnome-ai-assistant ]; then
    rm -rf ~/.local/lib/gnome-ai-assistant/
    ((app_files_removed++))
fi

# System-wide installation
if [ -f /usr/local/bin/gnome-ai-assistant ]; then
    sudo rm -f /usr/local/bin/gnome-ai-assistant 2>/dev/null || true
    ((app_files_removed++))
fi

if [ -d /usr/local/lib/gnome-ai-assistant ]; then
    sudo rm -rf /usr/local/lib/gnome-ai-assistant/ 2>/dev/null || true
    ((app_files_removed++))
fi

if [ -d /opt/gnome-ai-assistant ]; then
    sudo rm -rf /opt/gnome-ai-assistant/ 2>/dev/null || true
    ((app_files_removed++))
fi

if [ $app_files_removed -gt 0 ]; then
    print_success "Removed $app_files_removed application file(s)/directory(ies)"
else
    print_warning "No application files found"
fi

# 8. Remove desktop entry
print_status "Removing desktop entry..."
desktop_files_removed=0

if [ -f ~/.local/share/applications/gnome-ai-assistant.desktop ]; then
    rm -f ~/.local/share/applications/gnome-ai-assistant.desktop
    ((desktop_files_removed++))
fi

if [ -f /usr/share/applications/gnome-ai-assistant.desktop ]; then
    sudo rm -f /usr/share/applications/gnome-ai-assistant.desktop 2>/dev/null || true
    ((desktop_files_removed++))
fi

if [ $desktop_files_removed -gt 0 ]; then
    print_success "Removed $desktop_files_removed desktop entry file(s)"
else
    print_warning "No desktop entry files found"
fi

# 9. Remove temporary files and sockets
print_status "Removing temporary files and sockets..."
temp_files_removed=0

for socket_file in /tmp/gnome-ai-assistant*.sock; do
    if [ -e "$socket_file" ]; then
        rm -f "$socket_file"
        ((temp_files_removed++))
    fi
done

if [ $temp_files_removed -gt 0 ]; then
    print_success "Removed $temp_files_removed temporary file(s)"
else
    print_warning "No temporary files found"
fi

# 10. Clean up logs
print_status "Cleaning up logs..."
if command_exists journalctl; then
    # Clear user service logs
    journalctl --user --vacuum-time=1s --user-unit=gnome-ai-assistant >/dev/null 2>&1 || true
    print_success "Cleaned systemd logs"
fi

# Remove application log files
if [ -d /var/log/gnome-ai-assistant ]; then
    sudo rm -rf /var/log/gnome-ai-assistant/ 2>/dev/null || true
    print_success "Removed application log directory"
fi

# 11. Final verification
print_status "Performing final verification..."

# Check for remaining processes
if pgrep -f gnome-ai-assistant >/dev/null 2>&1; then
    print_warning "Some processes are still running. Attempting to terminate..."
    pkill -f gnome-ai-assistant 2>/dev/null || true
    sleep 2
    if pgrep -f gnome-ai-assistant >/dev/null 2>&1; then
        print_warning "Some processes could not be terminated. You may need to restart your system."
    else
        print_success "All processes terminated"
    fi
else
    print_success "No running processes found"
fi

# Check for remaining files
remaining_files=$(find / -name "*gnome-ai-assistant*" 2>/dev/null | grep -v "/proc\|/sys\|/dev" | head -10)
if [ -n "$remaining_files" ]; then
    print_warning "Some files may still remain:"
    echo "$remaining_files"
    echo "You may want to remove these manually if needed."
else
    print_success "No obvious remaining files found"
fi

# Final success message
echo ""
print_success "✅ GNOME AI Assistant has been successfully uninstalled!"
echo ""
print_status "📋 What was removed:"
echo "  ✓ Systemd service and configuration"
echo "  ✓ GNOME Shell extension"
echo "  ✓ User data and configuration files"
echo "  ✓ Application files and desktop entries"
echo "  ✓ Temporary files and sockets"
echo "  ✓ Log files"
echo ""
print_warning "⚠️  Post-uninstall steps:"
echo "  1. Restart GNOME Shell: Press Alt+F2, type 'r', press Enter"
echo "  2. Or log out and log back in"
echo "  3. The project directory was NOT removed (if you cloned the repo)"
echo "  4. Python packages were NOT removed (they may be used by other apps)"
echo ""
print_status "ℹ️  To remove Python packages manually, see UNINSTALL.md"
print_status "ℹ️  For issues or questions: https://github.com/Aditya-4987/GNOME_extension/issues"
echo ""
