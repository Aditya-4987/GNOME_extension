"""
Clipboard monitor for GNOME AI Assistant.

This module monitors clipboard changes and maintains a history
of clipboard content for context-aware assistance.
"""

import asyncio
import logging
import time
import hashlib
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ClipboardDataType(Enum):
    """Types of clipboard data."""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    HTML = "html"
    RICH_TEXT = "rich_text"
    UNKNOWN = "unknown"


@dataclass
class ClipboardEntry:
    """A single clipboard entry."""
    content: Union[str, bytes]
    data_type: ClipboardDataType
    timestamp: float
    source_application: Optional[str]
    content_hash: str
    size: int
    mime_type: Optional[str] = None


class ClipboardMonitor:
    """Monitors clipboard changes and maintains history."""
    
    def __init__(self, max_history_size: int = 100):
        self.max_history_size = max_history_size
        self._clipboard_history: List[ClipboardEntry] = []
        self._last_content_hash = None
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._poll_interval = 1.0  # seconds
        
        # Size limits for security and performance
        self._max_text_size = 1024 * 1024  # 1MB
        self._max_image_size = 10 * 1024 * 1024  # 10MB
    
    async def start_monitoring(self):
        """Start monitoring clipboard changes."""
        if not self._monitoring:
            self._monitoring = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("Clipboard monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring clipboard changes."""
        if self._monitoring:
            self._monitoring = False
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("Clipboard monitoring stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._check_clipboard()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in clipboard monitor loop: {e}")
                await asyncio.sleep(1.0)  # Brief pause on error
    
    async def _check_clipboard(self):
        """Check for clipboard changes."""
        try:
            # Get current clipboard content
            current_entry = await self._get_current_clipboard()
            
            if current_entry and current_entry.content_hash != self._last_content_hash:
                # New clipboard content detected
                self._add_to_history(current_entry)
                self._last_content_hash = current_entry.content_hash
                
                logger.debug(f"New clipboard content: {current_entry.data_type.value}, "
                           f"size: {current_entry.size} bytes")
                
        except Exception as e:
            logger.error(f"Error checking clipboard: {e}")
    
    async def _get_current_clipboard(self) -> Optional[ClipboardEntry]:
        """Get the current clipboard content."""
        try:
            # Try to get text content first
            text_content = await self._get_clipboard_text()
            if text_content:
                return self._create_clipboard_entry(
                    content=text_content,
                    data_type=ClipboardDataType.TEXT,
                    mime_type="text/plain"
                )
            
            # Try to get image content
            image_content = await self._get_clipboard_image()
            if image_content:
                return self._create_clipboard_entry(
                    content=image_content,
                    data_type=ClipboardDataType.IMAGE,
                    mime_type="image/png"
                )
            
            # Try to get file list
            file_list = await self._get_clipboard_files()
            if file_list:
                return self._create_clipboard_entry(
                    content="\n".join(file_list),
                    data_type=ClipboardDataType.FILE,
                    mime_type="text/uri-list"
                )
            
        except Exception as e:
            logger.error(f"Error getting clipboard content: {e}")
        
        return None
    
    async def _get_clipboard_text(self) -> Optional[str]:
        """Get text content from clipboard."""
        try:
            # Use xclip to get clipboard content
            process = await asyncio.create_subprocess_exec(
                "xclip", "-selection", "clipboard", "-o",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                text = stdout.decode('utf-8', errors='ignore')
                
                # Check size limit
                if len(text.encode('utf-8')) <= self._max_text_size:
                    return text
                else:
                    logger.warning(f"Clipboard text too large: {len(text)} characters")
                    return text[:self._max_text_size]  # Truncate
            
        except Exception as e:
            logger.error(f"Error getting clipboard text: {e}")
        
        return None
    
    async def _get_clipboard_image(self) -> Optional[bytes]:
        """Get image content from clipboard."""
        try:
            # Use xclip to get image content
            process = await asyncio.create_subprocess_exec(
                "xclip", "-selection", "clipboard", "-t", "image/png", "-o",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                # Check size limit
                if len(stdout) <= self._max_image_size:
                    return stdout
                else:
                    logger.warning(f"Clipboard image too large: {len(stdout)} bytes")
            
        except Exception as e:
            logger.debug(f"No image in clipboard or error: {e}")
        
        return None
    
    async def _get_clipboard_files(self) -> Optional[List[str]]:
        """Get file list from clipboard."""
        try:
            # Use xclip to get file URI list
            process = await asyncio.create_subprocess_exec(
                "xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and stdout:
                content = stdout.decode('utf-8', errors='ignore').strip()
                if content:
                    # Parse URI list
                    files = []
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and line.startswith('file://'):
                            # Convert file:// URI to path
                            file_path = line[7:]  # Remove 'file://' prefix
                            files.append(file_path)
                    
                    return files if files else None
            
        except Exception as e:
            logger.debug(f"No files in clipboard or error: {e}")
        
        return None
    
    def _create_clipboard_entry(self, content: Union[str, bytes], 
                              data_type: ClipboardDataType,
                              mime_type: Optional[str] = None) -> ClipboardEntry:
        """Create a clipboard entry."""
        current_time = time.time()
        
        # Calculate content hash
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content
        
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        
        # Get source application (simplified)
        source_app = self._get_active_application()
        
        return ClipboardEntry(
            content=content,
            data_type=data_type,
            timestamp=current_time,
            source_application=source_app,
            content_hash=content_hash,
            size=len(content_bytes),
            mime_type=mime_type
        )
    
    def _get_active_application(self) -> Optional[str]:
        """Get the currently active application (source of clipboard content)."""
        try:
            # This is a simplified implementation
            # In practice, you might want to use more sophisticated methods
            import subprocess
            
            result = subprocess.run(
                ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and "window id" in result.stdout:
                window_id = result.stdout.split()[-1]
                
                # Get window class
                result = subprocess.run(
                    ["xprop", "-id", window_id, "WM_CLASS"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0 and "=" in result.stdout:
                    class_info = result.stdout.split('=', 1)[1].strip()
                    # Extract application name from WM_CLASS
                    if '"' in class_info:
                        app_name = class_info.split('"')[1]
                        return app_name
        
        except Exception as e:
            logger.debug(f"Could not get active application: {e}")
        
        return None
    
    def _add_to_history(self, entry: ClipboardEntry):
        """Add entry to clipboard history."""
        # Check for duplicates (same content hash)
        for existing_entry in self._clipboard_history:
            if existing_entry.content_hash == entry.content_hash:
                # Update timestamp of existing entry instead of adding duplicate
                existing_entry.timestamp = entry.timestamp
                return
        
        # Add new entry
        self._clipboard_history.append(entry)
        
        # Maintain size limit
        if len(self._clipboard_history) > self.max_history_size:
            self._clipboard_history = self._clipboard_history[-self.max_history_size:]
    
    def get_history(self, limit: Optional[int] = None) -> List[ClipboardEntry]:
        """Get clipboard history."""
        history = self._clipboard_history.copy()
        if limit:
            history = history[-limit:]
        return history
    
    def get_recent_text(self, limit: int = 5) -> List[str]:
        """Get recent text entries from clipboard."""
        text_entries = [
            entry.content for entry in self._clipboard_history
            if entry.data_type == ClipboardDataType.TEXT
        ]
        return text_entries[-limit:] if text_entries else []
    
    def search_history(self, query: str, data_type: Optional[ClipboardDataType] = None) -> List[ClipboardEntry]:
        """Search clipboard history."""
        query_lower = query.lower()
        results = []
        
        for entry in self._clipboard_history:
            # Filter by data type if specified
            if data_type and entry.data_type != data_type:
                continue
            
            # Search in text content
            if entry.data_type == ClipboardDataType.TEXT:
                if isinstance(entry.content, str) and query_lower in entry.content.lower():
                    results.append(entry)
            elif entry.data_type == ClipboardDataType.FILE:
                if isinstance(entry.content, str) and query_lower in entry.content.lower():
                    results.append(entry)
        
        return results
    
    def get_content_by_hash(self, content_hash: str) -> Optional[ClipboardEntry]:
        """Get clipboard entry by content hash."""
        for entry in self._clipboard_history:
            if entry.content_hash == content_hash:
                return entry
        return None
    
    async def set_clipboard_content(self, content: str) -> bool:
        """Set clipboard content."""
        try:
            process = await asyncio.create_subprocess_exec(
                "xclip", "-selection", "clipboard",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate(input=content.encode('utf-8'))
            
            if process.returncode == 0:
                logger.info("Clipboard content set successfully")
                return True
            else:
                logger.error(f"Failed to set clipboard content: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Error setting clipboard content: {e}")
            return False
    
    def clear_history(self):
        """Clear clipboard history."""
        self._clipboard_history.clear()
        self._last_content_hash = None
        logger.info("Clipboard history cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get clipboard usage statistics."""
        if not self._clipboard_history:
            return {"total_entries": 0}
        
        # Count by data type
        type_counts = {}
        for entry in self._clipboard_history:
            type_name = entry.data_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        # Count by source application
        app_counts = {}
        for entry in self._clipboard_history:
            if entry.source_application:
                app_counts[entry.source_application] = app_counts.get(entry.source_application, 0) + 1
        
        # Calculate size statistics
        sizes = [entry.size for entry in self._clipboard_history]
        
        return {
            "total_entries": len(self._clipboard_history),
            "types": type_counts,
            "source_applications": app_counts,
            "size_stats": {
                "total_bytes": sum(sizes),
                "average_bytes": sum(sizes) / len(sizes) if sizes else 0,
                "max_bytes": max(sizes) if sizes else 0,
                "min_bytes": min(sizes) if sizes else 0
            },
            "time_range": {
                "oldest": min(entry.timestamp for entry in self._clipboard_history),
                "newest": max(entry.timestamp for entry in self._clipboard_history)
            } if self._clipboard_history else {}
        }
    
    def export_history(self, include_binary: bool = False) -> Dict[str, Any]:
        """Export clipboard history for backup or analysis."""
        exported_entries = []
        
        for entry in self._clipboard_history:
            exported_entry = {
                "data_type": entry.data_type.value,
                "timestamp": entry.timestamp,
                "source_application": entry.source_application,
                "content_hash": entry.content_hash,
                "size": entry.size,
                "mime_type": entry.mime_type
            }
            
            # Include content based on type and settings
            if entry.data_type == ClipboardDataType.TEXT:
                exported_entry["content"] = entry.content
            elif entry.data_type == ClipboardDataType.FILE:
                exported_entry["content"] = entry.content
            elif include_binary and entry.data_type == ClipboardDataType.IMAGE:
                # For images, include base64-encoded content
                import base64
                if isinstance(entry.content, bytes):
                    exported_entry["content"] = base64.b64encode(entry.content).decode('ascii')
            
            exported_entries.append(exported_entry)
        
        return {
            "version": "1.0",
            "export_timestamp": time.time(),
            "total_entries": len(exported_entries),
            "entries": exported_entries
        }
