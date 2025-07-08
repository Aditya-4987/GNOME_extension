"""
Advanced package manager tool for GNOME AI Assistant.

This module provides comprehensive package management capabilities
for Arch Linux, including AUR support.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
import re

from .base import BaseTool, ToolParameter, ToolResponse
from ..utils.logger import get_logger
from ..core.permissions import RiskLevel

logger = get_logger(__name__)


@dataclass
class PackageInfo:
    """Information about a package."""
    name: str
    version: str
    description: str
    repository: str
    installed: bool
    size: str
    dependencies: List[str]
    maintainer: str
    url: str


class PackageManagerTool(BaseTool):
    """Advanced package manager tool for Arch Linux."""
    
    def __init__(self):
        super().__init__(
            name="package_manager",
            description="Manage system packages using pacman and AUR helpers",
            parameters=[
                ToolParameter(
                    name="action",
                    description="Package management action",
                    type="string",
                    required=True,
                    enum=[
                        "search", "install", "remove", "update", "upgrade",
                        "info", "list_installed", "list_orphans", "clean_cache",
                        "search_aur", "install_aur", "list_aur", "check_updates",
                        "dependency_tree", "package_files", "which_package",
                        "security_updates", "downgrade", "hold_package",
                        "unhold_package", "rebuild_database"
                    ]
                ),
                ToolParameter(
                    name="package_name",
                    description="Package name to operate on",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="packages",
                    description="List of package names (JSON array)",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="confirm",
                    description="Confirm dangerous operations",
                    type="boolean",
                    required=False
                ),
                ToolParameter(
                    name="force",
                    description="Force operation (use with caution)",
                    type="boolean",
                    required=False
                ),
                ToolParameter(
                    name="query",
                    description="Search query",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="repository",
                    description="Specific repository to search",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="aur_helper",
                    description="AUR helper to use (yay, paru, etc.)",
                    type="string",
                    required=False
                )
            ],
            required_permissions=["system_admin", "package_management"],
            risk_level=RiskLevel.HIGH
        )
    
    async def _run_command(self, cmd: List[str], require_sudo: bool = False) -> Tuple[int, str, str]:
        """Run a command and return exit code, stdout, stderr."""
        try:
            if require_sudo:
                cmd = ["sudo"] + cmd
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            return process.returncode, stdout.decode(), stderr.decode()
            
        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return 1, "", str(e)
    
    async def _get_aur_helper(self, preferred: Optional[str] = None) -> Optional[str]:
        """Get available AUR helper."""
        helpers = [preferred] if preferred else ["yay", "paru", "auracle", "aurman", "pakku"]
        
        for helper in helpers:
            if helper:
                returncode, _, _ = await self._run_command(["which", helper])
                if returncode == 0:
                    return helper
        
        return None
    
    async def _search_packages(self, query: str, repository: Optional[str] = None) -> List[PackageInfo]:
        """Search for packages in official repositories."""
        try:
            cmd = ["pacman", "-Ss"]
            if repository:
                cmd.extend([f"{repository}/{query}"])
            else:
                cmd.append(query)
            
            returncode, stdout, stderr = await self._run_command(cmd)
            
            packages = []
            if returncode == 0:
                lines = stdout.split('\n')
                current_package = None
                
                for line in lines:
                    line = line.strip()
                    if line.startswith(('core/', 'extra/', 'community/', 'multilib/', 'testing/')):
                        # Package line
                        parts = line.split(' ', 2)
                        if len(parts) >= 2:
                            name_version = parts[0].split('/')
                            if len(name_version) >= 2:
                                repo = name_version[0]
                                name_ver = name_version[1].split(' ')[0]
                                version = parts[1] if len(parts) > 1 else ""
                                
                                # Check if installed
                                installed = '[installed]' in line
                                
                                current_package = PackageInfo(
                                    name=name_ver,
                                    version=version,
                                    description="",
                                    repository=repo,
                                    installed=installed,
                                    size="",
                                    dependencies=[],
                                    maintainer="",
                                    url=""
                                )
                                packages.append(current_package)
                    
                    elif line and current_package and not line.startswith(('core/', 'extra/', 'community/', 'multilib/', 'testing/')):
                        # Description line
                        current_package.description = line.strip()
            
            return packages
            
        except Exception as e:
            logger.error(f"Error searching packages: {e}")
            return []
    
    async def _search_aur(self, query: str, aur_helper: Optional[str] = None) -> List[PackageInfo]:
        """Search for packages in AUR."""
        try:
            helper = await self._get_aur_helper(aur_helper)
            if not helper:
                return []
            
            cmd = [helper, "-Ss", query]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            packages = []
            if returncode == 0:
                # Parse AUR helper output (similar to pacman but from AUR)
                lines = stdout.split('\n')
                current_package = None
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('aur/'):
                        # AUR package line
                        parts = line.split(' ', 2)
                        if len(parts) >= 2:
                            name_ver = parts[0].split('/')[-1]
                            version = parts[1] if len(parts) > 1 else ""
                            
                            current_package = PackageInfo(
                                name=name_ver,
                                version=version,
                                description="",
                                repository="aur",
                                installed=False,  # TODO: Check if AUR package is installed
                                size="",
                                dependencies=[],
                                maintainer="",
                                url=""
                            )
                            packages.append(current_package)
                    
                    elif line and current_package and not line.startswith('aur/'):
                        current_package.description = line.strip()
            
            return packages
            
        except Exception as e:
            logger.error(f"Error searching AUR: {e}")
            return []
    
    async def _get_package_info(self, package_name: str) -> Optional[PackageInfo]:
        """Get detailed information about a package."""
        try:
            cmd = ["pacman", "-Si", package_name]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode != 0:
                # Try installed packages
                cmd = ["pacman", "-Qi", package_name]
                returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                info = {}
                for line in stdout.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        info[key.strip()] = value.strip()
                
                return PackageInfo(
                    name=info.get("Name", package_name),
                    version=info.get("Version", ""),
                    description=info.get("Description", ""),
                    repository=info.get("Repository", ""),
                    installed=returncode == 0 and "Installed Size" in info,
                    size=info.get("Installed Size", info.get("Download Size", "")),
                    dependencies=info.get("Depends On", "").split() if info.get("Depends On") != "None" else [],
                    maintainer=info.get("Packager", ""),
                    url=info.get("URL", "")
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting package info: {e}")
            return None
    
    async def _install_packages(self, packages: List[str], force: bool = False) -> bool:
        """Install packages using pacman."""
        try:
            cmd = ["pacman", "-S", "--noconfirm"]
            if force:
                cmd.append("--overwrite")
                cmd.append("*")
            cmd.extend(packages)
            
            returncode, stdout, stderr = await self._run_command(cmd, require_sudo=True)
            return returncode == 0
            
        except Exception as e:
            logger.error(f"Error installing packages: {e}")
            return False
    
    async def _install_aur_packages(self, packages: List[str], aur_helper: Optional[str] = None) -> bool:
        """Install packages from AUR."""
        try:
            helper = await self._get_aur_helper(aur_helper)
            if not helper:
                return False
            
            cmd = [helper, "-S", "--noconfirm"]
            cmd.extend(packages)
            
            returncode, stdout, stderr = await self._run_command(cmd)
            return returncode == 0
            
        except Exception as e:
            logger.error(f"Error installing AUR packages: {e}")
            return False
    
    async def _remove_packages(self, packages: List[str], remove_deps: bool = True) -> bool:
        """Remove packages."""
        try:
            cmd = ["pacman", "-R", "--noconfirm"]
            if remove_deps:
                cmd[1] = "-Rs"  # Remove with dependencies
            cmd.extend(packages)
            
            returncode, stdout, stderr = await self._run_command(cmd, require_sudo=True)
            return returncode == 0
            
        except Exception as e:
            logger.error(f"Error removing packages: {e}")
            return False
    
    async def _update_system(self) -> Tuple[bool, str]:
        """Update the package database and upgrade system."""
        try:
            # Update database
            returncode, stdout, stderr = await self._run_command(
                ["pacman", "-Sy", "--noconfirm"], require_sudo=True
            )
            
            if returncode != 0:
                return False, f"Failed to update database: {stderr}"
            
            # Upgrade system
            returncode, stdout, stderr = await self._run_command(
                ["pacman", "-Su", "--noconfirm"], require_sudo=True
            )
            
            return returncode == 0, stdout + stderr
            
        except Exception as e:
            logger.error(f"Error updating system: {e}")
            return False, str(e)
    
    async def _list_installed_packages(self) -> List[PackageInfo]:
        """List all installed packages."""
        try:
            cmd = ["pacman", "-Q"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            packages = []
            if returncode == 0:
                for line in stdout.split('\n'):
                    if line.strip():
                        parts = line.strip().split(' ', 1)
                        if len(parts) >= 2:
                            packages.append(PackageInfo(
                                name=parts[0],
                                version=parts[1],
                                description="",
                                repository="",
                                installed=True,
                                size="",
                                dependencies=[],
                                maintainer="",
                                url=""
                            ))
            
            return packages
            
        except Exception as e:
            logger.error(f"Error listing installed packages: {e}")
            return []
    
    async def _check_updates(self) -> List[str]:
        """Check for available updates."""
        try:
            cmd = ["pacman", "-Qu"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            updates = []
            if returncode == 0:
                for line in stdout.split('\n'):
                    if line.strip():
                        updates.append(line.strip())
            
            return updates
            
        except Exception as e:
            logger.error(f"Error checking updates: {e}")
            return []
    
    async def _clean_cache(self) -> bool:
        """Clean package cache."""
        try:
            cmd = ["pacman", "-Sc", "--noconfirm"]
            returncode, stdout, stderr = await self._run_command(cmd, require_sudo=True)
            return returncode == 0
            
        except Exception as e:
            logger.error(f"Error cleaning cache: {e}")
            return False
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute package management action."""
        action = parameters.get("action")
        package_name = parameters.get("package_name")
        packages_json = parameters.get("packages")
        confirm = parameters.get("confirm", False)
        force = parameters.get("force", False)
        query = parameters.get("query", "")
        repository = parameters.get("repository")
        aur_helper = parameters.get("aur_helper")
        
        # Parse packages list if provided
        packages = []
        if packages_json:
            try:
                packages = json.loads(packages_json)
            except json.JSONDecodeError:
                packages = [packages_json]  # Single package as string
        elif package_name:
            packages = [package_name]
        
        try:
            if action == "search":
                if not query:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="query parameter is required for search"
                    )
                
                search_results = await self._search_packages(query, repository)
                return ToolResponse(
                    success=True,
                    result={
                        "action": "search",
                        "query": query,
                        "packages": [
                            {
                                "name": p.name,
                                "version": p.version,
                                "description": p.description,
                                "repository": p.repository,
                                "installed": p.installed
                            }
                            for p in search_results
                        ]
                    }
                )
            
            elif action == "search_aur":
                if not query:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="query parameter is required for AUR search"
                    )
                
                aur_results = await self._search_aur(query, aur_helper)
                return ToolResponse(
                    success=True,
                    result={
                        "action": "search_aur",
                        "query": query,
                        "packages": [
                            {
                                "name": p.name,
                                "version": p.version,
                                "description": p.description,
                                "repository": p.repository
                            }
                            for p in aur_results
                        ]
                    }
                )
            
            elif action == "info":
                if not package_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="package_name parameter is required"
                    )
                
                package_info = await self._get_package_info(package_name)
                if package_info:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": "info",
                            "package": {
                                "name": package_info.name,
                                "version": package_info.version,
                                "description": package_info.description,
                                "repository": package_info.repository,
                                "installed": package_info.installed,
                                "size": package_info.size,
                                "dependencies": package_info.dependencies,
                                "maintainer": package_info.maintainer,
                                "url": package_info.url
                            }
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error=f"Package '{package_name}' not found"
                    )
            
            elif action == "install":
                if not packages:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="package_name or packages parameter is required"
                    )
                
                if not confirm:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Installation requires confirmation. Set 'confirm' parameter to true."
                    )
                
                success = await self._install_packages(packages, force)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "install",
                        "packages": packages,
                        "installed": success
                    } if success else None,
                    error="Failed to install packages" if not success else None
                )
            
            elif action == "install_aur":
                if not packages:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="package_name or packages parameter is required"
                    )
                
                if not confirm:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="AUR installation requires confirmation. Set 'confirm' parameter to true."
                    )
                
                success = await self._install_aur_packages(packages, aur_helper)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "install_aur",
                        "packages": packages,
                        "installed": success
                    } if success else None,
                    error="Failed to install AUR packages" if not success else None
                )
            
            elif action == "remove":
                if not packages:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="package_name or packages parameter is required"
                    )
                
                if not confirm:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Package removal requires confirmation. Set 'confirm' parameter to true."
                    )
                
                success = await self._remove_packages(packages)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "remove",
                        "packages": packages,
                        "removed": success
                    } if success else None,
                    error="Failed to remove packages" if not success else None
                )
            
            elif action == "update":
                success, output = await self._update_system()
                return ToolResponse(
                    success=success,
                    result={
                        "action": "update",
                        "output": output
                    } if success else None,
                    error=f"Update failed: {output}" if not success else None
                )
            
            elif action == "list_installed":
                installed_packages = await self._list_installed_packages()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "list_installed",
                        "count": len(installed_packages),
                        "packages": [
                            {
                                "name": p.name,
                                "version": p.version
                            }
                            for p in installed_packages
                        ]
                    }
                )
            
            elif action == "check_updates":
                updates = await self._check_updates()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "check_updates",
                        "available_updates": len(updates),
                        "updates": updates
                    }
                )
            
            elif action == "clean_cache":
                success = await self._clean_cache()
                return ToolResponse(
                    success=success,
                    result={
                        "action": "clean_cache",
                        "cleaned": success
                    } if success else None,
                    error="Failed to clean cache" if not success else None
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
                error=f"Package manager error: {e}"
            )
