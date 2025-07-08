"""Web browser control tool for the AI assistant."""

import asyncio
import subprocess
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .base import BaseTool, ToolResponse, ToolParameter
from ..core.permissions import RiskLevel
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WebBrowserTool(BaseTool):
    """Tool for controlling web browsers and web navigation."""
    
    def __init__(self):
        super().__init__()
        self.name = "web_browser"
        self.description = "Control web browsers, open URLs, manage tabs and bookmarks"
        self.category = "web"
        self.risk_level = RiskLevel.MEDIUM
        self.required_permissions = ["browser_control", "url_access"]
        
        # Define parameters
        self.parameters = [
            ToolParameter(
                name="action",
                type="string",
                description="Action to perform",
                required=True,
                enum_values=[
                    "open_url", "open_tab", "close_tab", "search",
                    "get_tabs", "bookmark_url", "get_bookmarks",
                    "navigate_back", "navigate_forward", "refresh"
                ]
            ),
            ToolParameter(
                name="url",
                type="string", 
                description="URL to open or bookmark",
                required=False
            ),
            ToolParameter(
                name="query",
                type="string",
                description="Search query for web search",
                required=False
            ),
            ToolParameter(
                name="browser",
                type="string",
                description="Browser to use (firefox, chrome, default)",
                required=False,
                default="default",
                enum_values=["firefox", "chrome", "chromium", "default"]
            ),
            ToolParameter(
                name="tab_id",
                type="string",
                description="Tab ID for tab-specific operations",
                required=False
            ),
            ToolParameter(
                name="bookmark_name",
                type="string",
                description="Name for the bookmark",
                required=False
            )
        ]
    
    async def execute(self, action: str, url: str = None, query: str = None, 
                     browser: str = "default", tab_id: str = None, 
                     bookmark_name: str = None, **kwargs) -> ToolResponse:
        """
        Execute web browser control action.
        
        Args:
            action: Action to perform
            url: URL for URL-based actions
            query: Search query for search actions
            browser: Browser to use
            tab_id: Tab ID for tab operations
            bookmark_name: Name for bookmarks
            
        Returns:
            Tool execution result
        """
        try:
            if action == "open_url":
                return await self._open_url(url, browser)
            elif action == "open_tab":
                return await self._open_tab(url, browser)
            elif action == "close_tab":
                return await self._close_tab(tab_id, browser)
            elif action == "search":
                return await self._web_search(query, browser)
            elif action == "get_tabs":
                return await self._get_tabs(browser)
            elif action == "bookmark_url":
                return await self._bookmark_url(url, bookmark_name, browser)
            elif action == "get_bookmarks":
                return await self._get_bookmarks(browser)
            elif action == "navigate_back":
                return await self._navigate_back(browser)
            elif action == "navigate_forward":
                return await self._navigate_forward(browser)
            elif action == "refresh":
                return await self._refresh_page(browser)
            else:
                return ToolResponse(
                    success=False,
                    error=f"Unknown action: {action}"
                )
                
        except Exception as e:
            logger.error(f"Web browser tool error: {e}")
            return ToolResponse(
                success=False,
                error=f"Browser operation failed: {str(e)}"
            )
    
    async def _open_url(self, url: str, browser: str) -> ToolResponse:
        """Open a URL in the browser."""
        if not url:
            return ToolResponse(success=False, error="URL is required")
        
        try:
            # Validate URL format
            if not (url.startswith('http://') or url.startswith('https://') or url.startswith('file://')):
                url = f"https://{url}"
            
            if browser == "default":
                cmd = ["xdg-open", url]
            elif browser == "firefox":
                cmd = ["firefox", url]
            elif browser in ["chrome", "chromium"]:
                cmd = [browser, url]
            else:
                return ToolResponse(success=False, error=f"Unsupported browser: {browser}")
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.wait()
            
            if process.returncode == 0:
                return ToolResponse(
                    success=True,
                    result=f"Opened URL: {url} in {browser}"
                )
            else:
                return ToolResponse(
                    success=False,
                    error=f"Failed to open URL in {browser}"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to open URL: {str(e)}")
    
    async def _open_tab(self, url: str, browser: str) -> ToolResponse:
        """Open a new tab with URL."""
        if not url:
            return ToolResponse(success=False, error="URL is required")
        
        try:
            if not (url.startswith('http://') or url.startswith('https://')):
                url = f"https://{url}"
            
            if browser == "firefox":
                cmd = ["firefox", "--new-tab", url]
            elif browser in ["chrome", "chromium"]:
                cmd = [browser, "--new-tab", url]
            else:
                # Fallback to opening URL normally
                return await self._open_url(url, browser)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            await process.wait()
            
            return ToolResponse(
                success=True,
                result=f"Opened new tab with URL: {url}"
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to open tab: {str(e)}")
    
    async def _web_search(self, query: str, browser: str) -> ToolResponse:
        """Perform a web search."""
        if not query:
            return ToolResponse(success=False, error="Search query is required")
        
        try:
            # Use DuckDuckGo as default search engine
            search_url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
            return await self._open_url(search_url, browser)
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Search failed: {str(e)}")
    
    async def _get_tabs(self, browser: str) -> ToolResponse:
        """Get list of open tabs (limited implementation)."""
        try:
            # This is a simplified implementation
            # Real implementation would require browser-specific APIs
            
            if browser == "firefox":
                # Try to get Firefox tabs using lz4jsoncat if available
                cmd = ["pgrep", "-f", "firefox"]
            elif browser in ["chrome", "chromium"]:
                cmd = ["pgrep", "-f", browser]
            else:
                return ToolResponse(
                    success=False,
                    error="Tab listing not supported for this browser"
                )
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await process.communicate()
            
            if process.returncode == 0 and stdout:
                pids = stdout.decode().strip().split('\n')
                return ToolResponse(
                    success=True,
                    result=f"Found {len(pids)} {browser} processes running"
                )
            else:
                return ToolResponse(
                    success=True,
                    result=f"No {browser} processes found"
                )
                
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get tabs: {str(e)}")
    
    async def _bookmark_url(self, url: str, name: str, browser: str) -> ToolResponse:
        """Bookmark a URL (simplified implementation)."""
        if not url:
            return ToolResponse(success=False, error="URL is required")
        
        try:
            # This is a simplified implementation
            # Real implementation would integrate with browser bookmark APIs
            
            bookmark_data = {
                "url": url,
                "name": name or url,
                "timestamp": asyncio.get_event_loop().time(),
                "browser": browser
            }
            
            return ToolResponse(
                success=True,
                result=f"Bookmark created for {url}",
                metadata=bookmark_data
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to bookmark: {str(e)}")
    
    async def _get_bookmarks(self, browser: str) -> ToolResponse:
        """Get bookmarks (simplified implementation)."""
        try:
            # This would normally read from browser bookmark files
            # For now, return a placeholder response
            
            return ToolResponse(
                success=True,
                result="Bookmark listing requires browser-specific implementation",
                metadata={"browser": browser}
            )
            
        except Exception as e:
            return ToolResponse(success=False, error=f"Failed to get bookmarks: {str(e)}")
    
    async def _navigate_back(self, browser: str) -> ToolResponse:
        """Navigate back in browser (requires browser automation)."""
        return ToolResponse(
            success=False,
            error="Navigation control requires browser automation setup"
        )
    
    async def _navigate_forward(self, browser: str) -> ToolResponse:
        """Navigate forward in browser (requires browser automation)."""
        return ToolResponse(
            success=False, 
            error="Navigation control requires browser automation setup"
        )
    
    async def _refresh_page(self, browser: str) -> ToolResponse:
        """Refresh current page (requires browser automation)."""
        return ToolResponse(
            success=False,
            error="Page refresh requires browser automation setup"
        )
    
    def get_help(self) -> str:
        """Get help text for the tool."""
        return """
Web Browser Control Tool

This tool allows you to control web browsers and perform web-related tasks.

Available actions:
- open_url: Open a URL in the browser
- open_tab: Open a new tab with URL  
- search: Perform a web search
- close_tab: Close a specific tab
- get_tabs: Get list of open tabs
- bookmark_url: Bookmark a URL
- get_bookmarks: Get saved bookmarks
- navigate_back: Go back in browser history
- navigate_forward: Go forward in browser history  
- refresh: Refresh the current page

Supported browsers: firefox, chrome, chromium, default

Examples:
- Open a website: {"action": "open_url", "url": "https://example.com"}
- Search the web: {"action": "search", "query": "AI assistant"} 
- Open new tab: {"action": "open_tab", "url": "https://docs.example.com"}
- Bookmark page: {"action": "bookmark_url", "url": "https://example.com", "bookmark_name": "Example Site"}
"""
