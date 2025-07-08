"""Tools module initialization."""

# Import all tool classes for registry discovery
from .file_manager import FileManagerTool
from .window_manager import WindowManagerTool  
from .spotify import SpotifyTool
from .spotify_enhanced import SpotifyTool as SpotifyEnhancedTool
from .system_control import SystemControlTool
from .package_manager import PackageManagerTool
from .package_manager_enhanced import PackageManagerTool as PackageManagerEnhancedTool
from .web_browser import WebBrowserTool
from .network import NetworkTool

__all__ = [
    'FileManagerTool',
    'WindowManagerTool', 
    'SpotifyTool',
    'SpotifyEnhancedTool',
    'SystemControlTool',
    'PackageManagerTool',
    'PackageManagerEnhancedTool',
    'WebBrowserTool',
    'NetworkTool'
]