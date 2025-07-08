"""
Unit tests for the web browser tool.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import asyncio

from src.gnome_ai_assistant.tools.web_browser import WebBrowserTool
from src.gnome_ai_assistant.tools.base import ToolResponse


class TestWebBrowserTool:
    """Test the WebBrowserTool class."""
    
    def test_tool_initialization(self):
        """Test tool initializes correctly."""
        tool = WebBrowserTool()
        
        assert tool.name == "web_browser"
        assert tool.description == "Control web browsers, open URLs, manage tabs and bookmarks"
        assert tool.category == "web"
        assert len(tool.parameters) > 0
        assert tool.required_permissions == ["browser_control", "url_access"]
    
    @pytest.mark.asyncio
    async def test_open_url_success(self):
        """Test successful URL opening."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="open_url", url="https://example.com")
            
            assert result.success is True
            assert "example.com" in result.result
            mock_subprocess.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_open_url_with_protocol_prefix(self):
        """Test URL opening with automatic protocol prefix."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="open_url", url="example.com")
            
            assert result.success is True
            # Should add https:// prefix
            call_args = mock_subprocess.call_args[0][0]
            assert any("https://example.com" in str(arg) for arg in call_args)
    
    @pytest.mark.asyncio
    async def test_open_url_failure(self):
        """Test URL opening failure."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="open_url", url="https://example.com")
            
            assert result.success is False
            assert "Failed to open URL" in result.error
    
    @pytest.mark.asyncio
    async def test_open_url_no_url(self):
        """Test URL opening without URL parameter."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="open_url")
        
        assert result.success is False
        assert "URL is required" in result.error
    
    @pytest.mark.asyncio
    async def test_web_search(self):
        """Test web search functionality."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="search", query="test query")
            
            assert result.success is True
            # Should use DuckDuckGo by default
            call_args = mock_subprocess.call_args[0][0]
            assert any("duckduckgo.com" in str(arg) for arg in call_args)
    
    @pytest.mark.asyncio
    async def test_web_search_no_query(self):
        """Test web search without query parameter."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="search")
        
        assert result.success is False
        assert "Search query is required" in result.error
    
    @pytest.mark.asyncio
    async def test_browser_selection(self):
        """Test different browser selection."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.wait = AsyncMock(return_value=None)
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            # Test Firefox
            result = await tool.execute(action="open_url", url="https://example.com", browser="firefox")
            assert result.success is True
            call_args = mock_subprocess.call_args[0][0]
            assert "firefox" in call_args
            
            # Test Chrome
            result = await tool.execute(action="open_url", url="https://example.com", browser="chrome")
            assert result.success is True
            call_args = mock_subprocess.call_args[0][0]
            assert "chrome" in call_args
    
    @pytest.mark.asyncio
    async def test_unsupported_browser(self):
        """Test unsupported browser error."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="open_url", url="https://example.com", browser="unsupported")
        
        assert result.success is False
        assert "Unsupported browser" in result.error
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action handling."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="unknown_action")
        
        assert result.success is False
        assert "Unknown action" in result.error
    
    @pytest.mark.asyncio
    async def test_get_tabs(self):
        """Test get tabs functionality."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"12345\n67890", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="get_tabs", browser="firefox")
            
            assert result.success is True
            assert "2 firefox processes" in result.result
    
    @pytest.mark.asyncio
    async def test_bookmark_url(self):
        """Test bookmark URL functionality."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="bookmark_url", url="https://example.com", bookmark_name="Test Site")
        
        assert result.success is True
        assert "Bookmark created" in result.result
        assert result.metadata is not None
        assert result.metadata["url"] == "https://example.com"
        assert result.metadata["name"] == "Test Site"
    
    @pytest.mark.asyncio
    async def test_bookmark_url_no_url(self):
        """Test bookmark URL without URL parameter."""
        tool = WebBrowserTool()
        
        result = await tool.execute(action="bookmark_url")
        
        assert result.success is False
        assert "URL is required" in result.error
    
    @pytest.mark.asyncio
    async def test_navigation_actions_not_implemented(self):
        """Test navigation actions that are not implemented."""
        tool = WebBrowserTool()
        
        # Test navigate back
        result = await tool.execute(action="navigate_back")
        assert result.success is False
        assert "browser automation" in result.error
        
        # Test navigate forward
        result = await tool.execute(action="navigate_forward")
        assert result.success is False
        assert "browser automation" in result.error
        
        # Test refresh
        result = await tool.execute(action="refresh")
        assert result.success is False
        assert "browser automation" in result.error
    
    def test_get_help(self):
        """Test help text generation."""
        tool = WebBrowserTool()
        
        help_text = tool.get_help()
        
        assert "Web Browser Control Tool" in help_text
        assert "open_url" in help_text
        assert "search" in help_text
        assert "bookmark_url" in help_text
        assert "firefox" in help_text
        assert "chrome" in help_text
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        tool = WebBrowserTool()
        
        # Test valid parameters
        errors = tool.validate_parameters(action="open_url", url="https://example.com")
        assert len(errors) == 0
        
        # Test missing required parameter
        errors = tool.validate_parameters(url="https://example.com")  # Missing action
        assert len(errors) > 0
        assert any("required" in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling in tool execution."""
        tool = WebBrowserTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Test exception")
            
            result = await tool.execute(action="open_url", url="https://example.com")
            
            assert result.success is False
            assert "Test exception" in result.error
