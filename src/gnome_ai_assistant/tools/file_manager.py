"""File management tool for GNOME AI Assistant."""

import os
import shutil
import mimetypes
from pathlib import Path
from typing import List, Optional, Dict, Any
import asyncio
import aiofiles
import json

from .base import BaseTool, ToolResponse, ToolParameter
from ..core.permissions import RiskLevel
from ..utils.logger import get_logger

logger = get_logger("tools.file_manager")


class FileManagerTool(BaseTool):
    """Tool for file and directory operations."""
    
    def __init__(self):
        super().__init__()
        self.name = "file_manager"
        self.description = "Manage files and directories (read, write, copy, move, delete)"
        self.category = "system"
        self.risk_level = RiskLevel.MEDIUM
        self.required_permissions = ["file_system_access"]
        
        # Override auto-discovered parameters with more detailed ones
        self.parameters = [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum_values=["read", "write", "copy", "move", "delete", "list", "create_dir", "get_info", "search"]
            ),
            ToolParameter(
                name="path",
                type="string",
                description="File or directory path",
                required=True
            ),
            ToolParameter(
                name="content",
                type="string",
                description="Content to write (for write action)",
                required=False
            ),
            ToolParameter(
                name="destination",
                type="string",
                description="Destination path (for copy/move actions)",
                required=False
            ),
            ToolParameter(
                name="recursive",
                type="boolean",
                description="Recursive operation (for list/delete actions)",
                required=False,
                default=False
            ),
            ToolParameter(
                name="pattern",
                type="string",
                description="Search pattern (for search action)",
                required=False
            )
        ]
    
    async def execute(self, action: str, path: str, content: str = None, 
                     destination: str = None, recursive: bool = False, 
                     pattern: str = None) -> ToolResponse:
        """Execute file management operation."""
        try:
            # Validate and normalize path
            path = Path(path).expanduser().resolve()
            
            # Security check - prevent access to sensitive directories
            if self._is_sensitive_path(path):
                return ToolResponse(
                    success=False,
                    error=f"Access denied to sensitive path: {path}"
                )
            
            # Execute action
            if action == "read":
                return await self._read_file(path)
            elif action == "write":
                return await self._write_file(path, content)
            elif action == "copy":
                return await self._copy_item(path, Path(destination).expanduser().resolve())
            elif action == "move":
                return await self._move_item(path, Path(destination).expanduser().resolve())
            elif action == "delete":
                return await self._delete_item(path, recursive)
            elif action == "list":
                return await self._list_directory(path, recursive)
            elif action == "create_dir":
                return await self._create_directory(path)
            elif action == "get_info":
                return await self._get_file_info(path)
            elif action == "search":
                return await self._search_files(path, pattern, recursive)
            else:
                return ToolResponse(
                    success=False,
                    error=f"Unknown action: {action}"
                )
        
        except Exception as e:
            logger.error(f"File manager error: {e}")
            return ToolResponse(
                success=False,
                error=str(e)
            )
    
    def _is_sensitive_path(self, path: Path) -> bool:
        """Check if path is in a sensitive directory."""
        sensitive_dirs = [
            "/etc",
            "/boot",
            "/sys",
            "/proc",
            "/dev"
        ]
        
        path_str = str(path)
        for sensitive in sensitive_dirs:
            if path_str.startswith(sensitive):
                return True
        
        return False
    
    async def _read_file(self, path: Path) -> ToolResponse:
        """Read file content."""
        try:
            if not path.exists():
                return ToolResponse(
                    success=False,
                    error=f"File does not exist: {path}"
                )
            
            if not path.is_file():
                return ToolResponse(
                    success=False,
                    error=f"Path is not a file: {path}"
                )
            
            # Check file size
            file_size = path.stat().st_size
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                return ToolResponse(
                    success=False,
                    error=f"File too large: {file_size} bytes (max 10MB)"
                )
            
            # Try to detect encoding
            try:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    
                return ToolResponse(
                    success=True,
                    result={
                        "content": content,
                        "size": file_size,
                        "encoding": "utf-8"
                    }
                )
            except UnicodeDecodeError:
                # Try binary read for non-text files
                async with aiofiles.open(path, 'rb') as f:
                    binary_content = await f.read()
                    
                return ToolResponse(
                    success=True,
                    result={
                        "content": f"<binary file: {len(binary_content)} bytes>",
                        "size": file_size,
                        "encoding": "binary",
                        "mime_type": mimetypes.guess_type(str(path))[0]
                    }
                )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to read file: {e}"
            )
    
    async def _write_file(self, path: Path, content: str) -> ToolResponse:
        """Write content to file."""
        try:
            if content is None:
                return ToolResponse(
                    success=False,
                    error="Content is required for write action"
                )
            
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                await f.write(content)
            
            return ToolResponse(
                success=True,
                result={
                    "path": str(path),
                    "size": len(content.encode('utf-8')),
                    "action": "created" if not path.existed() else "updated"
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to write file: {e}"
            )
    
    async def _copy_item(self, source: Path, destination: Path) -> ToolResponse:
        """Copy file or directory."""
        try:
            if not source.exists():
                return ToolResponse(
                    success=False,
                    error=f"Source does not exist: {source}"
                )
            
            # Check if destination would overwrite
            if destination.exists():
                return ToolResponse(
                    success=False,
                    error=f"Destination already exists: {destination}"
                )
            
            # Create parent directories
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy
            if source.is_file():
                await asyncio.get_event_loop().run_in_executor(
                    None, shutil.copy2, str(source), str(destination)
                )
            else:
                await asyncio.get_event_loop().run_in_executor(
                    None, shutil.copytree, str(source), str(destination)
                )
            
            return ToolResponse(
                success=True,
                result={
                    "source": str(source),
                    "destination": str(destination),
                    "type": "file" if source.is_file() else "directory"
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to copy: {e}"
            )
    
    async def _move_item(self, source: Path, destination: Path) -> ToolResponse:
        """Move file or directory."""
        try:
            if not source.exists():
                return ToolResponse(
                    success=False,
                    error=f"Source does not exist: {source}"
                )
            
            # Check if destination would overwrite
            if destination.exists():
                return ToolResponse(
                    success=False,
                    error=f"Destination already exists: {destination}"
                )
            
            # Create parent directories
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Move
            await asyncio.get_event_loop().run_in_executor(
                None, shutil.move, str(source), str(destination)
            )
            
            return ToolResponse(
                success=True,
                result={
                    "source": str(source),
                    "destination": str(destination)
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to move: {e}"
            )
    
    async def _delete_item(self, path: Path, recursive: bool) -> ToolResponse:
        """Delete file or directory."""
        try:
            if not path.exists():
                return ToolResponse(
                    success=False,
                    error=f"Path does not exist: {path}"
                )
            
            if path.is_file():
                path.unlink()
                return ToolResponse(
                    success=True,
                    result={
                        "path": str(path),
                        "type": "file"
                    }
                )
            elif path.is_dir():
                if recursive:
                    await asyncio.get_event_loop().run_in_executor(
                        None, shutil.rmtree, str(path)
                    )
                else:
                    path.rmdir()  # Only works if directory is empty
                
                return ToolResponse(
                    success=True,
                    result={
                        "path": str(path),
                        "type": "directory",
                        "recursive": recursive
                    }
                )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to delete: {e}"
            )
    
    async def _list_directory(self, path: Path, recursive: bool) -> ToolResponse:
        """List directory contents."""
        try:
            if not path.exists():
                return ToolResponse(
                    success=False,
                    error=f"Directory does not exist: {path}"
                )
            
            if not path.is_dir():
                return ToolResponse(
                    success=False,
                    error=f"Path is not a directory: {path}"
                )
            
            items = []
            
            if recursive:
                for item in path.rglob("*"):
                    items.append(self._get_item_info(item))
            else:
                for item in path.iterdir():
                    items.append(self._get_item_info(item))
            
            return ToolResponse(
                success=True,
                result={
                    "path": str(path),
                    "items": items,
                    "count": len(items),
                    "recursive": recursive
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to list directory: {e}"
            )
    
    async def _create_directory(self, path: Path) -> ToolResponse:
        """Create directory."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            
            return ToolResponse(
                success=True,
                result={
                    "path": str(path),
                    "created": True
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to create directory: {e}"
            )
    
    async def _get_file_info(self, path: Path) -> ToolResponse:
        """Get file/directory information."""
        try:
            if not path.exists():
                return ToolResponse(
                    success=False,
                    error=f"Path does not exist: {path}"
                )
            
            info = self._get_item_info(path)
            
            return ToolResponse(
                success=True,
                result=info
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to get file info: {e}"
            )
    
    async def _search_files(self, path: Path, pattern: str, recursive: bool) -> ToolResponse:
        """Search for files matching pattern."""
        try:
            if not path.exists():
                return ToolResponse(
                    success=False,
                    error=f"Directory does not exist: {path}"
                )
            
            if not path.is_dir():
                return ToolResponse(
                    success=False,
                    error=f"Path is not a directory: {path}"
                )
            
            if not pattern:
                return ToolResponse(
                    success=False,
                    error="Search pattern is required"
                )
            
            matches = []
            
            if recursive:
                for item in path.rglob(pattern):
                    matches.append(self._get_item_info(item))
            else:
                for item in path.glob(pattern):
                    matches.append(self._get_item_info(item))
            
            return ToolResponse(
                success=True,
                result={
                    "path": str(path),
                    "pattern": pattern,
                    "matches": matches,
                    "count": len(matches),
                    "recursive": recursive
                }
            )
        
        except Exception as e:
            return ToolResponse(
                success=False,
                error=f"Failed to search files: {e}"
            )
    
    def _get_item_info(self, path: Path) -> Dict[str, Any]:
        """Get information about a file or directory."""
        try:
            stat = path.stat()
            
            info = {
                "name": path.name,
                "path": str(path),
                "type": "directory" if path.is_dir() else "file",
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "permissions": oct(stat.st_mode)[-3:]
            }
            
            if path.is_file():
                info["mime_type"] = mimetypes.guess_type(str(path))[0]
            
            return info
        
        except Exception as e:
            return {
                "name": path.name,
                "path": str(path),
                "error": str(e)
            }
