"""
Window manager tool for GNOME AI Assistant.

This module provides functionality to control windows and desktop environment
using AT-SPI (Assistive Technology Service Provider Interface) and other
GNOME-specific APIs.
"""

import asyncio
import logging
import subprocess
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
import time

try:
    import pyatspi
    ATSPI_AVAILABLE = True
except ImportError:
    ATSPI_AVAILABLE = False

from .base import BaseTool, ToolResponse, ToolParameter
from ..utils.logger import get_logger
from ..core.permissions import RiskLevel

logger = get_logger(__name__)


@dataclass
class WindowInfo:
    """Information about a window."""
    pid: int
    window_id: str
    title: str
    application: str
    workspace: int
    position: Tuple[int, int]
    size: Tuple[int, int]
    state: str  # maximized, minimized, normal, fullscreen
    focused: bool


@dataclass
class WorkspaceInfo:
    """Information about a workspace."""
    index: int
    name: str
    active: bool
    window_count: int


class WindowManagerTool(BaseTool):
    """Tool for window and workspace management."""
    
    def __init__(self):
        super().__init__(
            name="window_manager",
            description="Manage windows, workspaces, and desktop environment",
            parameters=[
                ToolParameter(
                    name="action",
                    description="Window management action",
                    type="string",
                    required=True,
                    enum=[
                        "list_windows", "get_active_window", "switch_window",
                        "close_window", "minimize_window", "maximize_window", 
                        "restore_window", "move_window", "resize_window",
                        "list_workspaces", "switch_workspace", "move_window_to_workspace",
                        "show_desktop", "open_application", "focus_application",
                        "get_screen_info", "take_screenshot", "set_wallpaper"
                    ]
                ),
                ToolParameter(
                    name="window_id",
                    description="Window ID or title to target",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="workspace_id",
                    description="Workspace index or name",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="application",
                    description="Application name to launch or focus",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="x",
                    description="X coordinate for window positioning",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="y", 
                    description="Y coordinate for window positioning",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="width",
                    description="Window width",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="height",
                    description="Window height", 
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="file_path",
                    description="File path for wallpaper or screenshot",
                    type="string",
                    required=False
                )
            ],
            required_permissions=["desktop_control", "application_launch"],
            risk_level=RiskLevel.MEDIUM
        )
    
    async def execute(self, action: str, window_id: str = None, 
                     application_name: str = None, window_title: str = None) -> ToolResponse:
        """Execute window management operation."""
        try:
            if not ATSPI_AVAILABLE:
                # Fallback to wmctrl if AT-SPI is not available
                return await self._execute_wmctrl(action, window_id, application_name, window_title)
            
            if action == "list":
                return await self._list_windows()
            elif action == "get_active":
                return await self._get_active_window()
            elif action == "focus":
                return await self._focus_window(window_id, application_name, window_title)
            elif action == "close":
                return await self._close_window(window_id, application_name, window_title)
            elif action == "minimize":
                return await self._minimize_window(window_id, application_name, window_title)
            elif action == "maximize":
                return await self._maximize_window(window_id, application_name, window_title)
            elif action == "restore":
                return await self._restore_window(window_id, application_name, window_title)
            elif action == "switch":
                return await self._switch_windows()
            else:
                return ToolResponse(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            logger.error(f"Window manager error: {e}")
            return ToolResponse(
                success=False,
                error=str(e)
            )
    
    async def _list_windows(self) -> ToolResponse:
        """List all available windows."""
        try:
            windows = []
            
            if ATSPI_AVAILABLE:
                desktop = pyatspi.Registry.getDesktop(0)
                
                for app in desktop:
                    try:
                        if app.name and app.name != "":
                            for window in app:
                                if window.getRole() == pyatspi.ROLE_FRAME or window.getRole() == pyatspi.ROLE_WINDOW:
                                    window_info = {
                                        "id": str(id(window)),
                                        "title": window.name or "Untitled",
                                        "application": app.name,
                                        "role": window.getRole().value_name,
                                        "states": [state.value_name for state in window.getState().getStates()]
                                    }
                                    windows.append(window_info)
                    except Exception as e:
                        logger.debug(f"Error accessing application {app.name}: {e}")
                        continue
            
            return ToolResponse(
                success=True,
                result={
                    "windows": windows,
                    "count": len(windows)
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to list windows: {e}"
            )
    
    async def _get_active_window(self) -> ToolResponse:
        """Get the currently active window."""
        try:
            if ATSPI_AVAILABLE:
                # Find focused window using AT-SPI
                desktop = pyatspi.Registry.getDesktop(0)
                
                for app in desktop:
                    try:
                        for window in app:
                            if window.getRole() in [pyatspi.ROLE_FRAME, pyatspi.ROLE_WINDOW]:
                                states = window.getState().getStates()
                                if pyatspi.STATE_ACTIVE in states:
                                    return ToolResponse(
                                        success=True,
                                        result={
                                            "id": str(id(window)),
                                            "title": window.name or "Untitled",
                                            "application": app.name,
                                            "active": True
                                        }
                                    )
                    except Exception:
                        continue
            
            return ToolResponse(
                success=False,
                error="No active window found"
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to get active window: {e}"
            )
    
    async def _focus_window(self, window_id: str = None, application_name: str = None, 
                           window_title: str = None) -> ToolResponse:
        """Focus a specific window."""
        try:
            window = await self._find_window(window_id, application_name, window_title)
            if not window:
                return ToolResponse(
                    success=False,
                    error="Window not found"
                )
            
            if ATSPI_AVAILABLE:
                # Use AT-SPI to focus window
                window.grabFocus()
                
                return ToolResponse(
                    success=True,
                    result={
                        "action": "focused",
                        "window": {
                            "id": str(id(window)),
                            "title": window.name,
                            "application": window.getApplication().name
                        }
                    }
                )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to focus window: {e}"
            )
    
    async def _close_window(self, window_id: str = None, application_name: str = None, 
                           window_title: str = None) -> ToolResponse:
        """Close a specific window."""
        try:
            window = await self._find_window(window_id, application_name, window_title)
            if not window:
                return ToolResponse(
                    success=False,
                    error="Window not found"
                )
            
            if ATSPI_AVAILABLE:
                # Try to find and click close button
                try:
                    for child in window:
                        if child.getRole() == pyatspi.ROLE_PUSH_BUTTON:
                            if "close" in (child.name or "").lower():
                                child.doAction(0)  # Usually the primary action
                                break
                    else:
                        # Fallback: try Alt+F4
                        await self._send_key_combination("Alt+F4")
                except Exception:
                    # Final fallback
                    await self._send_key_combination("Alt+F4")
                
                return ToolResponse(
                    success=True,
                    result={
                        "action": "closed",
                        "window": {
                            "title": window.name,
                            "application": window.getApplication().name
                        }
                    }
                )
            
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to close window: {e}"
            )
    
    async def _minimize_window(self, window_id: str = None, application_name: str = None, 
                              window_title: str = None) -> ToolResponse:
        """Minimize a specific window."""
        try:
            # For now, use keyboard shortcut as AT-SPI window state manipulation is complex
            window = await self._find_window(window_id, application_name, window_title)
            if not window:
                return ToolResponse(
                    success=False,
                    error="Window not found"
                )
            
            # Focus window first, then minimize
            if ATSPI_AVAILABLE:
                window.grabFocus()
                await asyncio.sleep(0.1)
                await self._send_key_combination("Alt+F9")  # GNOME minimize shortcut
            
            return ToolResponse(
                success=True,
                result={
                    "action": "minimized",
                    "window": {
                        "title": window.name,
                        "application": window.getApplication().name
                    }
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to minimize window: {e}"
            )
    
    async def _maximize_window(self, window_id: str = None, application_name: str = None, 
                              window_title: str = None) -> ToolResponse:
        """Maximize a specific window."""
        try:
            window = await self._find_window(window_id, application_name, window_title)
            if not window:
                return ToolResponse(
                    success=False,
                    error="Window not found"
                )
            
            # Focus window first, then maximize
            if ATSPI_AVAILABLE:
                window.grabFocus()
                await asyncio.sleep(0.1)
                await self._send_key_combination("Alt+F10")  # GNOME maximize shortcut
            
            return ToolResponse(
                success=True,
                result={
                    "action": "maximized",
                    "window": {
                        "title": window.name,
                        "application": window.getApplication().name
                    }
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to maximize window: {e}"
            )
    
    async def _restore_window(self, window_id: str = None, application_name: str = None, 
                             window_title: str = None) -> ToolResponse:
        """Restore a minimized/maximized window."""
        try:
            window = await self._find_window(window_id, application_name, window_title)
            if not window:
                return ToolResponse(
                    success=False,
                    error="Window not found"
                )
            
            # Focus window first, then restore
            if ATSPI_AVAILABLE:
                window.grabFocus()
                await asyncio.sleep(0.1)
                await self._send_key_combination("Alt+F5")  # GNOME restore shortcut
            
            return ToolResponse(
                success=True,
                result={
                    "action": "restored",
                    "window": {
                        "title": window.name,
                        "application": window.getApplication().name
                    }
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to restore window: {e}"
            )
    
    async def _switch_windows(self) -> ToolResponse:
        """Switch between windows (show window switcher)."""
        try:
            await self._send_key_combination("Alt+Tab")
            
            return ToolResponse(
                success=True,
                result={
                    "action": "window_switcher_opened"
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to switch windows: {e}"
            )
    
    async def _find_window(self, window_id: str = None, application_name: str = None, 
                          window_title: str = None):
        """Find a window by ID, application name, or title."""
        if not ATSPI_AVAILABLE:
            return None
        
        try:
            desktop = pyatspi.Registry.getDesktop(0)
            
            for app in desktop:
                try:
                    # Check application name match
                    if application_name and application_name.lower() not in (app.name or "").lower():
                        continue
                    
                    for window in app:
                        if window.getRole() not in [pyatspi.ROLE_FRAME, pyatspi.ROLE_WINDOW]:
                            continue
                        
                        # Check window ID match
                        if window_id and str(id(window)) != window_id:
                            continue
                        
                        # Check window title match
                        if window_title and window_title.lower() not in (window.name or "").lower():
                            continue
                        
                        return window
                except Exception:
                    continue
            
            return None
        
        except Exception as e:
            logger.error(f"Error finding window: {e}")
            return None
    
    async def _send_key_combination(self, keys: str) -> None:
        """Send keyboard shortcut."""
        try:
            # Use xdotool as fallback for key combinations
            await asyncio.create_subprocess_exec(
                "xdotool", "key", keys,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        except Exception as e:
            logger.debug(f"Failed to send key combination {keys}: {e}")
    
    async def _execute_wmctrl(self, action: str, window_id: str = None, 
                             application_name: str = None, window_title: str = None) -> ToolResponse:
        """Fallback implementation using wmctrl."""
        try:
            if action == "list":
                result = await asyncio.create_subprocess_exec(
                    "wmctrl", "-l",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await result.communicate()
                
                if result.returncode != 0:
                    return ToolResponse(
                        success=False,
                        error=f"wmctrl failed: {stderr.decode()}"
                    )
                
                windows = []
                for line in stdout.decode().strip().split('\n'):
                    if line:
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append({
                                "id": parts[0],
                                "desktop": parts[1],
                                "application": parts[2],
                                "title": parts[3]
                            })
                
                return ToolResponse(
                    success=True,
                    result={
                        "windows": windows,
                        "count": len(windows)
                    }
                )
            
            elif action == "focus" and (window_id or window_title):
                target = window_id if window_id else window_title
                flag = "-i" if window_id else "-a"
                
                result = await asyncio.create_subprocess_exec(
                    "wmctrl", flag, target,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                if result.returncode == 0:
                    return ToolResponse(success=True, result={"action": "focused"})
                else:
                    return ToolResponse(success=False, error="Window not found")
            
            elif action == "close" and (window_id or window_title):
                target = window_id if window_id else window_title
                flag = "-i" if window_id else "-a"
                
                result = await asyncio.create_subprocess_exec(
                    "wmctrl", flag, target, "-c",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                if result.returncode == 0:
                    return ToolResponse(success=True, result={"action": "closed"})
                else:
                    return ToolResponse(success=False, error="Failed to close window")
            
            else:
                return ToolResponse(
                    success=False,
                    error=f"Action {action} not supported with wmctrl fallback"
                )
        
        except FileNotFoundError:
            return ToolResponse(
                success=False,
                error="Neither AT-SPI nor wmctrl is available for window management"
            )
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"wmctrl error: {e}"
            )
