"""
Package manager tool for GNOME AI Assistant.

This module provides functionality to manage system packages
using various package managers (apt, dnf, pacman, flatpak, snap).
"""

import asyncio
import logging
import shutil
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolParameter, ToolResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PackageInfo:
    """Information about a package."""
    name: str
    version: str
    description: str
    installed: bool
    size: Optional[str] = None
    repository: Optional[str] = None


class PackageManagerTool(BaseTool):
    """Tool for managing system packages."""
    
    def __init__(self):
        super().__init__(
            name="package_manager",
            description="Manage system packages (install, remove, update, search)",
            parameters=[
                ToolParameter(
                    name="action",
                    description="Package management action",
                    type="string",
                    required=True,
                    enum=[
                        "search", "install", "remove", "update", "upgrade",
                        "list_installed", "info", "list_available",
                        "clean", "autoremove"
                    ]
                ),
                ToolParameter(
                    name="package_name",
                    description="Name of the package",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="package_manager",
                    description="Specific package manager to use",
                    type="string",
                    required=False,
                    enum=["auto", "apt", "dnf", "pacman", "flatpak", "snap"]
                ),
                ToolParameter(
                    name="yes",
                    description="Automatically answer yes to prompts",
                    type="boolean",
                    required=False
                )
            ]
        )
        self._available_managers = self._detect_package_managers()
    
    def _detect_package_managers(self) -> Dict[str, bool]:
        """Detect available package managers on the system."""
        managers = {
            "apt": shutil.which("apt") is not None,
            "dnf": shutil.which("dnf") is not None,
            "pacman": shutil.which("pacman") is not None,
            "flatpak": shutil.which("flatpak") is not None,
            "snap": shutil.which("snap") is not None
        }
        
        logger.info(f"Available package managers: {[k for k, v in managers.items() if v]}")
        return managers
    
    def _get_primary_manager(self) -> Optional[str]:
        """Get the primary package manager for the system."""
        if self._available_managers.get("apt"):
            return "apt"
        elif self._available_managers.get("dnf"):
            return "dnf"
        elif self._available_managers.get("pacman"):
            return "pacman"
        else:
            return None
    
    async def _run_command(self, cmd: List[str], require_root: bool = False) -> tuple[int, str, str]:
        """Run a package manager command."""
        try:
            if require_root:
                # Check if we need sudo
                if cmd[0] in ["apt", "dnf", "pacman"] and cmd[1] in ["install", "remove", "upgrade", "update"]:
                    cmd = ["sudo"] + cmd
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return process.returncode, stdout.decode(), stderr.decode()
            
        except Exception as e:
            logger.error(f"Error running command {' '.join(cmd)}: {e}")
            return 1, "", str(e)
    
    async def _search_packages(self, query: str, manager: str) -> List[PackageInfo]:
        """Search for packages."""
        packages = []
        
        try:
            if manager == "apt":
                cmd = ["apt", "search", query]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    lines = stdout.split('\n')
                    current_package = None
                    
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('WARNING'):
                            if '/' in line and ' - ' in line:
                                # Package line: package/repo version - description
                                parts = line.split(' - ', 1)
                                if len(parts) == 2:
                                    package_part = parts[0]
                                    description = parts[1]
                                    
                                    if '/' in package_part:
                                        name = package_part.split('/')[0]
                                        version = ""
                                        
                                        packages.append(PackageInfo(
                                            name=name,
                                            version=version,
                                            description=description,
                                            installed=False
                                        ))
            
            elif manager == "dnf":
                cmd = ["dnf", "search", query]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    lines = stdout.split('\n')
                    for line in lines:
                        if ' : ' in line and not line.startswith('='):
                            parts = line.split(' : ', 1)
                            if len(parts) == 2:
                                name_arch = parts[0].strip()
                                description = parts[1].strip()
                                
                                name = name_arch.split('.')[0] if '.' in name_arch else name_arch
                                
                                packages.append(PackageInfo(
                                    name=name,
                                    version="",
                                    description=description,
                                    installed=False
                                ))
            
            elif manager == "pacman":
                cmd = ["pacman", "-Ss", query]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    lines = stdout.split('\n')
                    i = 0
                    while i < len(lines):
                        line = lines[i].strip()
                        if '/' in line and ' ' in line:
                            # Package line: repo/name version
                            parts = line.split(' ', 1)
                            if len(parts) >= 2:
                                repo_name = parts[0]
                                version = parts[1] if len(parts) > 1 else ""
                                
                                if '/' in repo_name:
                                    name = repo_name.split('/')[1]
                                    
                                    # Description is on the next line
                                    description = ""
                                    if i + 1 < len(lines):
                                        desc_line = lines[i + 1].strip()
                                        if desc_line and not '/' in desc_line:
                                            description = desc_line
                                    
                                    packages.append(PackageInfo(
                                        name=name,
                                        version=version,
                                        description=description,
                                        installed=False
                                    ))
                        i += 1
            
            elif manager == "flatpak":
                cmd = ["flatpak", "search", query]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    lines = stdout.split('\n')[1:]  # Skip header
                    for line in lines:
                        if line.strip():
                            parts = line.split('\t')
                            if len(parts) >= 3:
                                name = parts[0].strip()
                                description = parts[1].strip()
                                app_id = parts[2].strip()
                                
                                packages.append(PackageInfo(
                                    name=name,
                                    version="",
                                    description=description,
                                    installed=False
                                ))
            
            elif manager == "snap":
                cmd = ["snap", "find", query]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    lines = stdout.split('\n')[1:]  # Skip header
                    for line in lines:
                        if line.strip():
                            parts = line.split()
                            if len(parts) >= 4:
                                name = parts[0]
                                version = parts[1]
                                publisher = parts[2]
                                description = ' '.join(parts[4:])
                                
                                packages.append(PackageInfo(
                                    name=name,
                                    version=version,
                                    description=description,
                                    installed=False
                                ))
                
        except Exception as e:
            logger.error(f"Error searching packages with {manager}: {e}")
        
        return packages
    
    async def _install_package(self, package_name: str, manager: str, auto_yes: bool = False) -> tuple[bool, str]:
        """Install a package."""
        try:
            cmd = []
            
            if manager == "apt":
                cmd = ["apt", "install"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "dnf":
                cmd = ["dnf", "install"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "pacman":
                cmd = ["pacman", "-S"]
                if auto_yes:
                    cmd.append("--noconfirm")
                cmd.append(package_name)
            
            elif manager == "flatpak":
                cmd = ["flatpak", "install"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "snap":
                cmd = ["snap", "install", package_name]
            
            if not cmd:
                return False, f"Unsupported package manager: {manager}"
            
            returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
            
            if returncode == 0:
                return True, f"Successfully installed {package_name}"
            else:
                return False, f"Failed to install {package_name}: {stderr}"
                
        except Exception as e:
            logger.error(f"Error installing package {package_name}: {e}")
            return False, str(e)
    
    async def _remove_package(self, package_name: str, manager: str, auto_yes: bool = False) -> tuple[bool, str]:
        """Remove a package."""
        try:
            cmd = []
            
            if manager == "apt":
                cmd = ["apt", "remove"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "dnf":
                cmd = ["dnf", "remove"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "pacman":
                cmd = ["pacman", "-R"]
                if auto_yes:
                    cmd.append("--noconfirm")
                cmd.append(package_name)
            
            elif manager == "flatpak":
                cmd = ["flatpak", "uninstall"]
                if auto_yes:
                    cmd.append("-y")
                cmd.append(package_name)
            
            elif manager == "snap":
                cmd = ["snap", "remove", package_name]
            
            if not cmd:
                return False, f"Unsupported package manager: {manager}"
            
            returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
            
            if returncode == 0:
                return True, f"Successfully removed {package_name}"
            else:
                return False, f"Failed to remove {package_name}: {stderr}"
                
        except Exception as e:
            logger.error(f"Error removing package {package_name}: {e}")
            return False, str(e)
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute package management action."""
        action = parameters.get("action")
        package_name = parameters.get("package_name", "")
        manager = parameters.get("package_manager", "auto")
        auto_yes = parameters.get("yes", False)
        
        # Determine package manager
        if manager == "auto":
            manager = self._get_primary_manager()
            if not manager:
                return ToolResponse(
                    success=False,
                    result=None,
                    error="No supported package manager found"
                )
        
        if not self._available_managers.get(manager):
            return ToolResponse(
                success=False,
                result=None,
                error=f"Package manager '{manager}' is not available"
            )
        
        try:
            if action == "search":
                if not package_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Package name is required for search"
                    )
                
                packages = await self._search_packages(package_name, manager)
                return ToolResponse(
                    success=True,
                    result={
                        "action": "search",
                        "query": package_name,
                        "manager": manager,
                        "packages": [
                            {
                                "name": pkg.name,
                                "version": pkg.version,
                                "description": pkg.description,
                                "installed": pkg.installed
                            }
                            for pkg in packages
                        ]
                    }
                )
            
            elif action == "install":
                if not package_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Package name is required for installation"
                    )
                
                success, message = await self._install_package(package_name, manager, auto_yes)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "install",
                        "package": package_name,
                        "manager": manager,
                        "message": message
                    } if success else None,
                    error=None if success else message
                )
            
            elif action == "remove":
                if not package_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Package name is required for removal"
                    )
                
                success, message = await self._remove_package(package_name, manager, auto_yes)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "remove",
                        "package": package_name,
                        "manager": manager,
                        "message": message
                    } if success else None,
                    error=None if success else message
                )
            
            elif action == "update":
                cmd = []
                if manager == "apt":
                    cmd = ["apt", "update"]
                elif manager == "dnf":
                    cmd = ["dnf", "check-update"]
                elif manager == "pacman":
                    cmd = ["pacman", "-Sy"]
                elif manager == "flatpak":
                    cmd = ["flatpak", "update"]
                elif manager == "snap":
                    cmd = ["snap", "refresh", "--list"]
                
                if cmd:
                    returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
                    return ToolResponse(
                        success=returncode == 0,
                        result={
                            "action": "update",
                            "manager": manager,
                            "output": stdout
                        } if returncode == 0 else None,
                        error=stderr if returncode != 0 else None
                    )
            
            elif action == "upgrade":
                cmd = []
                if manager == "apt":
                    cmd = ["apt", "upgrade"]
                    if auto_yes:
                        cmd.append("-y")
                elif manager == "dnf":
                    cmd = ["dnf", "upgrade"]
                    if auto_yes:
                        cmd.append("-y")
                elif manager == "pacman":
                    cmd = ["pacman", "-Su"]
                    if auto_yes:
                        cmd.append("--noconfirm")
                elif manager == "flatpak":
                    cmd = ["flatpak", "update"]
                    if auto_yes:
                        cmd.append("-y")
                elif manager == "snap":
                    cmd = ["snap", "refresh"]
                
                if cmd:
                    returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
                    return ToolResponse(
                        success=returncode == 0,
                        result={
                            "action": "upgrade",
                            "manager": manager,
                            "output": stdout
                        } if returncode == 0 else None,
                        error=stderr if returncode != 0 else None
                    )
            
            else:
                return ToolResponse(
                    success=False,
                    result=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Error executing package manager action {action}: {e}")
            return ToolResponse(
                success=False,
                result=None,
                error=f"Failed to execute action: {str(e)}"
            )
