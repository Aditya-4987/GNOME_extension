"""Network and internet control tool for the AI assistant."""

import asyncio
import subprocess
import json
import socket
import ipaddress
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolResponse, ToolParameter
from ..core.permissions import RiskLevel
from ..utils.logger import get_logger

logger = get_logger(__name__)


class NetworkTool(BaseTool):
    """Tool for network diagnostics, monitoring, and basic control."""
    
    def __init__(self):
        super().__init__()
        self.name = "network"
        self.description = "Network diagnostics, connectivity checks, and basic network control"
        self.category = "system"
        self.risk_level = RiskLevel.MEDIUM
        self.required_permissions = ["network_access", "system_info"]
        
        # Define parameters
        self.parameters = [
            ToolParameter(
                name="action",
                type="string",
                description="Network action to perform",
                required=True,
                enum_values=[
                    "ping", "traceroute", "port_scan", "get_interfaces",
                    "get_connections", "dns_lookup", "speed_test",
                    "wifi_scan", "wifi_connect", "get_public_ip",
                    "check_connectivity", "network_stats"
                ]
            ),
            ToolParameter(
                name="target",
                type="string",
                description="Target host, IP, or domain for network operations",
                required=False
            ),
            ToolParameter(
                name="port",
                type="integer",
                description="Port number for port-specific operations",
                required=False
            ),
            ToolParameter(
                name="count",
                type="integer", 
                description="Number of packets/attempts (for ping, etc.)",
                required=False,
                default=4
            ),
            ToolParameter(
                name="timeout",
                type="integer",
                description="Timeout in seconds",
                required=False,
                default=5
            ),
            ToolParameter(
                name="interface",
                type="string",
                description="Network interface name",
                required=False
            ),
            ToolParameter(
                name="ssid",
                type="string",
                description="WiFi network SSID",
                required=False
            ),
            ToolParameter(
                name="password",
                type="string",
                description="WiFi network password",
                required=False
            )
        ]
    
    async def execute(self, action: str, target: str = None, port: int = None,
                     count: int = 4, timeout: int = 5, interface: str = None,
                     ssid: str = None, password: str = None, **kwargs) -> ToolResponse:
        """
        Execute network operation.
        
        Args:
            action: Network action to perform
            target: Target host/IP/domain
            port: Port number
            count: Number of packets/attempts
            timeout: Operation timeout
            interface: Network interface
            ssid: WiFi SSID
            password: WiFi password
            
        Returns:
            Tool execution result
        """
        try:
            if action == "ping":
                return await self._ping(target, count, timeout)
            elif action == "traceroute":
                return await self._traceroute(target)
            elif action == "port_scan":
                return await self._port_scan(target, port)
            elif action == "get_interfaces":
                return await self._get_interfaces()
            elif action == "get_connections":
                return await self._get_connections()
            elif action == "dns_lookup":
                return await self._dns_lookup(target)
            elif action == "speed_test":
                return await self._speed_test()
            elif action == "wifi_scan":
                return await self._wifi_scan(interface)
            elif action == "wifi_connect":
                return await self._wifi_connect(ssid, password)
            elif action == "get_public_ip":
                return await self._get_public_ip()
            elif action == "check_connectivity":
                return await self._check_connectivity()
            elif action == "network_stats":
                return await self._network_stats(interface)
            else:
                return ToolResponse(
                    success=False,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Network tool error: {e}")
            return ToolResponse(
                success=False,
                error=f"Network operation failed: {str(e)}"
            )
    
    async def _ping(self, target: str, count: int, timeout: int) -> ToolResponse:
        """Ping a host."""
        if not target:
            return ToolResponse(success=False, error="Target is required for ping")
        
        try:
            cmd = ["ping", "-c", str(count), "-W", str(timeout), target]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                
                # Parse ping statistics
                lines = output.strip().split('\n')
                stats_line = next((line for line in lines if "packet loss" in line), "")
                rtt_line = next((line for line in lines if "min/avg/max" in line), "")
                
                result = {
                    "target": target,
                    "packets_sent": count,
                    "success": True,
                    "output": output,
                    "packet_loss": stats_line,
                    "rtt_stats": rtt_line
                }
                
                return ToolResponse(
                    success=True,
                    result=f"Ping to {target} successful",
                    metadata=result
                )
            else:
                error_output = stderr.decode() or stdout.decode()
                return ToolResponse(
                    success=False,
                    error=f"Ping failed: {error_output}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"Ping failed: {str(e)}")
    
    async def _traceroute(self, target: str) -> ToolResponse:
        """Trace route to a host."""
        if not target:
            return ToolResponse(success=False, error="Target is required for traceroute")
        
        try:
            # Try traceroute first, fallback to tracepath
            for cmd_name in ["traceroute", "tracepath"]:
                try:
                    cmd = [cmd_name, target]
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await asyncio.wait_for(
                        process.communicate(), timeout=30
                    )
                    
                    if process.returncode == 0:
                        output = stdout.decode()
                        return ToolResponse(
                            success=True,
                            result=f"Traceroute to {target} completed",
                            metadata={
                                "target": target,
                                "output": output,
                                "tool_used": cmd_name
                            }
                        )
                    
                except FileNotFoundError:
                    continue
                except asyncio.TimeoutError:
                    return ToolResponse(
                        success=False,
                        error="Traceroute timed out"
                    )
            
            return ToolResponse(
                success=False,
                error="Traceroute tools not available"
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Traceroute failed: {str(e)}")
    
    async def _port_scan(self, target: str, port: int = None) -> ToolResponse:
        """Basic port connectivity check."""
        if not target:
            return ToolResponse(success=False, error="Target is required for port scan")
        
        try:
            # If no port specified, check common ports
            if port is None:
                common_ports = [22, 23, 25, 53, 80, 110, 143, 443, 993, 995]
            else:
                common_ports = [port]
            
            results = []
            
            for p in common_ports:
                try:
                    # Use asyncio to test port connectivity
                    _, writer = await asyncio.wait_for(
                        asyncio.open_connection(target, p),
                        timeout=2
                    )
                    writer.close()
                    await writer.wait_closed()
                    
                    results.append({"port": p, "status": "open"})
                    
                except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                    results.append({"port": p, "status": "closed"})
            
            open_ports = [r for r in results if r["status"] == "open"]
            
            return ToolResponse(
                success=True,
                result=f"Port scan of {target} completed. Found {len(open_ports)} open ports",
                metadata={
                    "target": target,
                    "results": results,
                    "open_ports": open_ports
                }
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Port scan failed: {str(e)}")
    
    async def _get_interfaces(self) -> ToolResponse:
        """Get network interfaces."""
        try:
            cmd = ["ip", "addr", "show"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                
                # Parse interface information
                interfaces = []
                current_interface = None
                
                for line in output.split('\n'):
                    if line and not line.startswith(' '):
                        # New interface
                        parts = line.split(':')
                        if len(parts) >= 2:
                            current_interface = {
                                "name": parts[1].strip(),
                                "state": "UP" if "UP" in line else "DOWN",
                                "addresses": []
                            }
                            interfaces.append(current_interface)
                    elif "inet " in line and current_interface:
                        # IP address
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            current_interface["addresses"].append(parts[1])
                
                return ToolResponse(
                    success=True,
                    result=f"Found {len(interfaces)} network interfaces",
                    metadata={"interfaces": interfaces}
                )
            else:
                return ToolResponse(
                    success=False,
                    error=f"Failed to get interfaces: {stderr.decode()}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get interfaces: {str(e)}")
    
    async def _get_connections(self) -> ToolResponse:
        """Get active network connections."""
        try:
            cmd = ["netstat", "-tuln"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                lines = output.strip().split('\n')[2:]  # Skip headers
                
                connections = []
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 4:
                        connections.append({
                            "protocol": parts[0],
                            "local_address": parts[3],
                            "state": parts[5] if len(parts) > 5 else "LISTEN"
                        })
                
                return ToolResponse(
                    success=True,
                    result=f"Found {len(connections)} active connections",
                    metadata={"connections": connections}
                )
            else:
                return ToolResponse(
                    success=False,
                    error=f"Failed to get connections: {stderr.decode()}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get connections: {str(e)}")
    
    async def _dns_lookup(self, target: str) -> ToolResponse:
        """Perform DNS lookup."""
        if not target:
            return ToolResponse(success=False, error="Target is required for DNS lookup")
        
        try:
            # Use socket.getaddrinfo for DNS resolution
            result = socket.getaddrinfo(target, None)
            
            addresses = []
            for family, type_, proto, canonname, sockaddr in result:
                if family == socket.AF_INET:  # IPv4
                    addresses.append({"type": "IPv4", "address": sockaddr[0]})
                elif family == socket.AF_INET6:  # IPv6
                    addresses.append({"type": "IPv6", "address": sockaddr[0]})
            
            # Remove duplicates
            unique_addresses = []
            seen = set()
            for addr in addresses:
                key = (addr["type"], addr["address"])
                if key not in seen:
                    unique_addresses.append(addr)
                    seen.add(key)
            
            return ToolResponse(
                success=True,
                result=f"DNS lookup for {target} found {len(unique_addresses)} addresses",
                metadata={
                    "target": target,
                    "addresses": unique_addresses
                }
            )
            
        except socket.gaierror as e:
            return ToolResponse(
                success=False,
                error=f"DNS lookup failed: {str(e)}"
            )
        except Exception as e:
            return ToolResponse(success=False, error=f"DNS lookup failed: {str(e)}")
    
    async def _speed_test(self) -> ToolResponse:
        """Basic network speed test."""
        try:
            # Simple speed test using curl to download a test file
            test_url = "http://speedtest.ftp.otenet.gr/files/test1Mb.db"
            
            cmd = ["curl", "-o", "/dev/null", "-s", "-w", "%{speed_download},%{time_total}", test_url]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=30
            )
            
            if process.returncode == 0:
                output = stdout.decode().strip()
                if ',' in output:
                    speed_bytes, time_total = output.split(',')
                    speed_mbps = float(speed_bytes) * 8 / 1024 / 1024  # Convert to Mbps
                    
                    return ToolResponse(
                        success=True,
                        result=f"Download speed: {speed_mbps:.2f} Mbps",
                        metadata={
                            "speed_mbps": speed_mbps,
                            "time_seconds": float(time_total),
                            "test_file_size": "1MB"
                        }
                    )
            
            return ToolResponse(
                success=False,
                error="Speed test failed"
            )
            
        except asyncio.TimeoutError:
            return ToolResponse(success=False, error="Speed test timed out")
        except Exception as e:
            return ToolResponse(success=False, error=f"Speed test failed: {str(e)}")
    
    async def _wifi_scan(self, interface: str = None) -> ToolResponse:
        """Scan for WiFi networks."""
        try:
            # Use nmcli to scan for WiFi networks
            cmd = ["nmcli", "dev", "wifi", "list"]
            if interface:
                cmd.extend(["--device", interface])
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                lines = output.strip().split('\n')[1:]  # Skip header
                
                networks = []
                for line in lines:
                    if line.strip():
                        # Parse nmcli output (simplified)
                        parts = line.split()
                        if len(parts) >= 6:
                            networks.append({
                                "ssid": parts[1] if parts[1] != '--' else "Hidden",
                                "signal": parts[6],
                                "security": parts[5]
                            })
                
                return ToolResponse(
                    success=True,
                    result=f"Found {len(networks)} WiFi networks",
                    metadata={"networks": networks}
                )
            else:
                return ToolResponse(
                    success=False,
                    error=f"WiFi scan failed: {stderr.decode()}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"WiFi scan failed: {str(e)}")
    
    async def _wifi_connect(self, ssid: str, password: str = None) -> ToolResponse:
        """Connect to WiFi network."""
        if not ssid:
            return ToolResponse(success=False, error="SSID is required")
        
        try:
            # Use nmcli to connect to WiFi
            if password:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
            else:
                cmd = ["nmcli", "dev", "wifi", "connect", ssid]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return ToolResponse(
                    success=True,
                    result=f"Connected to WiFi network: {ssid}"
                )
            else:
                error_msg = stderr.decode() or stdout.decode()
                return ToolResponse(
                    success=False,
                    error=f"WiFi connection failed: {error_msg}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"WiFi connection failed: {str(e)}")
    
    async def _get_public_ip(self) -> ToolResponse:
        """Get public IP address."""
        try:
            # Use multiple services for reliability
            services = [
                "https://ipv4.icanhazip.com",
                "https://api.ipify.org",
                "https://checkip.amazonaws.com"
            ]
            
            for service in services:
                try:
                    cmd = ["curl", "-s", "--max-time", "5", service]
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        ip = stdout.decode().strip()
                        if ip:
                            return ToolResponse(
                                success=True,
                                result=f"Public IP: {ip}",
                                metadata={"public_ip": ip, "service": service}
                            )
                            
                except Exception:
                    continue
            
            return ToolResponse(
                success=False,
                error="Could not determine public IP"
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get public IP: {str(e)}")
    
    async def _check_connectivity(self) -> ToolResponse:
        """Check internet connectivity."""
        try:
            # Check connectivity to multiple reliable hosts
            hosts = ["8.8.8.8", "1.1.1.1", "google.com"]
            
            results = []
            for host in hosts:
                try:
                    cmd = ["ping", "-c", "1", "-W", "3", host]
                    
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    results.append({
                        "host": host,
                        "reachable": process.returncode == 0
                    })
                    
                except Exception:
                    results.append({
                        "host": host,
                        "reachable": False
                    })
            
            reachable_count = sum(1 for r in results if r["reachable"])
            
            connectivity_status = "good" if reachable_count >= 2 else \
                                "limited" if reachable_count == 1 else "none"
            
            return ToolResponse(
                success=True,
                result=f"Internet connectivity: {connectivity_status}",
                metadata={
                    "status": connectivity_status,
                    "results": results,
                    "reachable_hosts": reachable_count
                }
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Connectivity check failed: {str(e)}")
    
    async def _network_stats(self, interface: str = None) -> ToolResponse:
        """Get network statistics."""
        try:
            if interface:
                cmd = ["cat", f"/sys/class/net/{interface}/statistics/rx_bytes",
                       f"/sys/class/net/{interface}/statistics/tx_bytes"]
            else:
                cmd = ["cat", "/proc/net/dev"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                output = stdout.decode()
                
                if interface:
                    lines = output.strip().split('\n')
                    if len(lines) >= 2:
                        rx_bytes = int(lines[0])
                        tx_bytes = int(lines[1])
                        
                        return ToolResponse(
                            success=True,
                            result=f"Network stats for {interface}",
                            metadata={
                                "interface": interface,
                                "rx_bytes": rx_bytes,
                                "tx_bytes": tx_bytes,
                                "rx_mb": rx_bytes / 1024 / 1024,
                                "tx_mb": tx_bytes / 1024 / 1024
                            }
                        )
                else:
                    # Parse /proc/net/dev output
                    lines = output.strip().split('\n')[2:]  # Skip headers
                    interfaces = []
                    
                    for line in lines:
                        parts = line.split()
                        if len(parts) >= 10:
                            interface_name = parts[0].rstrip(':')
                            interfaces.append({
                                "interface": interface_name,
                                "rx_bytes": int(parts[1]),
                                "tx_bytes": int(parts[9])
                            })
                    
                    return ToolResponse(
                        success=True,
                        result=f"Network statistics for {len(interfaces)} interfaces",
                        metadata={"interfaces": interfaces}
                    )
            
            return ToolResponse(
                success=False,
                error="Failed to get network statistics"
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get network stats: {str(e)}")
    
    def get_help(self) -> str:
        """Get help text for the tool."""
        return """
Network Tool

This tool provides network diagnostics, monitoring, and basic control capabilities.

Available actions:
- ping: Ping a host to test connectivity
- traceroute: Trace the route to a host
- port_scan: Check if ports are open on a host
- get_interfaces: List network interfaces
- get_connections: Show active network connections
- dns_lookup: Resolve hostname to IP addresses
- speed_test: Basic internet speed test
- wifi_scan: Scan for available WiFi networks
- wifi_connect: Connect to a WiFi network
- get_public_ip: Get your public IP address
- check_connectivity: Check internet connectivity
- network_stats: Get network interface statistics

Examples:
- Ping Google: {"action": "ping", "target": "google.com"}
- Check port: {"action": "port_scan", "target": "example.com", "port": 80}
- WiFi scan: {"action": "wifi_scan"}
- Speed test: {"action": "speed_test"}
- Get public IP: {"action": "get_public_ip"}
"""
