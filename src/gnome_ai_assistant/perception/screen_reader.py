"""
Screen reader for GNOME AI Assistant.

This module provides screen reading capabilities using AT-SPI
(Assistive Technology Service Provider Interface) to extract
text and UI element information from the desktop.
"""

import asyncio
import logging
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ElementType(Enum):
    """Types of UI elements."""
    WINDOW = "window"
    BUTTON = "button"
    TEXT = "text"
    TEXTBOX = "textbox"
    MENU = "menu"
    MENUITEM = "menuitem"
    LABEL = "label"
    FRAME = "frame"
    PANEL = "panel"
    TOOLBAR = "toolbar"
    STATUSBAR = "statusbar"
    UNKNOWN = "unknown"


@dataclass
class UIElement:
    """Represents a UI element from screen reading."""
    name: str
    role: str
    element_type: ElementType
    text_content: str
    position: Tuple[int, int]
    size: Tuple[int, int]
    states: List[str]
    actions: List[str]
    parent: Optional[str] = None
    children: List[str] = None


@dataclass
class ScreenContent:
    """Complete screen content from screen reader."""
    focused_element: Optional[UIElement]
    active_window: Optional[UIElement]
    elements: List[UIElement]
    text_content: str
    timestamp: float


class ScreenReader:
    """Screen reader using AT-SPI for accessibility."""
    
    def __init__(self):
        self._at_spi_enabled = False
        self._last_scan_time = 0.0
        self._cache_duration = 1.0  # Cache for 1 second
        self._cached_content: Optional[ScreenContent] = None
    
    async def _check_at_spi_availability(self) -> bool:
        """Check if AT-SPI is available and accessible."""
        try:
            # Check if accessibility is enabled
            process = await asyncio.create_subprocess_exec(
                "gsettings", "get", "org.gnome.desktop.interface", "toolkit-accessibility",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                accessibility_enabled = "true" in stdout.decode().lower()
                if not accessibility_enabled:
                    logger.warning("Accessibility not enabled in GNOME. Screen reading may not work.")
                    return False
            
            # Check if accerciser or other AT-SPI tools are available
            tools = ["accerciser", "at-spi2-core"]
            for tool in tools:
                process = await asyncio.create_subprocess_exec(
                    "which", tool,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    self._at_spi_enabled = True
                    return True
            
            logger.warning("No AT-SPI tools found. Install accerciser or at-spi2-core.")
            return False
            
        except Exception as e:
            logger.error(f"Error checking AT-SPI availability: {e}")
            return False
    
    async def _get_window_list(self) -> List[Dict[str, Any]]:
        """Get list of all windows using wmctrl."""
        windows = []
        
        try:
            process = await asyncio.create_subprocess_exec(
                "wmctrl", "-l",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                lines = stdout.decode().split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split(None, 3)
                        if len(parts) >= 4:
                            windows.append({
                                "id": parts[0],
                                "desktop": parts[1],
                                "host": parts[2],
                                "title": parts[3]
                            })
            
        except Exception as e:
            logger.error(f"Error getting window list: {e}")
        
        return windows
    
    async def _get_active_window(self) -> Optional[Dict[str, Any]]:
        """Get the currently active window."""
        try:
            process = await asyncio.create_subprocess_exec(
                "xprop", "-root", "_NET_ACTIVE_WINDOW",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode().strip()
                if "window id" in output:
                    window_id = output.split()[-1]
                    
                    # Get window details
                    process = await asyncio.create_subprocess_exec(
                        "xprop", "-id", window_id, "WM_NAME", "_NET_WM_NAME",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        lines = stdout.decode().split('\n')
                        title = "Unknown"
                        
                        for line in lines:
                            if "_NET_WM_NAME" in line and "=" in line:
                                title = line.split('=', 1)[1].strip().strip('"')
                                break
                            elif "WM_NAME" in line and "=" in line:
                                title = line.split('=', 1)[1].strip().strip('"')
                        
                        return {
                            "id": window_id,
                            "title": title
                        }
            
        except Exception as e:
            logger.error(f"Error getting active window: {e}")
        
        return None
    
    async def _extract_text_with_tesseract(self, screenshot_path: str) -> str:
        """Extract text from screenshot using Tesseract OCR."""
        try:
            process = await asyncio.create_subprocess_exec(
                "tesseract", screenshot_path, "stdout",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.warning(f"Tesseract failed: {stderr.decode()}")
                return ""
                
        except Exception as e:
            logger.error(f"Error running Tesseract: {e}")
            return ""
    
    async def _take_screenshot(self) -> Optional[str]:
        """Take a screenshot and return the file path."""
        try:
            import tempfile
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
                screenshot_path = temp_file.name
            
            # Take screenshot using gnome-screenshot
            process = await asyncio.create_subprocess_exec(
                "gnome-screenshot", "-f", screenshot_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return screenshot_path
            else:
                # Try with import (ImageMagick)
                process = await asyncio.create_subprocess_exec(
                    "import", "-window", "root", screenshot_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    return screenshot_path
                else:
                    logger.error("Failed to take screenshot with both methods")
                    return None
                    
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return None
    
    async def _get_screen_text_ocr(self) -> str:
        """Get screen text using OCR as fallback."""
        try:
            screenshot_path = await self._take_screenshot()
            if screenshot_path:
                text = await self._extract_text_with_tesseract(screenshot_path)
                
                # Clean up screenshot
                import os
                try:
                    os.unlink(screenshot_path)
                except:
                    pass
                
                return text
            
        except Exception as e:
            logger.error(f"Error getting screen text with OCR: {e}")
        
        return ""
    
    async def _parse_at_spi_output(self, output: str) -> List[UIElement]:
        """Parse AT-SPI output to extract UI elements."""
        elements = []
        
        try:
            # This is a simplified parser for AT-SPI output
            # In a real implementation, you would use proper AT-SPI bindings
            lines = output.split('\n')
            current_element = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                if "role:" in line.lower():
                    role = line.split(":")[-1].strip()
                    element_type = ElementType.UNKNOWN
                    
                    # Map roles to element types
                    role_lower = role.lower()
                    if "button" in role_lower:
                        element_type = ElementType.BUTTON
                    elif "text" in role_lower:
                        element_type = ElementType.TEXT
                    elif "window" in role_lower:
                        element_type = ElementType.WINDOW
                    elif "menu" in role_lower:
                        element_type = ElementType.MENU
                    elif "label" in role_lower:
                        element_type = ElementType.LABEL
                    
                    if current_element:
                        elements.append(current_element)
                    
                    current_element = UIElement(
                        name="",
                        role=role,
                        element_type=element_type,
                        text_content="",
                        position=(0, 0),
                        size=(0, 0),
                        states=[],
                        actions=[]
                    )
                
                elif "name:" in line.lower() and current_element:
                    current_element.name = line.split(":")[-1].strip()
                
                elif "text:" in line.lower() and current_element:
                    current_element.text_content = line.split(":")[-1].strip()
                
                elif "position:" in line.lower() and current_element:
                    try:
                        pos_str = line.split(":")[-1].strip()
                        if "," in pos_str:
                            x, y = pos_str.split(",")
                            current_element.position = (int(x.strip()), int(y.strip()))
                    except:
                        pass
                
                elif "size:" in line.lower() and current_element:
                    try:
                        size_str = line.split(":")[-1].strip()
                        if "," in size_str:
                            w, h = size_str.split(",")
                            current_element.size = (int(w.strip()), int(h.strip()))
                    except:
                        pass
            
            # Add the last element
            if current_element:
                elements.append(current_element)
                
        except Exception as e:
            logger.error(f"Error parsing AT-SPI output: {e}")
        
        return elements
    
    async def read_screen(self, use_cache: bool = True) -> ScreenContent:
        """Read the current screen content."""
        import time
        current_time = time.time()
        
        # Check cache
        if (use_cache and self._cached_content and 
            current_time - self._last_scan_time < self._cache_duration):
            return self._cached_content
        
        try:
            # Initialize variables
            focused_element = None
            active_window = None
            elements = []
            text_content = ""
            
            # Check AT-SPI availability
            if not self._at_spi_enabled:
                await self._check_at_spi_availability()
            
            # Get active window information
            active_window_info = await self._get_active_window()
            if active_window_info:
                active_window = UIElement(
                    name=active_window_info["title"],
                    role="window",
                    element_type=ElementType.WINDOW,
                    text_content=active_window_info["title"],
                    position=(0, 0),
                    size=(0, 0),
                    states=["active"],
                    actions=[]
                )
            
            # Try to get detailed UI information using AT-SPI
            if self._at_spi_enabled:
                try:
                    # This would be replaced with proper AT-SPI calls
                    # For now, we'll use a simplified approach
                    process = await asyncio.create_subprocess_exec(
                        "busctl", "--user", "introspect", "org.a11y.Bus", "/org/a11y/bus",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        elements = await self._parse_at_spi_output(stdout.decode())
                    
                except Exception as e:
                    logger.warning(f"AT-SPI introspection failed: {e}")
            
            # Get text content using OCR as fallback
            if not elements or not any(elem.text_content for elem in elements):
                text_content = await self._get_screen_text_ocr()
            else:
                # Combine text from all elements
                text_content = "\n".join(
                    elem.text_content for elem in elements 
                    if elem.text_content
                )
            
            # Create screen content
            screen_content = ScreenContent(
                focused_element=focused_element,
                active_window=active_window,
                elements=elements,
                text_content=text_content,
                timestamp=current_time
            )
            
            # Cache the result
            self._cached_content = screen_content
            self._last_scan_time = current_time
            
            logger.info(f"Screen reading completed. Found {len(elements)} elements.")
            return screen_content
            
        except Exception as e:
            logger.error(f"Error reading screen: {e}")
            
            # Return empty content on error
            return ScreenContent(
                focused_element=None,
                active_window=None,
                elements=[],
                text_content="",
                timestamp=current_time
            )
    
    async def get_element_at_position(self, x: int, y: int) -> Optional[UIElement]:
        """Get the UI element at a specific screen position."""
        try:
            screen_content = await self.read_screen()
            
            for element in screen_content.elements:
                ex, ey = element.position
                ew, eh = element.size
                
                if (ex <= x <= ex + ew and ey <= y <= ey + eh):
                    return element
            
        except Exception as e:
            logger.error(f"Error getting element at position ({x}, {y}): {e}")
        
        return None
    
    async def find_elements_by_text(self, text: str) -> List[UIElement]:
        """Find UI elements containing specific text."""
        try:
            screen_content = await self.read_screen()
            matching_elements = []
            
            text_lower = text.lower()
            
            for element in screen_content.elements:
                if (text_lower in element.text_content.lower() or 
                    text_lower in element.name.lower()):
                    matching_elements.append(element)
            
            return matching_elements
            
        except Exception as e:
            logger.error(f"Error finding elements by text '{text}': {e}")
            return []
    
    async def get_screen_summary(self) -> Dict[str, Any]:
        """Get a summary of the current screen content."""
        try:
            screen_content = await self.read_screen()
            
            summary = {
                "timestamp": screen_content.timestamp,
                "active_window": screen_content.active_window.name if screen_content.active_window else None,
                "element_count": len(screen_content.elements),
                "element_types": {},
                "has_text": bool(screen_content.text_content),
                "text_length": len(screen_content.text_content),
                "interactive_elements": []
            }
            
            # Count element types
            for element in screen_content.elements:
                element_type = element.element_type.value
                summary["element_types"][element_type] = summary["element_types"].get(element_type, 0) + 1
                
                # Collect interactive elements
                if element.element_type in [ElementType.BUTTON, ElementType.TEXTBOX, ElementType.MENUITEM]:
                    summary["interactive_elements"].append({
                        "name": element.name,
                        "type": element_type,
                        "text": element.text_content,
                        "position": element.position
                    })
            
            return summary
            
        except Exception as e:
            logger.error(f"Error getting screen summary: {e}")
            return {"error": str(e)}
