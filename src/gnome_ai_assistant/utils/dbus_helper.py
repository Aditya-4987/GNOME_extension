"""
DBus helper utilities for GNOME AI Assistant.

This module provides utilities for interacting with DBus services
and monitoring DBus signals for system integration.
"""

import asyncio
import logging
import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Callable, Union
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class DBusType(Enum):
    """DBus bus types."""
    SYSTEM = "system"
    SESSION = "session"


@dataclass
class DBusService:
    """Information about a DBus service."""
    name: str
    bus_type: DBusType
    object_path: str
    interface: str


@dataclass
class DBusSignal:
    """Information about a DBus signal."""
    sender: str
    interface: str
    member: str
    path: str
    signature: str
    body: List[Any]


class DBusHelper:
    """Helper class for DBus operations."""
    
    def __init__(self):
        self._signal_handlers: Dict[str, List[Callable]] = {}
        self._monitoring_tasks: Dict[str, asyncio.Task] = {}
        self._running = False
    
    async def call_method(self, 
                         service_name: str,
                         object_path: str,
                         interface: str,
                         method: str,
                         args: Optional[List[Any]] = None,
                         bus_type: DBusType = DBusType.SESSION) -> Optional[str]:
        """Call a DBus method."""
        try:
            cmd = [
                "dbus-send",
                "--print-reply",
                f"--{bus_type.value}",
                f"--dest={service_name}",
                object_path,
                f"{interface}.{method}"
            ]
            
            # Add arguments
            if args:
                for arg in args:
                    if isinstance(arg, str):
                        cmd.append(f"string:{arg}")
                    elif isinstance(arg, int):
                        cmd.append(f"int32:{arg}")
                    elif isinstance(arg, float):
                        cmd.append(f"double:{arg}")
                    elif isinstance(arg, bool):
                        cmd.append(f"boolean:{str(arg).lower()}")
                    elif isinstance(arg, bytes):
                        cmd.append(f"array:byte:{arg.hex()}")
                    else:
                        # Try to convert to string
                        cmd.append(f"string:{str(arg)}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"DBus method call failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Error calling DBus method {interface}.{method}: {e}")
            return None
    
    async def get_property(self,
                          service_name: str,
                          object_path: str,
                          interface: str,
                          property_name: str,
                          bus_type: DBusType = DBusType.SESSION) -> Optional[str]:
        """Get a DBus property."""
        return await self.call_method(
            service_name,
            object_path,
            "org.freedesktop.DBus.Properties",
            "Get",
            [interface, property_name],
            bus_type
        )
    
    async def set_property(self,
                          service_name: str,
                          object_path: str,
                          interface: str,
                          property_name: str,
                          value: Any,
                          bus_type: DBusType = DBusType.SESSION) -> bool:
        """Set a DBus property."""
        try:
            # Format value based on type
            if isinstance(value, str):
                variant_value = f"string:{value}"
            elif isinstance(value, int):
                variant_value = f"int32:{value}"
            elif isinstance(value, float):
                variant_value = f"double:{value}"
            elif isinstance(value, bool):
                variant_value = f"boolean:{str(value).lower()}"
            else:
                variant_value = f"string:{str(value)}"
            
            result = await self.call_method(
                service_name,
                object_path,
                "org.freedesktop.DBus.Properties",
                "Set",
                [interface, property_name, variant_value],
                bus_type
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error setting DBus property {property_name}: {e}")
            return False
    
    async def introspect(self,
                        service_name: str,
                        object_path: str,
                        bus_type: DBusType = DBusType.SESSION) -> Optional[Dict[str, Any]]:
        """Introspect a DBus object."""
        try:
            result = await self.call_method(
                service_name,
                object_path,
                "org.freedesktop.DBus.Introspectable",
                "Introspect",
                bus_type=bus_type
            )
            
            if result:
                return self._parse_introspection_xml(result)
            
        except Exception as e:
            logger.error(f"Error introspecting {service_name}{object_path}: {e}")
        
        return None
    
    def _parse_introspection_xml(self, xml_data: str) -> Dict[str, Any]:
        """Parse DBus introspection XML."""
        try:
            # Remove the "method return" prefix that dbus-send adds
            xml_start = xml_data.find('<?xml')
            if xml_start != -1:
                xml_data = xml_data[xml_start:]
            else:
                # Look for the start of the actual XML
                xml_start = xml_data.find('<node')
                if xml_start != -1:
                    xml_data = xml_data[xml_start:]
            
            root = ET.fromstring(xml_data)
            
            interfaces = {}
            
            for interface in root.findall('interface'):
                interface_name = interface.get('name')
                if interface_name:
                    interface_info = {
                        'methods': [],
                        'properties': [],
                        'signals': []
                    }
                    
                    # Parse methods
                    for method in interface.findall('method'):
                        method_name = method.get('name')
                        if method_name:
                            method_info = {
                                'name': method_name,
                                'args': []
                            }
                            
                            for arg in method.findall('arg'):
                                arg_info = {
                                    'name': arg.get('name', ''),
                                    'type': arg.get('type', ''),
                                    'direction': arg.get('direction', 'in')
                                }
                                method_info['args'].append(arg_info)
                            
                            interface_info['methods'].append(method_info)
                    
                    # Parse properties
                    for prop in interface.findall('property'):
                        prop_name = prop.get('name')
                        if prop_name:
                            prop_info = {
                                'name': prop_name,
                                'type': prop.get('type', ''),
                                'access': prop.get('access', 'read')
                            }
                            interface_info['properties'].append(prop_info)
                    
                    # Parse signals
                    for signal in interface.findall('signal'):
                        signal_name = signal.get('name')
                        if signal_name:
                            signal_info = {
                                'name': signal_name,
                                'args': []
                            }
                            
                            for arg in signal.findall('arg'):
                                arg_info = {
                                    'name': arg.get('name', ''),
                                    'type': arg.get('type', '')
                                }
                                signal_info['args'].append(arg_info)
                            
                            interface_info['signals'].append(signal_info)
                    
                    interfaces[interface_name] = interface_info
            
            return {
                'interfaces': interfaces,
                'child_nodes': [node.get('name') for node in root.findall('node') if node.get('name')]
            }
            
        except ET.ParseError as e:
            logger.error(f"Error parsing introspection XML: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error processing introspection data: {e}")
            return {}
    
    async def list_services(self, bus_type: DBusType = DBusType.SESSION) -> List[str]:
        """List available DBus services."""
        try:
            result = await self.call_method(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ListNames",
                bus_type=bus_type
            )
            
            if result:
                # Parse the result to extract service names
                services = []
                lines = result.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('string "') and line.endswith('"'):
                        service_name = line[8:-1]  # Remove 'string "' and '"'
                        services.append(service_name)
                
                return services
            
        except Exception as e:
            logger.error(f"Error listing DBus services: {e}")
        
        return []
    
    async def monitor_signals(self,
                             interface: Optional[str] = None,
                             member: Optional[str] = None,
                             path: Optional[str] = None,
                             sender: Optional[str] = None,
                             bus_type: DBusType = DBusType.SESSION) -> str:
        """Start monitoring DBus signals."""
        try:
            monitor_id = f"{interface or 'any'}_{member or 'any'}_{path or 'any'}"
            
            if monitor_id in self._monitoring_tasks:
                logger.warning(f"Already monitoring signals for {monitor_id}")
                return monitor_id
            
            # Build dbus-monitor command
            cmd = ["dbus-monitor", f"--{bus_type.value}"]
            
            # Build match rule
            match_rules = []
            if interface:
                match_rules.append(f"interface='{interface}'")
            if member:
                match_rules.append(f"member='{member}'")
            if path:
                match_rules.append(f"path='{path}'")
            if sender:
                match_rules.append(f"sender='{sender}'")
            
            if match_rules:
                match_rule = ",".join(match_rules)
                cmd.append(f"type='signal',{match_rule}")
            else:
                cmd.append("type='signal'")
            
            # Start monitoring task
            self._monitoring_tasks[monitor_id] = asyncio.create_task(
                self._monitor_signals_task(cmd, monitor_id)
            )
            
            logger.info(f"Started monitoring DBus signals: {monitor_id}")
            return monitor_id
            
        except Exception as e:
            logger.error(f"Error starting signal monitoring: {e}")
            raise
    
    async def _monitor_signals_task(self, cmd: List[str], monitor_id: str):
        """Task for monitoring DBus signals."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                
                line_str = line.decode().strip()
                
                # Parse signal information
                signal = self._parse_signal_line(line_str)
                if signal:
                    await self._handle_signal(monitor_id, signal)
                    
        except asyncio.CancelledError:
            logger.info(f"Signal monitoring stopped: {monitor_id}")
            if process:
                process.terminate()
        except Exception as e:
            logger.error(f"Error in signal monitoring task {monitor_id}: {e}")
        finally:
            if monitor_id in self._monitoring_tasks:
                del self._monitoring_tasks[monitor_id]
    
    def _parse_signal_line(self, line: str) -> Optional[DBusSignal]:
        """Parse a signal line from dbus-monitor output."""
        try:
            # This is a simplified parser for dbus-monitor output
            # Real implementation would need more sophisticated parsing
            
            if "signal" not in line.lower():
                return None
            
            # Extract basic signal information
            # Format: signal time=... sender=... -> destination=... serial=... path=...; interface=...; member=...
            
            parts = line.split(';')
            if len(parts) < 3:
                return None
            
            # Extract path, interface, member
            path = ""
            interface = ""
            member = ""
            sender = ""
            
            for part in parts:
                part = part.strip()
                if part.startswith('path='):
                    path = part[5:]
                elif part.startswith('interface='):
                    interface = part[10:]
                elif part.startswith('member='):
                    member = part[7:]
            
            # Extract sender from the beginning
            if 'sender=' in line:
                sender_start = line.find('sender=') + 7
                sender_end = line.find(' ', sender_start)
                if sender_end != -1:
                    sender = line[sender_start:sender_end]
                else:
                    sender = line[sender_start:]
            
            if interface and member:
                return DBusSignal(
                    sender=sender,
                    interface=interface,
                    member=member,
                    path=path,
                    signature="",  # Would need more parsing
                    body=[]  # Would need more parsing
                )
            
        except Exception as e:
            logger.debug(f"Error parsing signal line: {e}")
        
        return None
    
    async def _handle_signal(self, monitor_id: str, signal: DBusSignal):
        """Handle a received DBus signal."""
        try:
            # Call registered handlers
            handlers = self._signal_handlers.get(monitor_id, [])
            for handler in handlers:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(signal)
                    else:
                        handler(signal)
                except Exception as e:
                    logger.error(f"Error in signal handler: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling signal: {e}")
    
    def add_signal_handler(self, monitor_id: str, handler: Callable[[DBusSignal], None]):
        """Add a signal handler for a specific monitor."""
        if monitor_id not in self._signal_handlers:
            self._signal_handlers[monitor_id] = []
        
        self._signal_handlers[monitor_id].append(handler)
        logger.info(f"Added signal handler for {monitor_id}")
    
    def remove_signal_handler(self, monitor_id: str, handler: Callable[[DBusSignal], None]):
        """Remove a signal handler."""
        if monitor_id in self._signal_handlers:
            try:
                self._signal_handlers[monitor_id].remove(handler)
                logger.info(f"Removed signal handler for {monitor_id}")
            except ValueError:
                logger.warning(f"Handler not found for {monitor_id}")
    
    async def stop_monitoring(self, monitor_id: str):
        """Stop monitoring signals for a specific ID."""
        if monitor_id in self._monitoring_tasks:
            task = self._monitoring_tasks[monitor_id]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            logger.info(f"Stopped monitoring signals: {monitor_id}")
    
    async def stop_all_monitoring(self):
        """Stop all signal monitoring."""
        for monitor_id in list(self._monitoring_tasks.keys()):
            await self.stop_monitoring(monitor_id)
    
    # Common GNOME/DBus service helpers
    
    async def get_gnome_settings(self, schema: str, key: str) -> Optional[str]:
        """Get a GNOME setting value."""
        try:
            process = await asyncio.create_subprocess_exec(
                "gsettings", "get", schema, key,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip().strip("'\"")
            
        except Exception as e:
            logger.error(f"Error getting GNOME setting {schema}.{key}: {e}")
        
        return None
    
    async def set_gnome_settings(self, schema: str, key: str, value: str) -> bool:
        """Set a GNOME setting value."""
        try:
            process = await asyncio.create_subprocess_exec(
                "gsettings", "set", schema, key, value,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            return process.returncode == 0
            
        except Exception as e:
            logger.error(f"Error setting GNOME setting {schema}.{key}: {e}")
            return False
    
    async def show_notification(self, summary: str, body: str = "", 
                              urgency: str = "normal", timeout: int = 5000) -> bool:
        """Show a notification using DBus."""
        try:
            args = [
                "GNOME AI Assistant",  # app_name
                0,  # replaces_id
                "",  # app_icon
                summary,  # summary
                body,  # body
                [],  # actions
                {},  # hints
                timeout  # timeout
            ]
            
            result = await self.call_method(
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.Notifications",
                "Notify",
                args,
                DBusType.SESSION
            )
            
            return result is not None
            
        except Exception as e:
            logger.error(f"Error showing notification: {e}")
            return False

# Convenience function to get a DBus session helper
def get_dbus_session() -> DBusHelper:
    """
    Get a DBus helper instance for session bus operations.
    
    Returns:
        DBusHelper instance configured for session bus
    """
    return DBusHelper()
