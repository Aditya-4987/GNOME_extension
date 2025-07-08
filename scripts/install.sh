#!/bin/bash

# GNOME AI Assistant Installation Script
# This script installs the GNOME AI Assistant system including
# the Python service, GNOME Shell extension, and system dependencies.

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
PYTHON_VERSION="3.11"
VENV_DIR="$HOME/.local/share/gnome-ai-assistant/venv"
SERVICE_DIR="$HOME/.local/share/gnome-ai-assistant"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/gnome-ai-assistant@gnome.org"
CONFIG_DIR="$HOME/.config/gnome-ai-assistant"

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

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        PYTHON_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
            print_success "Python $PYTHON_VER found"
            return 0
        else
            print_error "Python 3.11+ required, found $PYTHON_VER"
            return 1
        fi
    else
        print_error "Python 3 not found"
        return 1
    fi
}

# Function to detect distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        echo "$ID"
    elif [ -f /etc/debian_version ]; then
        echo "debian"
    elif [ -f /etc/redhat-release ]; then
        echo "rhel"
    else
        echo "unknown"
    fi
}

# Function to install system dependencies
install_system_dependencies() {
    print_status "Installing system dependencies..."
    
    DISTRO=$(detect_distro)
    
    case "$DISTRO" in
        "ubuntu"|"debian")
            sudo apt update
            sudo apt install -y \
                python3 \
                python3-pip \
                python3-venv \
                python3-dev \
                build-essential \
                pkg-config \
                libdbus-1-dev \
                libgirepository1.0-dev \
                gir1.2-gtk-4.0 \
                gir1.2-adw-1 \
                dbus-x11 \
                xclip \
                wmctrl \
                tesseract-ocr \
                gnome-shell-extensions \
                gnome-screenshot \
                zenity \
                curl \
                git
            ;;
        "fedora")
            sudo dnf install -y \
                python3 \
                python3-pip \
                python3-devel \
                gcc \
                pkg-config \
                dbus-devel \
                gobject-introspection-devel \
                gtk4-devel \
                libadwaita-devel \
                dbus-x11 \
                xclip \
                wmctrl \
                tesseract \
                gnome-shell-extensions \
                gnome-screenshot \
                zenity \
                curl \
                git
            ;;
        "arch"|"manjaro")
            sudo pacman -S --needed \
                python \
                python-pip \
                base-devel \
                pkg-config \
                dbus \
                gobject-introspection \
                gtk4 \
                libadwaita \
                xorg-xprop \
                xclip \
                wmctrl \
                tesseract \
                gnome-shell-extensions \
                gnome-screenshot \
                zenity \
                curl \
                git
            ;;
        *)
            print_warning "Unknown distribution: $DISTRO"
            print_warning "Please install the following packages manually:"
            print_warning "- Python 3.11+"
            print_warning "- pip, venv, dev tools"
            print_warning "- DBus development libraries"
            print_warning "- GTK4, GObject Introspection"
            print_warning "- xclip, wmctrl, tesseract"
            print_warning "- GNOME Shell extensions support"
            ;;
    esac
    
    print_success "System dependencies installed"
}

# Function to create virtual environment
create_virtual_environment() {
    print_status "Creating Python virtual environment..."
    
    # Create service directory
    mkdir -p "$(dirname "$VENV_DIR")"
    
    # Create virtual environment
    python3 -m venv "$VENV_DIR"
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Upgrade pip
    pip install --upgrade pip setuptools wheel
    
    print_success "Virtual environment created"
}

# Function to install Python dependencies
install_python_dependencies() {
    print_status "Installing Python dependencies..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Install core dependencies
    pip install \
        fastapi \
        uvicorn \
        aiofiles \
        aiohttp \
        websockets \
        pydantic \
        sqlalchemy \
        alembic \
        chromadb \
        numpy \
        PyGObject \
        dbus-python \
        psutil \
        click \
        jinja2 \
        python-multipart
    
    # Install optional LLM dependencies
    pip install \
        openai \
        anthropic \
        requests
    
    # Install development dependencies (optional)
    if [ "$1" = "--dev" ]; then
        pip install \
            pytest \
            pytest-asyncio \
            black \
            flake8 \
            mypy \
            coverage
    fi
    
    print_success "Python dependencies installed"
}

