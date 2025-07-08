"""GNOME notifications interface for permission requests and updates."""

import asyncio
import subprocess
from typing import Optional, Callable, Dict, Any
import json
import logging

from ..utils.logger import get_logger

logger = get_logger("interfaces.notifications")


class NotificationManager:
    """Manages GNOME notifications for the AI assistant."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.active_notifications: Dict[str, str] = {}  # notification_id -> request_id
        self.response_callbacks: Dict[str, Callable] = {}  # request_id -> callback
    
    async def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        timeout: int = 5000,
        actions: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Send a GNOME notification.
        
        Args:
            title: Notification title
            message: Notification message
            urgency: Urgency level (low, normal, critical)
            timeout: Timeout in milliseconds
            actions: Optional action buttons {action_id: label}
            
        Returns:
            Notification ID if successful
        """
        try:
            cmd = [
                "notify-send",
                f"--urgency={urgency}",
                f"--expire-time={timeout}",
                title,
                message
            ]
            
            # Add actions if provided
            if actions:
                for action_id, label in actions.items():
                    cmd.extend([f"--action={action_id}={label}"])
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Generate notification ID (notify-send doesn't return one)
                notification_id = f"notif_{len(self.active_notifications)}"
                logger.info(f"Sent notification: {title}")
                return notification_id
            else:
                logger.error(f"Failed to send notification: {stderr.decode()}")
                return None
        
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return None
    
    async def send_permission_notification(
        self,
        title: str,
        message: str,
        risk_level: str,
        request_id: str,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Send permission request notification with action buttons.
        
        Args:
            title: Notification title
            message: Permission request message
            risk_level: Risk level (low, medium, high, critical)
            request_id: Unique request identifier
            callback: Callback function for response
            
        Returns:
            True if notification sent successfully
        """
        try:
            # Map risk level to urgency
            urgency_map = {
                "low": "normal",
                "medium": "normal", 
                "high": "critical",
                "critical": "critical"
            }
            urgency = urgency_map.get(risk_level, "normal")
            
            # Define action buttons based on risk level
            if risk_level in ["high", "critical"]:
                actions = {
                    "deny": "Deny",
                    "allow_once": "Allow Once",
                    "allow_session": "Allow for Session",
                    "allow_permanent": "Always Allow"
                }
            else:
                actions = {
                    "deny": "Deny",
                    "allow_session": "Allow",
                    "allow_permanent": "Always Allow"
                }
            
            # Send notification using zenity for better action support
            response = await self._send_permission_dialog(
                title, message, actions, urgency == "critical"
            )
            
            # Store callback
            if callback:
                self.response_callbacks[request_id] = callback
                # Call callback with response
                await callback(request_id, response)
            
            return True
        
        except Exception as e:
            logger.error(f"Error sending permission notification: {e}")
            return False
    
    async def _send_permission_dialog(
        self,
        title: str,
        message: str,
        actions: Dict[str, str],
        is_critical: bool = False
    ) -> str:
        """
        Send permission dialog using zenity.
        
        Args:
            title: Dialog title
            message: Dialog message
            actions: Available actions
            is_critical: Whether this is a critical permission request
            
        Returns:
            Selected action
        """
        try:
            # Build zenity command
            cmd = [
                "zenity",
                "--question",
                f"--title={title}",
                f"--text={message}",
                "--no-wrap",
                "--width=400",
                "--height=200"
            ]
            
            if is_critical:
                cmd.append("--warning")
            
            # Add extra buttons for more options
            if len(actions) > 2:
                cmd.extend([
                    "--extra-button=Allow Once",
                    "--extra-button=Allow for Session", 
                    "--extra-button=Always Allow"
                ])
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            # Map exit codes to responses
            if result.returncode == 0:
                return "allow_session"  # OK button
            elif result.returncode == 1:
                return "deny"  # Cancel button
            elif result.returncode == 5:
                return "allow_once"  # Extra button 1
            elif result.returncode == 6:
                return "allow_session"  # Extra button 2
            elif result.returncode == 7:
                return "allow_permanent"  # Extra button 3
            else:
                return "deny"  # Default to deny
        
        except FileNotFoundError:
            logger.warning("zenity not available, falling back to simple notification")
            # Fallback to simple notification
            await self.send_notification(
                title,
                f"{message}\n\nPlease respond via the extension interface.",
                urgency="critical" if is_critical else "normal"
            )
            return "allow_session"  # Default action
        
        except Exception as e:
            logger.error(f"Error showing permission dialog: {e}")
            return "deny"
    
    async def send_progress_notification(
        self,
        task_id: str,
        message: str,
        progress: float
    ) -> None:
        """
        Send task progress notification.
        
        Args:
            task_id: Task identifier
            message: Progress message
            progress: Progress percentage (0.0 to 1.0)
        """
        try:
            progress_percent = int(progress * 100)
            await self.send_notification(
                "AI Assistant",
                f"{message} ({progress_percent}%)",
                urgency="low",
                timeout=3000
            )
        
        except Exception as e:
            logger.error(f"Error sending progress notification: {e}")
    
    async def send_completion_notification(
        self,
        task_id: str,
        message: str,
        success: bool = True
    ) -> None:
        """
        Send task completion notification.
        
        Args:
            task_id: Task identifier
            message: Completion message
            success: Whether task completed successfully
        """
        try:
            title = "Task Completed" if success else "Task Failed"
            urgency = "normal" if success else "critical"
            
            await self.send_notification(
                title,
                message,
                urgency=urgency,
                timeout=10000 if not success else 5000
            )
        
        except Exception as e:
            logger.error(f"Error sending completion notification: {e}")
    
    def cleanup(self) -> None:
        """Cleanup notification manager resources."""
        self.active_notifications.clear()
        self.response_callbacks.clear()


# Global notification manager instance
notification_manager = NotificationManager()


# Convenience functions
async def send_notification(title: str, message: str, **kwargs) -> Optional[str]:
    """Send a notification."""
    return await notification_manager.send_notification(title, message, **kwargs)


async def send_permission_notification(title: str, message: str, risk_level: str, 
                                     request_id: str, callback: Optional[Callable] = None) -> bool:
    """Send a permission request notification."""
    return await notification_manager.send_permission_notification(
        title, message, risk_level, request_id, callback
    )


async def send_progress_notification(task_id: str, message: str, progress: float) -> None:
    """Send a task progress notification."""
    await notification_manager.send_progress_notification(task_id, message, progress)


async def send_completion_notification(task_id: str, message: str, success: bool = True) -> None:
    """Send a task completion notification."""
    await notification_manager.send_completion_notification(task_id, message, success)
