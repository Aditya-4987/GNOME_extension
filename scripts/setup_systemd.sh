#!/bin/bash

# GNOME AI Assistant Systemd Setup Script
# This script sets up the systemd user service for the AI assistant

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="gnome-ai-assistant"
VENV_DIR="$HOME/.local/share/gnome-ai-assistant/venv"
CONFIG_DIR="$HOME/.config/gnome-ai-assistant"

# Function to create systemd service file
create_service_file() {
    print_status "Creating systemd service file..."
    
    # Create systemd user directory
    mkdir -p "$HOME/.config/systemd/user"
    
    # Create service file
    cat > "$HOME/.config/systemd/user/${SERVICE_NAME}.service" << EOF
[Unit]
Description=GNOME AI Assistant Service
Documentation=https://github.com/gnome-ai-assistant/gnome-ai-assistant
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=exec
ExecStart=${VENV_DIR}/bin/python -m gnome_ai_assistant.main
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=5
TimeoutStopSec=10

# Environment
Environment=PATH=${VENV_DIR}/bin:\$PATH
Environment=PYTHONPATH=${PROJECT_ROOT}/src:\$PYTHONPATH
Environment=XDG_CONFIG_HOME=%h/.config
Environment=XDG_DATA_HOME=%h/.local/share

# Working directory
WorkingDirectory=${PROJECT_ROOT}

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=%h/.config/gnome-ai-assistant %h/.local/share/gnome-ai-assistant /tmp

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=gnome-ai-assistant

[Install]
WantedBy=default.target
EOF
    
    print_success "Service file created"
}

# Function to create service environment file
create_environment_file() {
    print_status "Creating environment file..."
    
    # Create environment file
    cat > "$HOME/.config/systemd/user/${SERVICE_NAME}.env" << EOF
# GNOME AI Assistant Environment Variables

# Service configuration
GNOME_AI_ASSISTANT_CONFIG_DIR=${CONFIG_DIR}
GNOME_AI_ASSISTANT_LOG_LEVEL=INFO
GNOME_AI_ASSISTANT_SOCKET_PATH=/tmp/gnome_ai_assistant.sock

# Python configuration
PYTHONPATH=${PROJECT_ROOT}/src
PYTHONUNBUFFERED=1

# Display configuration (for GUI applications)
DISPLAY=:0
WAYLAND_DISPLAY=wayland-0

# DBus session
DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus
EOF
    
    print_success "Environment file created"
}

# Function to reload and enable service
setup_service() {
    print_status "Setting up systemd service..."
    
    # Reload systemd daemon
    systemctl --user daemon-reload
    
    # Enable service
    systemctl --user enable "${SERVICE_NAME}.service"
    
    print_success "Service enabled"
}

# Function to start service
start_service() {
    print_status "Starting service..."
    
    # Start service
    systemctl --user start "${SERVICE_NAME}.service"
    
    # Check status
    if systemctl --user is-active --quiet "${SERVICE_NAME}.service"; then
        print_success "Service started successfully"
    else
        print_error "Failed to start service"
        print_status "Checking service status..."
        systemctl --user status "${SERVICE_NAME}.service" --no-pager
        return 1
    fi
}

# Function to check service status
check_service_status() {
    print_status "Checking service status..."
    
    if systemctl --user is-enabled --quiet "${SERVICE_NAME}.service"; then
        print_success "Service is enabled"
    else
        print_warning "Service is not enabled"
    fi
    
    if systemctl --user is-active --quiet "${SERVICE_NAME}.service"; then
        print_success "Service is running"
    else
        print_warning "Service is not running"
    fi
    
    # Show detailed status
    echo
    systemctl --user status "${SERVICE_NAME}.service" --no-pager
}

# Function to show service logs
show_logs() {
    print_status "Recent service logs:"
    echo
    journalctl --user -u "${SERVICE_NAME}.service" -n 20 --no-pager
}

# Function to create timer for auto-restart
create_restart_timer() {
    print_status "Creating restart timer..."
    
    # Create timer file
    cat > "$HOME/.config/systemd/user/${SERVICE_NAME}-restart.timer" << EOF
[Unit]
Description=Restart GNOME AI Assistant periodically
Requires=${SERVICE_NAME}.service

[Timer]
OnBootSec=1min
OnUnitActiveSec=1h
Persistent=true

[Install]
WantedBy=timers.target
EOF
    
    # Create restart service
    cat > "$HOME/.config/systemd/user/${SERVICE_NAME}-restart.service" << EOF
[Unit]
Description=Restart GNOME AI Assistant
After=${SERVICE_NAME}.service

[Service]
Type=oneshot
ExecStart=/bin/systemctl --user restart ${SERVICE_NAME}.service
EOF
    
    # Reload and enable timer
    systemctl --user daemon-reload
    systemctl --user enable "${SERVICE_NAME}-restart.timer"
    
    print_success "Restart timer created"
}

# Function to remove service
remove_service() {
    print_status "Removing systemd service..."
    
    # Stop and disable service
    systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}.service" 2>/dev/null || true
    
    # Stop and disable timer
    systemctl --user stop "${SERVICE_NAME}-restart.timer" 2>/dev/null || true
    systemctl --user disable "${SERVICE_NAME}-restart.timer" 2>/dev/null || true
    
    # Remove files
    rm -f "$HOME/.config/systemd/user/${SERVICE_NAME}.service"
    rm -f "$HOME/.config/systemd/user/${SERVICE_NAME}.env"
    rm -f "$HOME/.config/systemd/user/${SERVICE_NAME}-restart.timer"
    rm -f "$HOME/.config/systemd/user/${SERVICE_NAME}-restart.service"
    
    # Reload daemon
    systemctl --user daemon-reload
    
    print_success "Service removed"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [command]"
    echo
    echo "Commands:"
    echo "  install     Install and setup the systemd service"
    echo "  start       Start the service"
    echo "  stop        Stop the service"
    echo "  restart     Restart the service"
    echo "  status      Show service status"
    echo "  logs        Show service logs"
    echo "  enable      Enable service to start on boot"
    echo "  disable     Disable service auto-start"
    echo "  remove      Remove the service completely"
    echo "  timer       Setup auto-restart timer"
    echo
}

# Main function
main() {
    case "${1:-install}" in
        install)
            create_service_file
            create_environment_file
            setup_service
            start_service
            check_service_status
            ;;
        start)
            systemctl --user start "${SERVICE_NAME}.service"
            print_success "Service started"
            ;;
        stop)
            systemctl --user stop "${SERVICE_NAME}.service"
            print_success "Service stopped"
            ;;
        restart)
            systemctl --user restart "${SERVICE_NAME}.service"
            print_success "Service restarted"
            ;;
        status)
            check_service_status
            ;;
        logs)
            show_logs
            ;;
        enable)
            systemctl --user enable "${SERVICE_NAME}.service"
            print_success "Service enabled"
            ;;
        disable)
            systemctl --user disable "${SERVICE_NAME}.service"
            print_success "Service disabled"
            ;;
        remove)
            remove_service
            ;;
        timer)
            create_restart_timer
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $1"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
