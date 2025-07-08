#!/bin/bash
# GNOME AI Assistant Extension Installation Script

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
EXTENSION_UUID="gnome-ai-assistant@example.com"
EXTENSION_DIR="$HOME/.local/share/gnome-shell/extensions/$EXTENSION_UUID"

# Function to check GNOME Shell version
check_gnome_version() {
    print_status "Checking GNOME Shell version..."
    
    if ! command -v gnome-shell &> /dev/null; then
        print_error "GNOME Shell is not installed"
        return 1
    fi
    
    GNOME_VERSION=$(gnome-shell --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
    GNOME_MAJOR=$(echo $GNOME_VERSION | cut -d. -f1)
    
    if [[ $GNOME_MAJOR -lt 45 ]]; then
        print_error "GNOME Shell version $GNOME_VERSION is not supported (minimum: 45.0)"
        return 1
    fi
    
    print_success "GNOME Shell version $GNOME_VERSION is supported"
    return 0
}

# Function to install extension
install_extension() {
    print_status "Installing GNOME AI Assistant extension..."
    
    # Remove existing extension if it exists
    if [[ -d "$EXTENSION_DIR" ]]; then
        print_warning "Removing existing extension..."
        rm -rf "$EXTENSION_DIR"
    fi
    
    # Create extension directory
    mkdir -p "$EXTENSION_DIR"
    
    # Copy extension files
    print_status "Copying extension files..."
    cp -r "$PROJECT_ROOT/src/extension/"* "$EXTENSION_DIR/"
    
    # Ensure proper permissions
    chmod +x "$EXTENSION_DIR"/*.js || true
    
    # Validate metadata
    if [[ ! -f "$EXTENSION_DIR/metadata.json" ]]; then
        print_error "Extension metadata.json not found"
        return 1
    fi
    
    # Check if extension files are valid
    if [[ ! -f "$EXTENSION_DIR/extension.js" ]]; then
        print_error "Extension main file not found"
        return 1
    fi
    
    print_success "Extension files installed to $EXTENSION_DIR"
    return 0
}

# Function to enable extension
enable_extension() {
    print_status "Enabling GNOME AI Assistant extension..."
    
    # Check if extension is already enabled
    if gnome-extensions list --enabled | grep -q "$EXTENSION_UUID"; then
        print_warning "Extension is already enabled"
        return 0
    fi
    
    # Enable the extension
    if gnome-extensions enable "$EXTENSION_UUID"; then
        print_success "Extension enabled successfully"
        return 0
    else
        print_error "Failed to enable extension"
        return 1
    fi
}

# Function to check extension status
check_extension_status() {
    print_status "Checking extension status..."
    
    # Check if extension is installed
    if [[ ! -d "$EXTENSION_DIR" ]]; then
        print_error "Extension is not installed"
        return 1
    fi
    
    # Check if extension is enabled
    if gnome-extensions list --enabled | grep -q "$EXTENSION_UUID"; then
        print_success "Extension is installed and enabled"
        
        # Check if extension is running
        if gnome-extensions info "$EXTENSION_UUID" | grep -q "State: ENABLED"; then
            print_success "Extension is running"
        else
            print_warning "Extension is enabled but not running"
        fi
    else
        print_warning "Extension is installed but not enabled"
    fi
    
    return 0
}

# Function to restart GNOME Shell (X11 only)
restart_gnome_shell() {
    print_status "Checking display server..."
    
    if [[ "$XDG_SESSION_TYPE" == "x11" ]]; then
        print_status "Restarting GNOME Shell..."
        
        # Kill and restart GNOME Shell
        if killall -SIGUSR1 gnome-shell; then
            print_success "GNOME Shell restarted"
        else
            print_warning "Could not restart GNOME Shell automatically"
            print_status "Please press Alt+F2, type 'r' and press Enter to restart GNOME Shell"
        fi
    else
        print_warning "Running on Wayland - manual logout/login may be required"
        print_status "Please log out and log back in to ensure the extension is loaded"
    fi
}

# Function to show usage instructions
show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --install     Install the extension"
    echo "  --enable      Enable the extension"
    echo "  --status      Check extension status"
    echo "  --restart     Restart GNOME Shell (X11 only)"
    echo "  --help        Show this help message"
    echo ""
    echo "If no options are provided, the script will:"
    echo "1. Check GNOME Shell version compatibility"
    echo "2. Install the extension"
    echo "3. Enable the extension"
    echo "4. Check extension status"
    echo "5. Restart GNOME Shell (if needed)"
}

# Main function
main() {
    local action="$1"
    
    case "$action" in
        --install)
            check_gnome_version && install_extension
            ;;
        --enable)
            enable_extension
            ;;
        --status)
            check_extension_status
            ;;
        --restart)
            restart_gnome_shell
            ;;
        --help)
            show_usage
            ;;
        "")
            # Default behavior - full installation
            print_status "Starting GNOME AI Assistant extension installation..."
            echo ""
            
            # Check prerequisites
            if ! check_gnome_version; then
                print_error "Prerequisites not met"
                exit 1
            fi
            
            # Install extension
            if ! install_extension; then
                print_error "Extension installation failed"
                exit 1
            fi
            
            # Enable extension
            if ! enable_extension; then
                print_error "Extension enabling failed"
                exit 1
            fi
            
            # Check status
            check_extension_status
            
            # Restart GNOME Shell if needed
            restart_gnome_shell
            
            echo ""
            print_success "GNOME AI Assistant extension installation completed!"
            print_status "The extension should now be available in your top panel"
            print_status "Make sure the AI Assistant service is running for full functionality"
            ;;
        *)
            print_error "Unknown option: $action"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