# Function to install the Python package
install_python_package() {
    print_status "Installing GNOME AI Assistant Python package..."
    
    # Activate virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Install package in development mode
    cd "$PROJECT_ROOT"
    pip install -e .
    
    print_success "Python package installed"
}

# Function to create configuration directory and files
create_configuration() {
    print_status "Creating configuration..."
    
    # Create config directory
    mkdir -p "$CONFIG_DIR"
    
    # Copy default configuration
    if [ -f "$PROJECT_ROOT/config/settings.json" ]; then
        cp "$PROJECT_ROOT/config/settings.json" "$CONFIG_DIR/settings.json"
    else
        # Create basic configuration
        cat > "$CONFIG_DIR/settings.json" << EOF
{
    "service": {
        "host": "localhost",
        "port": 8080,
        "socket_path": "/tmp/gnome_ai_assistant.sock",
        "log_level": "INFO",
        "max_conversations": 100
    },
    "llm": {
        "provider": "ollama",
        "model": "llama2",
        "api_base": "http://localhost:11434",
        "api_key": null,
        "temperature": 0.7,
        "max_tokens": 2048
    },
    "permissions": {
        "auto_grant_safe": true,
        "require_confirmation": true,
        "audit_log": true
    },
    "tools": {
        "enabled": [
            "file_manager",
            "window_manager",
            "spotify",
            "package_manager",
            "system_control"
        ]
    },
    "security": {
        "rate_limit": 100,
        "max_file_size": 104857600,
        "allowed_directories": [
            "\$HOME/Documents",
            "\$HOME/Downloads",
            "\$HOME/Desktop"
        ]
    }
}
EOF
    fi
    
    # Create logs directory
    mkdir -p "$CONFIG_DIR/logs"
    
    # Create data directory
    mkdir -p "$CONFIG_DIR/data"
    
    print_success "Configuration created"
}

