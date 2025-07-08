"""
Spotify control tool for GNOME AI Assistant.

This module provides functionality to control Spotify playback
using DBus integration with the Media Player Remote Interfacing Specification (MPRIS).
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolParameter, ToolResponse
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SpotifyTrack:
    """Represents a Spotify track."""
    title: str
    artist: str
    album: str
    duration: int  # seconds
    position: int  # seconds
    track_id: str


class SpotifyTool(BaseTool):
    """Tool for controlling Spotify playback."""
    
    def __init__(self):
        super().__init__(
            name="spotify",
            description="Control Spotify music playback",
            parameters=[
                ToolParameter(
                    name="action",
                    description="Action to perform",
                    type="string",
                    required=True,
                    enum=[
                        "play", "pause", "next", "previous", "stop",
                        "get_current", "set_volume", "seek", "search",
                        "get_playlists", "play_playlist"
                    ]
                ),
                ToolParameter(
                    name="query",
                    description="Search query or playlist name",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="volume",
                    description="Volume level (0.0 to 1.0)",
                    type="number",
                    required=False
                ),
                ToolParameter(
                    name="position",
                    description="Position to seek to in seconds",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="uri",
                    description="Spotify URI to play",
                    type="string",
                    required=False
                )
            ]
        )
        self._dbus_interface = None
        self._player_interface = None
    
    async def _ensure_dbus_connection(self) -> bool:
        """Ensure DBus connection to Spotify."""
        try:
            if self._dbus_interface is None:
                # Use DBus to connect to Spotify
                process = await asyncio.create_subprocess_exec(
                    "dbus-send", "--print-reply", "--session",
                    "--dest=org.mpris.MediaPlayer2.spotify",
                    "/org/mpris/MediaPlayer2",
                    "org.freedesktop.DBus.Introspectable.Introspect",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0:
                    self._dbus_interface = True
                    logger.info("Connected to Spotify via DBus")
                    return True
                else:
                    logger.warning("Spotify not running or not accessible via DBus")
                    return False
        except Exception as e:
            logger.error(f"Failed to connect to Spotify: {e}")
            return False
        
        return self._dbus_interface is not None
    
    async def _dbus_call(self, method: str, *args) -> Optional[str]:
        """Make a DBus method call to Spotify."""
        try:
            cmd = [
                "dbus-send", "--print-reply", "--session",
                "--dest=org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2"
            ]
            
            if method.startswith("Player."):
                cmd[-1] = "/org/mpris/MediaPlayer2"
                cmd.append(f"org.mpris.MediaPlayer2.{method}")
            else:
                cmd.append(f"org.mpris.MediaPlayer2.{method}")
            
            # Add arguments
            for arg in args:
                if isinstance(arg, str):
                    cmd.append(f"string:{arg}")
                elif isinstance(arg, (int, float)):
                    cmd.append(f"double:{arg}")
                elif isinstance(arg, bool):
                    cmd.append(f"boolean:{str(arg).lower()}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                logger.error(f"DBus call failed: {stderr.decode()}")
                return None
                
        except Exception as e:
            logger.error(f"Error making DBus call: {e}")
            return None
    
    async def _get_property(self, property_name: str) -> Optional[str]:
        """Get a property from Spotify via DBus."""
        try:
            cmd = [
                "dbus-send", "--print-reply", "--session",
                "--dest=org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2",
                "org.freedesktop.DBus.Properties.Get",
                "string:org.mpris.MediaPlayer2.Player",
                f"string:{property_name}"
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                return stdout.decode().strip()
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error getting property: {e}")
            return None
    
    async def _get_current_track(self) -> Optional[SpotifyTrack]:
        """Get information about the currently playing track."""
        try:
            metadata_output = await self._get_property("Metadata")
            position_output = await self._get_property("Position")
            
            if not metadata_output:
                return None
            
            # Parse metadata (simplified parsing)
            title = "Unknown"
            artist = "Unknown"
            album = "Unknown"
            duration = 0
            track_id = ""
            position = 0
            
            # Extract basic info from DBus output
            lines = metadata_output.split('\n')
            for line in lines:
                if 'xesam:title' in line and 'string' in line:
                    title = line.split('"')[-2] if '"' in line else title
                elif 'xesam:artist' in line and 'string' in line:
                    artist = line.split('"')[-2] if '"' in line else artist
                elif 'xesam:album' in line and 'string' in line:
                    album = line.split('"')[-2] if '"' in line else album
                elif 'mpris:length' in line and 'int64' in line:
                    try:
                        duration = int(line.split()[-1]) // 1000000  # Convert from microseconds
                    except (ValueError, IndexError):
                        pass
                elif 'mpris:trackid' in line and 'string' in line:
                    track_id = line.split('"')[-2] if '"' in line else track_id
            
            # Parse position
            if position_output and 'int64' in position_output:
                try:
                    position = int(position_output.split()[-1]) // 1000000  # Convert from microseconds
                except (ValueError, IndexError):
                    pass
            
            return SpotifyTrack(
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                position=position,
                track_id=track_id
            )
            
        except Exception as e:
            logger.error(f"Error getting current track: {e}")
            return None
    
    async def _search_spotify(self, query: str) -> List[Dict[str, Any]]:
        """Search for tracks on Spotify (requires Spotify Web API)."""
        # This would require Spotify Web API integration
        # For now, return a placeholder
        logger.info(f"Searching Spotify for: {query}")
        return [{"message": "Search functionality requires Spotify Web API integration"}]
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute Spotify control action."""
        action = parameters.get("action")
        
        if not await self._ensure_dbus_connection():
            return ToolResponse(
                success=False,
                result=None,
                error="Spotify is not running or not accessible"
            )
        
        try:
            if action == "play":
                result = await self._dbus_call("Player.Play")
                return ToolResponse(
                    success=True,
                    result={"action": "play", "status": "Playing"}
                )
            
            elif action == "pause":
                result = await self._dbus_call("Player.Pause")
                return ToolResponse(
                    success=True,
                    result={"action": "pause", "status": "Paused"}
                )
            
            elif action == "stop":
                result = await self._dbus_call("Player.Stop")
                return ToolResponse(
                    success=True,
                    result={"action": "stop", "status": "Stopped"}
                )
            
            elif action == "next":
                result = await self._dbus_call("Player.Next")
                return ToolResponse(
                    success=True,
                    result={"action": "next", "status": "Skipped to next track"}
                )
            
            elif action == "previous":
                result = await self._dbus_call("Player.Previous")
                return ToolResponse(
                    success=True,
                    result={"action": "previous", "status": "Skipped to previous track"}
                )
            
            elif action == "get_current":
                track = await self._get_current_track()
                if track:
                    return ToolResponse(
                        success=True,
                        result={
                            "current_track": {
                                "title": track.title,
                                "artist": track.artist,
                                "album": track.album,
                                "duration": track.duration,
                                "position": track.position
                            }
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="No track currently playing"
                    )
            
            elif action == "set_volume":
                volume = parameters.get("volume", 0.5)
                if not 0.0 <= volume <= 1.0:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Volume must be between 0.0 and 1.0"
                    )
                
                result = await self._dbus_call("Player.SetVolume", volume)
                return ToolResponse(
                    success=True,
                    result={"action": "set_volume", "volume": volume}
                )
            
            elif action == "seek":
                position = parameters.get("position", 0)
                # Convert to microseconds for DBus
                position_us = position * 1000000
                result = await self._dbus_call("Player.SetPosition", position_us)
                return ToolResponse(
                    success=True,
                    result={"action": "seek", "position": position}
                )
            
            elif action == "search":
                query = parameters.get("query", "")
                if not query:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Search query is required"
                    )
                
                results = await self._search_spotify(query)
                return ToolResponse(
                    success=True,
                    result={"action": "search", "query": query, "results": results}
                )
            
            elif action == "get_playlists":
                # This would require Spotify Web API integration
                return ToolResponse(
                    success=True,
                    result={
                        "action": "get_playlists",
                        "message": "Playlist functionality requires Spotify Web API integration"
                    }
                )
            
            elif action == "play_playlist":
                uri = parameters.get("uri", "")
                if not uri:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="Spotify URI is required"
                    )
                
                result = await self._dbus_call("Player.OpenUri", uri)
                return ToolResponse(
                    success=True,
                    result={"action": "play_playlist", "uri": uri}
                )
            
            else:
                return ToolResponse(
                    success=False,
                    result=None,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Error executing Spotify action {action}: {e}")
            return ToolResponse(
                success=False,
                result=None,
                error=f"Failed to execute action: {str(e)}"
            )
