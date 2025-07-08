"""
System control tool for GNOME AI Assistant.

This module provides functionality to control system services,
power management, and other system-level operations.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolParameter, ToolResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ServiceInfo:
    """Information about a system service."""
    name: str
    state: str
    enabled: bool
    description: str


class SystemControlTool(BaseTool):
    """Tool for system control operations."""
    
    def __init__(self):
        super().__init__(
            name="system_control",
            description="Control system services, power management, and system information",
            parameters=[
                ToolParameter(
                    name="action",
                    description="System control action",
                    type="string",
                    required=True,
                    enum=[
                        "service_status", "service_start", "service_stop",
                        "service_restart", "service_enable", "service_disable",
                        "list_services", "system_info", "disk_usage",
                        "memory_info", "cpu_info", "network_info",
                        "shutdown", "restart", "suspend", "hibernate",
                        "lock_screen", "logout"
                    ]
                ),
                ToolParameter(
                    name="service_name",
                    description="Name of the service",
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
                    name="delay",
                    description="Delay in minutes for shutdown/restart",
                    type="integer",
                    required=False
                )
            ]
        )
    
    async def _run_command(self, cmd: List[str], require_root: bool = False) -> tuple[int, str, str]:
        """Run a system command."""
        try:
            if require_root and cmd[0] in ["systemctl", "shutdown", "reboot"]:
                # Check if we need sudo for certain operations
                if len(cmd) > 1 and cmd[1] in ["start", "stop", "restart", "enable", "disable"]:
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
    
    async def _get_service_info(self, service_name: str) -> Optional[ServiceInfo]:
        """Get information about a service."""
        try:
            # Get service status
            cmd = ["systemctl", "status", service_name]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            state = "unknown"
            enabled = False
            description = ""
            
            if returncode == 0 or "loaded" in stdout:
                lines = stdout.split('\n')
                for line in lines:
                    line = line.strip()
                    if "Active:" in line:
                        if "active (running)" in line:
                            state = "running"
                        elif "inactive (dead)" in line:
                            state = "stopped"
                        elif "failed" in line:
                            state = "failed"
                    elif "Loaded:" in line:
                        if "enabled" in line:
                            enabled = True
                        # Extract description
                        if ";" in line:
                            desc_part = line.split(";")[-1].strip()
                            if desc_part:
                                description = desc_part
            
            return ServiceInfo(
                name=service_name,
                state=state,
                enabled=enabled,
                description=description
            )
            
        except Exception as e:
            logger.error(f"Error getting service info for {service_name}: {e}")
            return None
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        info = {}
        
        try:
            # Get OS info
            cmd = ["uname", "-a"]
            returncode, stdout, stderr = await self._run_command(cmd)
            if returncode == 0:
                info["kernel"] = stdout.strip()
            
            # Get distribution info
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    os_info = {}
                    for line in f:
                        if "=" in line:
                            key, value = line.strip().split("=", 1)
                            os_info[key] = value.strip('"')
                    info["distribution"] = os_info
            
            # Get uptime
            cmd = ["uptime", "-p"]
            returncode, stdout, stderr = await self._run_command(cmd)
            if returncode == 0:
                info["uptime"] = stdout.strip()
            
            # Get load average
            cmd = ["uptime"]
            returncode, stdout, stderr = await self._run_command(cmd)
            if returncode == 0:
                if "load average:" in stdout:
                    load_part = stdout.split("load average:")[-1].strip()
                    info["load_average"] = load_part
            
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
        
        return info
    
    async def _get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information."""
        try:
            cmd = ["df", "-h"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                lines = stdout.strip().split('\n')[1:]  # Skip header
                filesystems = []
                
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 6:
                        filesystems.append({
                            "filesystem": parts[0],
                            "size": parts[1],
                            "used": parts[2],
                            "available": parts[3],
                            "use_percent": parts[4],
                            "mounted_on": parts[5]
                        })
                
                return {"filesystems": filesystems}
            
        except Exception as e:
            logger.error(f"Error getting disk usage: {e}")
        
        return {}
    
    async def _get_memory_info(self) -> Dict[str, Any]:
        """Get memory information."""
        try:
            cmd = ["free", "-h"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                lines = stdout.strip().split('\n')
                memory_info = {}
                
                for line in lines:
                    if line.startswith("Mem:"):
                        parts = line.split()
                        if len(parts) >= 7:
                            memory_info["memory"] = {
                                "total": parts[1],
                                "used": parts[2],
                                "free": parts[3],
                                "shared": parts[4],
                                "buff_cache": parts[5],
                                "available": parts[6]
                            }
                    elif line.startswith("Swap:"):
                        parts = line.split()
                        if len(parts) >= 4:
                            memory_info["swap"] = {
                                "total": parts[1],
                                "used": parts[2],
                                "free": parts[3]
                            }
                
                return memory_info
            
        except Exception as e:
            logger.error(f"Error getting memory info: {e}")
        
        return {}
    
    async def _get_cpu_info(self) -> Dict[str, Any]:
        """Get CPU information."""
        try:
            cpu_info = {}
            
            # Get CPU model and info from /proc/cpuinfo
            if os.path.exists("/proc/cpuinfo"):
                with open("/proc/cpuinfo", "r") as f:
                    cpuinfo = f.read()
                    
                    for line in cpuinfo.split('\n'):
                        if line.startswith("model name"):
                            cpu_info["model"] = line.split(":", 1)[1].strip()
                            break
                    
                    # Count cores
                    core_count = cpuinfo.count("processor")
                    cpu_info["cores"] = core_count
            
            # Get current CPU usage
            cmd = ["top", "-bn1"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                for line in stdout.split('\n'):
                    if "%Cpu(s):" in line:
                        # Parse CPU usage line
                        parts = line.split(",")
                        for part in parts:
                            part = part.strip()
                            if "us" in part:
                                cpu_info["user_percent"] = part.split()[0]
                            elif "sy" in part:
                                cpu_info["system_percent"] = part.split()[0]
                            elif "id" in part:
                                cpu_info["idle_percent"] = part.split()[0]
                        break
            
            return cpu_info
            
        except Exception as e:
            logger.error(f"Error getting CPU info: {e}")
            return {}
    
    async def _get_network_info(self) -> Dict[str, Any]:
        """Get network information."""
        try:
            network_info = {}
            
            # Get network interfaces
            cmd = ["ip", "addr", "show"]
            returncode, stdout, stderr = await self._run_command(cmd)
            
            if returncode == 0:
                interfaces = []
                current_interface = None
                
                for line in stdout.split('\n'):
                    line = line.strip()
                    if line and line[0].isdigit() and ":" in line:
                        # Interface line
                        parts = line.split(":", 2)
                        if len(parts) >= 2:
                            if_name = parts[1].strip().split()[0]
                            current_interface = {"name": if_name, "addresses": []}
                            interfaces.append(current_interface)
                    elif "inet " in line and current_interface:
                        # IPv4 address
                        parts = line.split()
                        if len(parts) >= 2:
                            current_interface["addresses"].append({
                                "type": "IPv4",
                                "address": parts[1]
                            })
                    elif "inet6 " in line and current_interface:
                        # IPv6 address
                        parts = line.split()
                        if len(parts) >= 2:
                            current_interface["addresses"].append({
                                "type": "IPv6",
                                "address": parts[1]
                            })
                
                network_info["interfaces"] = interfaces
            
            return network_info
            
        except Exception as e:
            logger.error(f"Error getting network info: {e}")
            return {}
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute system control action."""
        action = parameters.get("action")
        service_name = parameters.get("service_name", "")
        confirm = parameters.get("confirm", False)
        delay = parameters.get("delay", 0)
        
        try:
            if action == "service_status":
                if not service_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Service name is required"
                    )
                
                service_info = await self._get_service_info(service_name)
                if service_info:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": "service_status",
                            "service": {
                                "name": service_info.name,
                                "state": service_info.state,
                                "enabled": service_info.enabled,
                                "description": service_info.description
                            }
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error=f"Could not get status for service: {service_name}"
                    )
            
            elif action in ["service_start", "service_stop", "service_restart"]:
                if not service_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Service name is required"
                    )
                
                operation = action.split("_")[1]  # start, stop, restart
                cmd = ["systemctl", operation, service_name]
                
                returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
                
                if returncode == 0:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": action,
                            "service": service_name,
                            "message": f"Service {operation} completed successfully"
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error=f"Failed to {operation} service: {stderr}"
                    )
            
            elif action in ["service_enable", "service_disable"]:
                if not service_name:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Service name is required"
                    )
                
                operation = action.split("_")[1]  # enable, disable
                cmd = ["systemctl", operation, service_name]
                
                returncode, stdout, stderr = await self._run_command(cmd, require_root=True)
                
                if returncode == 0:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": action,
                            "service": service_name,
                            "message": f"Service {operation}d successfully"
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error=f"Failed to {operation} service: {stderr}"
                    )
            
            elif action == "list_services":
                cmd = ["systemctl", "list-units", "--type=service", "--no-pager"]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    services = []
                    lines = stdout.split('\n')[1:]  # Skip header
                    
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 4 and parts[0].endswith('.service'):
                            services.append({
                                "name": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": ' '.join(parts[4:]) if len(parts) > 4 else ""
                            })
                    
                    return ToolResponse(
                        success=True,
                        result={
                            "action": "list_services",
                            "services": services
                        }
                    )
            
            elif action == "system_info":
                info = await self._get_system_info()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "system_info",
                        "info": info
                    }
                )
            
            elif action == "disk_usage":
                usage = await self._get_disk_usage()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "disk_usage",
                        **usage
                    }
                )
            
            elif action == "memory_info":
                memory = await self._get_memory_info()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "memory_info",
                        **memory
                    }
                )
            
            elif action == "cpu_info":
                cpu = await self._get_cpu_info()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "cpu_info",
                        "cpu": cpu
                    }
                )
            
            elif action == "network_info":
                network = await self._get_network_info()
                return ToolResponse(
                    success=True,
                    result={
                        "action": "network_info",
                        **network
                    }
                )
            
            elif action in ["shutdown", "restart"]:
                if not confirm:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error=f"Confirmation required for {action}. Set 'confirm' parameter to true."
                    )
                
                cmd = ["sudo"]
                if action == "shutdown":
                    cmd.extend(["shutdown", "-h"])
                else:  # restart
                    cmd.extend(["shutdown", "-r"])
                
                if delay > 0:
                    cmd.append(f"+{delay}")
                else:
                    cmd.append("now")
                
                returncode, stdout, stderr = await self._run_command(cmd)
                
                return ToolResponse(
                    success=returncode == 0,
                    result={
                        "action": action,
                        "message": f"System {action} initiated"
                    } if returncode == 0 else None,
                    error=stderr if returncode != 0 else None
                )
            
            elif action in ["suspend", "hibernate"]:
                cmd = ["systemctl", action]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                return ToolResponse(
                    success=returncode == 0,
                    result={
                        "action": action,
                        "message": f"System {action} initiated"
                    } if returncode == 0 else None,
                    error=stderr if returncode != 0 else None
                )
            
            elif action == "lock_screen":
                # Try different lock screen commands
                commands = [
                    ["gnome-screensaver-command", "-l"],
                    ["loginctl", "lock-session"],
                    ["dm-tool", "lock"]
                ]
                
                for cmd in commands:
                    returncode, stdout, stderr = await self._run_command(cmd)
                    if returncode == 0:
                        return ToolResponse(
                            success=True,
                            result={
                                "action": "lock_screen",
                                "message": "Screen locked successfully"
                            }
                        )
                
                return ToolResponse(
                    success=False,
                    result=None,
                    error="Failed to lock screen with any available method"
                )
            
            elif action == "logout":
                # Try GNOME logout
                cmd = ["gnome-session-quit", "--logout", "--no-prompt"]
                returncode, stdout, stderr = await self._run_command(cmd)
                
                if returncode == 0:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": "logout",
                            "message": "Logout initiated"
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Failed to initiate logout"
                    )
            
            else:
                return ToolResponse(
                    success=False,
                    result=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Error executing system control action {action}: {e}")
            return ToolResponse(
                success=False,
                result=None,
                error=f"Failed to execute action: {str(e)}"
            )
