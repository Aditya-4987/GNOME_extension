"""
Enhanced Spotify control tool for GNOME AI Assistant.

This module provides comprehensive Spotify integration using DBus
and additional metadata retrieval capabilities.
"""

import asyncio
import logging
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import time

try:
    import dbus
    DBUS_AVAILABLE = True
except ImportError:
    DBUS_AVAILABLE = False

from .base import BaseTool, ToolParameter, ToolResponse
from ..utils.logger import get_logger
from ..core.permissions import RiskLevel

logger = get_logger(__name__)


@dataclass
class TrackInfo:
    """Information about a Spotify track."""
    track_id: str
    title: str
    artist: str
    album: str
    duration: int  # in seconds
    position: int  # current position in seconds
    artwork_url: str
    spotify_url: str


@dataclass
class PlaylistInfo:
    """Information about a Spotify playlist."""
    playlist_id: str
    name: str
    description: str
    track_count: int
    public: bool
    collaborative: bool
    owner: str


class SpotifyTool(BaseTool):
    """Enhanced Spotify control and information tool."""
    
    def __init__(self):
        super().__init__(
            name="spotify",
            description="Control Spotify playback and get music information",
            parameters=[
                ToolParameter(
                    name="action",
                    description="Spotify action to perform",
                    type="string",
                    required=True,
                    enum=[
                        "play", "pause", "toggle", "next", "previous",
                        "get_current_track", "get_status", "set_volume",
                        "seek", "shuffle", "repeat", "search", "play_track",
                        "play_album", "play_playlist", "get_playlists",
                        "get_recent_tracks", "get_recommendations",
                        "save_track", "remove_track", "create_playlist"
                    ]
                ),
                ToolParameter(
                    name="query",
                    description="Search query for tracks, albums, or playlists",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="track_uri",
                    description="Spotify track URI (spotify:track:...)",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="playlist_uri",
                    description="Spotify playlist URI",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="volume",
                    description="Volume level (0-100)",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="position",
                    description="Seek position in seconds",
                    type="integer",
                    required=False
                ),
                ToolParameter(
                    name="shuffle_mode",
                    description="Shuffle mode (true/false)",
                    type="boolean",
                    required=False
                ),
                ToolParameter(
                    name="repeat_mode",
                    description="Repeat mode (off, track, context)",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="playlist_name",
                    description="Name for new playlist",
                    type="string",
                    required=False
                ),
                ToolParameter(
                    name="limit",
                    description="Number of results to return",
                    type="integer",
                    required=False
                )
            ],
            required_permissions=["media_control", "external_services"],
            risk_level=RiskLevel.LOW
        )
        
        self.dbus_interface = None
        self.properties_interface = None
        self.session_bus = None
        
    async def _get_dbus_interface(self):
        """Get Spotify DBus interface."""
        if not DBUS_AVAILABLE:
            raise Exception("DBus not available")
        
        try:
            if not self.session_bus:
                self.session_bus = dbus.SessionBus()
            
            # Get Spotify object
            spotify_object = self.session_bus.get_object(
                "org.mpris.MediaPlayer2.spotify",
                "/org/mpris/MediaPlayer2"
            )
            
            self.dbus_interface = dbus.Interface(
                spotify_object,
                "org.mpris.MediaPlayer2.Player"
            )
            
            self.properties_interface = dbus.Interface(
                spotify_object,
                "org.freedesktop.DBus.Properties"
            )
            
            return True
            
        except dbus.DBusException as e:
            logger.error(f"Failed to connect to Spotify DBus: {e}")
            return False
    
    async def _run_spotify_command(self, cmd: List[str]) -> tuple[int, str, str]:
        """Run a Spotify command using spotify CLI or other tools."""
        try:
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
    
    async def _get_current_track_info(self) -> Optional[TrackInfo]:
        """Get information about the currently playing track."""
        try:
            if not await self._get_dbus_interface():
                return None
            
            # Get metadata from DBus
            metadata = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player",
                "Metadata"
            )
            
            # Get position
            position = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player",
                "Position"
            ) // 1000000  # Convert microseconds to seconds
            
            # Extract track information
            track_id = metadata.get("mpris:trackid", "")
            title = metadata.get("xesam:title", "Unknown")
            artist = ", ".join(metadata.get("xesam:artist", ["Unknown"]))
            album = metadata.get("xesam:album", "Unknown")
            duration = metadata.get("mpris:length", 0) // 1000000  # Convert to seconds
            artwork_url = metadata.get("mpris:artUrl", "")
            spotify_url = metadata.get("xesam:url", "")
            
            return TrackInfo(
                track_id=track_id,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                position=position,
                artwork_url=artwork_url,
                spotify_url=spotify_url
            )
            
        except Exception as e:
            logger.error(f"Error getting current track info: {e}")
            return None
    
    async def _get_playback_status(self) -> Dict[str, Any]:
        """Get current playback status."""
        try:
            if not await self._get_dbus_interface():
                return {}
            
            status = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player",
                "PlaybackStatus"
            )
            
            volume = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player",
                "Volume"
            )
            
            shuffle = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player", 
                "Shuffle"
            )
            
            loop_status = self.properties_interface.Get(
                "org.mpris.MediaPlayer2.Player",
                "LoopStatus"
            )
            
            return {
                "status": status.lower(),
                "volume": int(volume * 100),
                "shuffle": shuffle,
                "repeat": loop_status.lower()
            }
            
        except Exception as e:
            logger.error(f"Error getting playback status: {e}")
            return {}
    
    async def _search_spotify(self, query: str, search_type: str = "track", limit: int = 10) -> List[Dict[str, Any]]:
        """Search Spotify using CLI tool or API."""
        try:
            # Try using spotify CLI tool if available
            cmd = ["spotify", "search", search_type, query, "--limit", str(limit)]
            returncode, stdout, stderr = await self._run_spotify_command(cmd)
            
            if returncode == 0:
                # Parse JSON output
                try:
                    results = json.loads(stdout)
                    return results.get(f"{search_type}s", {}).get("items", [])
                except json.JSONDecodeError:
                    pass
            
            # Fallback: use web scraping or other methods
            logger.warning("Spotify CLI not available, search limited")
            return []
            
        except Exception as e:
            logger.error(f"Error searching Spotify: {e}")
            return []
    
    async def _control_playback(self, action: str) -> bool:
        """Control Spotify playback."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            if action == "play":
                self.dbus_interface.Play()
            elif action == "pause":
                self.dbus_interface.Pause()
            elif action == "toggle":
                self.dbus_interface.PlayPause()
            elif action == "next":
                self.dbus_interface.Next()
            elif action == "previous":
                self.dbus_interface.Previous()
            elif action == "stop":
                self.dbus_interface.Stop()
            else:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error controlling playback: {e}")
            return False
    
    async def _set_volume(self, volume: int) -> bool:
        """Set Spotify volume (0-100)."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            # Convert to 0.0-1.0 range
            volume_float = max(0.0, min(1.0, volume / 100.0))
            
            self.properties_interface.Set(
                "org.mpris.MediaPlayer2.Player",
                "Volume",
                volume_float
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting volume: {e}")
            return False
    
    async def _seek_to_position(self, position: int) -> bool:
        """Seek to specific position in track."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            # Convert seconds to microseconds
            position_microseconds = position * 1000000
            
            self.dbus_interface.SetPosition(
                dbus.ObjectPath("/not/used"),  # Spotify ignores this parameter
                position_microseconds
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeking to position: {e}")
            return False
    
    async def _set_shuffle(self, shuffle: bool) -> bool:
        """Set shuffle mode."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            self.properties_interface.Set(
                "org.mpris.MediaPlayer2.Player",
                "Shuffle",
                shuffle
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting shuffle: {e}")
            return False
    
    async def _set_repeat(self, repeat_mode: str) -> bool:
        """Set repeat mode (None, Track, Playlist)."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            mode_map = {
                "off": "None",
                "track": "Track", 
                "context": "Playlist",
                "playlist": "Playlist"
            }
            
            dbus_mode = mode_map.get(repeat_mode.lower(), "None")
            
            self.properties_interface.Set(
                "org.mpris.MediaPlayer2.Player",
                "LoopStatus",
                dbus_mode
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting repeat mode: {e}")
            return False
    
    async def _play_uri(self, uri: str) -> bool:
        """Play a specific Spotify URI."""
        try:
            if not await self._get_dbus_interface():
                return False
            
            self.dbus_interface.OpenUri(uri)
            return True
            
        except Exception as e:
            logger.error(f"Error playing URI {uri}: {e}")
            return False
    
    async def _get_playlists(self) -> List[PlaylistInfo]:
        """Get user's playlists."""
        try:
            # Try using spotify CLI
            cmd = ["spotify", "list", "playlists"]
            returncode, stdout, stderr = await self._run_spotify_command(cmd)
            
            if returncode == 0:
                try:
                    data = json.loads(stdout)
                    playlists = []
                    
                    for item in data.get("items", []):
                        playlists.append(PlaylistInfo(
                            playlist_id=item.get("id", ""),
                            name=item.get("name", ""),
                            description=item.get("description", ""),
                            track_count=item.get("tracks", {}).get("total", 0),
                            public=item.get("public", False),
                            collaborative=item.get("collaborative", False),
                            owner=item.get("owner", {}).get("display_name", "")
                        ))
                    
                    return playlists
                    
                except json.JSONDecodeError:
                    pass
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting playlists: {e}")
            return []
    
    async def execute(self, parameters: Dict[str, Any]) -> ToolResponse:
        """Execute Spotify action."""
        action = parameters.get("action")
        
        try:
            if action in ["play", "pause", "toggle", "next", "previous", "stop"]:
                success = await self._control_playback(action)
                return ToolResponse(
                    success=success,
                    result={
                        "action": action,
                        "status": "success" if success else "failed"
                    } if success else None,
                    error=f"Failed to {action} Spotify" if not success else None
                )
            
            elif action == "get_current_track":
                track_info = await self._get_current_track_info()
                if track_info:
                    return ToolResponse(
                        success=True,
                        result={
                            "action": "get_current_track",
                            "track": {
                                "title": track_info.title,
                                "artist": track_info.artist,
                                "album": track_info.album,
                                "duration": track_info.duration,
                                "position": track_info.position,
                                "spotify_url": track_info.spotify_url
                            }
                        }
                    )
                else:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="No track currently playing or Spotify not running"
                    )
            
            elif action == "get_status":
                status = await self._get_playback_status()
                track_info = await self._get_current_track_info()
                
                result = {
                    "action": "get_status",
                    "playback": status
                }
                
                if track_info:
                    result["current_track"] = {
                        "title": track_info.title,
                        "artist": track_info.artist,
                        "album": track_info.album
                    }
                
                return ToolResponse(
                    success=True,
                    result=result
                )
            
            elif action == "set_volume":
                volume = parameters.get("volume")
                if volume is None:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="volume parameter is required"
                    )
                
                success = await self._set_volume(volume)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "set_volume",
                        "volume": volume
                    } if success else None,
                    error="Failed to set volume" if not success else None
                )
            
            elif action == "seek":
                position = parameters.get("position")
                if position is None:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="position parameter is required"
                    )
                
                success = await self._seek_to_position(position)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "seek",
                        "position": position
                    } if success else None,
                    error="Failed to seek" if not success else None
                )
            
            elif action == "shuffle":
                shuffle_mode = parameters.get("shuffle_mode")
                if shuffle_mode is None:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="shuffle_mode parameter is required"
                    )
                
                success = await self._set_shuffle(shuffle_mode)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "shuffle",
                        "shuffle_mode": shuffle_mode
                    } if success else None,
                    error="Failed to set shuffle mode" if not success else None
                )
            
            elif action == "repeat":
                repeat_mode = parameters.get("repeat_mode", "off")
                
                success = await self._set_repeat(repeat_mode)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "repeat",
                        "repeat_mode": repeat_mode
                    } if success else None,
                    error="Failed to set repeat mode" if not success else None
                )
            
            elif action == "search":
                query = parameters.get("query")
                if not query:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="query parameter is required"
                    )
                
                limit = parameters.get("limit", 10)
                results = await self._search_spotify(query, "track", limit)
                
                return ToolResponse(
                    success=True,
                    result={
                        "action": "search",
                        "query": query,
                        "results": results[:limit]
                    }
                )
            
            elif action == "play_track":
                track_uri = parameters.get("track_uri")
                if not track_uri:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="track_uri parameter is required"
                    )
                
                success = await self._play_uri(track_uri)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "play_track",
                        "track_uri": track_uri
                    } if success else None,
                    error="Failed to play track" if not success else None
                )
            
            elif action == "play_playlist":
                playlist_uri = parameters.get("playlist_uri")
                if not playlist_uri:
                    return ToolResponse(
                        success=False,
                        result=None,
                        error="playlist_uri parameter is required"
                    )
                
                success = await self._play_uri(playlist_uri)
                return ToolResponse(
                    success=success,
                    result={
                        "action": "play_playlist",
                        "playlist_uri": playlist_uri
                    } if success else None,
                    error="Failed to play playlist" if not success else None
                )
            
            elif action == "get_playlists":
                playlists = await self._get_playlists()
                
                return ToolResponse(
                    success=True,
                    result={
                        "action": "get_playlists",
                        "playlists": [
                            {
                                "id": p.playlist_id,
                                "name": p.name,
                                "description": p.description,
                                "track_count": p.track_count,
                                "public": p.public,
                                "collaborative": p.collaborative,
                                "owner": p.owner
                            }
                            for p in playlists
                        ]
                    }
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
                error=f"Spotify error: {e}"
            )