# Function to install GNOME Shell extension
install_gnome_extension() {
    print_status "Installing GNOME Shell extension..."
    
    # Create extension directory
    mkdir -p "$EXTENSION_DIR"
    
    # Copy extension files
    cp -r "$PROJECT_ROOT/src/extension/"* "$EXTENSION_DIR/"
    
    # Set proper permissions
    chmod 644 "$EXTENSION_DIR"/*.js
    chmod 644 "$EXTENSION_DIR"/*.json
    
    print_success "GNOME Shell extension installed"
    print_warning "Please restart GNOME Shell (Alt+F2, type 'r', press Enter)"
    print_warning "Then enable the extension in GNOME Extensions app"
}

# Function to setup systemd user service
setup_systemd_service() {
    print_status "Setting up systemd user service..."
    
    # Create systemd user directory
    mkdir -p "$HOME/.config/systemd/user"
    
    # Create service file
    cat > "$HOME/.config/systemd/user/gnome-ai-assistant.service" << EOF
[Unit]
Description=GNOME AI Assistant Service
After=graphical-session.target

[Service]
Type=exec
ExecStart=$VENV_DIR/bin/python -m gnome_ai_assistant.main
Restart=always
RestartSec=5
Environment=PATH=$VENV_DIR/bin:\$PATH
Environment=PYTHONPATH=$PROJECT_ROOT/src:\$PYTHONPATH
WorkingDirectory=$PROJECT_ROOT

[Install]
WantedBy=default.target
EOF
    
    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable gnome-ai-assistant.service
    
    print_success "Systemd service configured"
}

# Function to check GNOME Shell version
check_gnome_shell() {
    if command_exists gnome-shell; then
        GNOME_VERSION=$(gnome-shell --version | grep -oP '\d+\.\d+' | head -1)
        print_status "GNOME Shell version: $GNOME_VERSION"
        
        # Check if version is supported (42+)
        if python3 -c "import sys; sys.exit(0 if float('$GNOME_VERSION') >= 42 else 1)"; then
            print_success "GNOME Shell version is supported"
        else
            print_warning "GNOME Shell 42+ is recommended, found $GNOME_VERSION"
        fi
    else
        print_error "GNOME Shell not found"
        return 1
    fi
}

# Function to start services
start_services() {
    print_status "Starting services..."
    
    # Start systemd service
    systemctl --user start gnome-ai-assistant.service
    
    # Check if service is running
    if systemctl --user is-active --quiet gnome-ai-assistant.service; then
        print_success "Service started successfully"
    else
        print_error "Failed to start service"
        return 1
    fi
}

# Function to run post-installation checks
post_install_checks() {
    print_status "Running post-installation checks..."
    
    # Check if service is running
    if systemctl --user is-active --quiet gnome-ai-assistant.service; then
        print_success "Service is running"
    else
        print_warning "Service is not running"
    fi
    
    # Check if socket exists
    if [ -S "/tmp/gnome_ai_assistant.sock" ]; then
        print_success "Unix socket created"
    else
        print_warning "Unix socket not found"
    fi
    
    # Check extension directory
    if [ -d "$EXTENSION_DIR" ]; then
        print_success "Extension installed"
    else
        print_warning "Extension not found"
    fi
    
    # Test CLI
    if "$VENV_DIR/bin/python" -m gnome_ai_assistant.interfaces.cli status > /dev/null 2>&1; then
        print_success "CLI interface working"
    else
        print_warning "CLI interface not working"
    fi
}

# Function to show installation summary
show_summary() {
    echo
    echo "================================================="
    echo "        GNOME AI Assistant Installation"
    echo "================================================="
    echo
    print_success "Installation completed!"
    echo
    echo "Service directory: $SERVICE_DIR"
    echo "Extension directory: $EXTENSION_DIR"
    echo "Configuration: $CONFIG_DIR"
    echo
    echo "Next steps:"
    echo "1. Restart GNOME Shell (Alt+F2 → type 'r' → Enter)"
    echo "2. Enable the extension in GNOME Extensions app"
    echo "3. Configure LLM settings in $CONFIG_DIR/settings.json"
    echo "4. Test with: $VENV_DIR/bin/python -m gnome_ai_assistant.interfaces.cli"
    echo
    echo "Service management:"
    echo "- Start:   systemctl --user start gnome-ai-assistant.service"
    echo "- Stop:    systemctl --user stop gnome-ai-assistant.service"
    echo "- Status:  systemctl --user status gnome-ai-assistant.service"
    echo "- Logs:    journalctl --user -u gnome-ai-assistant.service -f"
    echo
}

# Main installation function
main() {
    echo "================================================="
    echo "    GNOME AI Assistant Installation Script"
    echo "================================================="
    echo
    
    # Parse command line arguments
    DEV_MODE=false
    SKIP_DEPS=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dev)
                DEV_MODE=true
                shift
                ;;
            --skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --help|-h)
                echo "Usage: $0 [options]"
                echo
                echo "Options:"
                echo "  --dev         Install development dependencies"
                echo "  --skip-deps   Skip system dependency installation"
                echo "  --help, -h    Show this help message"
                echo
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Pre-installation checks
    print_status "Performing pre-installation checks..."
    
    if ! check_python_version; then
        exit 1
    fi
    
    if ! check_gnome_shell; then
        exit 1
    fi
    
    # Installation steps
    if [ "$SKIP_DEPS" = false ]; then
        install_system_dependencies
    fi
    
    create_virtual_environment
    
    if [ "$DEV_MODE" = true ]; then
        install_python_dependencies --dev
    else
        install_python_dependencies
    fi
    
    install_python_package
    create_configuration
    install_gnome_extension
    setup_systemd_service
    start_services
    
    # Post-installation
    sleep 2  # Give services time to start
    post_install_checks
    show_summary
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
