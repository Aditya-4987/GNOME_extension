"""
Interfaces module for GNOME AI Assistant.

This module provides various user interfaces including CLI, web interface,
voice interface, and GNOME notifications.
"""

from .notifications import send_permission_notification, NotificationManager
from .cli import CLIInterface
from .web import WebInterface

__all__ = [
    "send_permission_notification",
    "NotificationManager", 
    "CLIInterface",
    "WebInterface",
]
