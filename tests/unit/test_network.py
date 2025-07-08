"""
Unit tests for the network tool.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
import asyncio
import socket

from src.gnome_ai_assistant.tools.network import NetworkTool
from src.gnome_ai_assistant.tools.base import ToolResponse


class TestNetworkTool:
    """Test the NetworkTool class."""
    
    def test_tool_initialization(self):
        """Test tool initializes correctly."""
        tool = NetworkTool()
        
        assert tool.name == "network"
        assert tool.description == "Network diagnostics, connectivity checks, and basic network control"
        assert tool.category == "system"
        assert len(tool.parameters) > 0
        assert tool.required_permissions == ["network_access", "system_info"]
    
    @pytest.mark.asyncio
    async def test_ping_success(self):
        """Test successful ping."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"PING google.com (8.8.8.8) 56(84) bytes of data.\n"
                b"64 bytes from 8.8.8.8: icmp_seq=1 time=10.5 ms\n"
                b"--- google.com ping statistics ---\n"
                b"1 packets transmitted, 1 received, 0% packet loss, time 0ms\n"
                b"rtt min/avg/max/mdev = 10.5/10.5/10.5/0.0 ms\n",
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="ping", target="google.com", count=1)
            
            assert result.success is True
            assert "google.com" in result.result
            assert result.metadata is not None
            assert result.metadata["target"] == "google.com"
            assert result.metadata["packets_sent"] == 1
    
    @pytest.mark.asyncio
    async def test_ping_failure(self):
        """Test ping failure."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"",
                b"ping: unknown host nonexistent.example.com\n"
            ))
            mock_process.returncode = 1
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="ping", target="nonexistent.example.com")
            
            assert result.success is False
            assert "Ping failed" in result.error
    
    @pytest.mark.asyncio
    async def test_ping_no_target(self):
        """Test ping without target parameter."""
        tool = NetworkTool()
        
        result = await tool.execute(action="ping")
        
        assert result.success is False
        assert "Target is required" in result.error
    
    @pytest.mark.asyncio
    async def test_traceroute_success(self):
        """Test successful traceroute."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"traceroute to google.com (8.8.8.8), 30 hops max, 60 byte packets\n"
                b" 1  router.local (192.168.1.1)  1.234 ms  1.123 ms  1.098 ms\n"
                b" 2  8.8.8.8 (8.8.8.8)  10.567 ms  10.234 ms  10.456 ms\n",
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="traceroute", target="google.com")
            
            assert result.success is True
            assert "google.com" in result.result
            assert result.metadata is not None
            assert result.metadata["target"] == "google.com"
    
    @pytest.mark.asyncio
    async def test_traceroute_fallback(self):
        """Test traceroute fallback to tracepath."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # First call (traceroute) fails with FileNotFoundError
            # Second call (tracepath) succeeds
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"tracepath to google.com\n"
                b" 1?: [LOCALHOST]                                         pmtu 1500\n"
                b" 2:  8.8.8.8                                           10.567ms reached\n",
                b""
            ))
            mock_process.returncode = 0
            
            call_count = 0
            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise FileNotFoundError("traceroute not found")
                return mock_process
            
            mock_subprocess.side_effect = side_effect
            
            result = await tool.execute(action="traceroute", target="google.com")
            
            assert result.success is True
            assert result.metadata["tool_used"] == "tracepath"
    
    @pytest.mark.asyncio
    async def test_port_scan_single_port(self):
        """Test port scan for single port."""
        tool = NetworkTool()
        
        with patch('asyncio.open_connection') as mock_open_connection:
            mock_reader = Mock()
            mock_writer = Mock()
            mock_writer.close = Mock()
            mock_writer.wait_closed = AsyncMock()
            mock_open_connection.return_value = (mock_reader, mock_writer)
            
            result = await tool.execute(action="port_scan", target="google.com", port=80)
            
            assert result.success is True
            assert result.metadata is not None
            assert len(result.metadata["results"]) == 1
            assert result.metadata["results"][0]["port"] == 80
            assert result.metadata["results"][0]["status"] == "open"
    
    @pytest.mark.asyncio
    async def test_port_scan_multiple_ports(self):
        """Test port scan for multiple common ports."""
        tool = NetworkTool()
        
        with patch('asyncio.open_connection') as mock_open_connection:
            # Mock some ports as open, some as closed
            def connection_side_effect(host, port):
                if port in [22, 80, 443]:
                    mock_reader = Mock()
                    mock_writer = Mock()
                    mock_writer.close = Mock()
                    mock_writer.wait_closed = AsyncMock()
                    return (mock_reader, mock_writer)
                else:
                    raise ConnectionRefusedError("Connection refused")
            
            mock_open_connection.side_effect = connection_side_effect
            
            result = await tool.execute(action="port_scan", target="example.com")
            
            assert result.success is True
            assert result.metadata is not None
            assert len(result.metadata["results"]) == 10  # Common ports
            
            open_ports = [r for r in result.metadata["results"] if r["status"] == "open"]
            assert len(open_ports) == 3  # 22, 80, 443
    
    @pytest.mark.asyncio
    async def test_get_interfaces(self):
        """Test get network interfaces."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN\n"
                b"    inet 127.0.0.1/8 scope host lo\n"
                b"2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc pfifo_fast state UP\n"
                b"    inet 192.168.1.100/24 brd 192.168.1.255 scope global eth0\n",
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="get_interfaces")
            
            assert result.success is True
            assert result.metadata is not None
            interfaces = result.metadata["interfaces"]
            assert len(interfaces) == 2
            assert interfaces[0]["name"] == "lo"
            assert interfaces[1]["name"] == "eth0"
    
    @pytest.mark.asyncio
    async def test_dns_lookup_success(self):
        """Test successful DNS lookup."""
        tool = NetworkTool()
        
        with patch('socket.getaddrinfo') as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 80)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.4.4', 80)),
            ]
            
            result = await tool.execute(action="dns_lookup", target="google.com")
            
            assert result.success is True
            assert result.metadata is not None
            addresses = result.metadata["addresses"]
            assert len(addresses) == 2
            assert addresses[0]["address"] == "8.8.8.8"
            assert addresses[1]["address"] == "8.8.4.4"
    
    @pytest.mark.asyncio
    async def test_dns_lookup_failure(self):
        """Test DNS lookup failure."""
        tool = NetworkTool()
        
        with patch('socket.getaddrinfo') as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = socket.gaierror("Name resolution failed")
            
            result = await tool.execute(action="dns_lookup", target="nonexistent.example.com")
            
            assert result.success is False
            assert "DNS lookup failed" in result.error
    
    @pytest.mark.asyncio
    async def test_check_connectivity(self):
        """Test connectivity check."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock responses: 8.8.8.8 and google.com succeed, 1.1.1.1 fails
            call_count = 0
            def subprocess_side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                mock_process = Mock()
                mock_process.communicate = AsyncMock(return_value=(b"", b""))
                
                if call_count <= 2:  # First two calls succeed
                    mock_process.returncode = 0
                else:  # Third call fails
                    mock_process.returncode = 1
                
                return mock_process
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            result = await tool.execute(action="check_connectivity")
            
            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["status"] == "good"  # 2 out of 3 reachable
            assert result.metadata["reachable_hosts"] == 2
    
    @pytest.mark.asyncio
    async def test_get_public_ip(self):
        """Test get public IP."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"203.0.113.1\n", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="get_public_ip")
            
            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["public_ip"] == "203.0.113.1"
    
    @pytest.mark.asyncio
    async def test_speed_test(self):
        """Test speed test."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(b"1048576.0,1.0", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="speed_test")
            
            assert result.success is True
            assert result.metadata is not None
            assert result.metadata["speed_mbps"] == 8.0  # 1MB/s = 8 Mbps
    
    @pytest.mark.asyncio
    async def test_wifi_scan(self):
        """Test WiFi scan."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = Mock()
            mock_process.communicate = AsyncMock(return_value=(
                b"IN-USE  SSID      MODE   CHAN  RATE        SIGNAL  BARS  SECURITY\n"
                b"*       MyWiFi    Infra  6     130 Mbit/s  85      ||||  WPA2\n"
                b"        OpenNet   Infra  11    54 Mbit/s   45      ||__  --\n",
                b""
            ))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process
            
            result = await tool.execute(action="wifi_scan")
            
            assert result.success is True
            assert result.metadata is not None
            networks = result.metadata["networks"]
            assert len(networks) == 2
            assert networks[0]["ssid"] == "MyWiFi"
    
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        """Test unknown action handling."""
        tool = NetworkTool()
        
        result = await tool.execute(action="unknown_action")
        
        assert result.success is False
        assert "Unknown action" in result.error
    
    def test_get_help(self):
        """Test help text generation."""
        tool = NetworkTool()
        
        help_text = tool.get_help()
        
        assert "Network Tool" in help_text
        assert "ping" in help_text
        assert "traceroute" in help_text
        assert "port_scan" in help_text
        assert "dns_lookup" in help_text
        assert "speed_test" in help_text
    
    def test_parameter_validation(self):
        """Test parameter validation."""
        tool = NetworkTool()
        
        # Test valid parameters
        errors = tool.validate_parameters(action="ping", target="google.com")
        assert len(errors) == 0
        
        # Test missing required parameter
        errors = tool.validate_parameters(target="google.com")  # Missing action
        assert len(errors) > 0
        assert any("required" in error for error in errors)
    
    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test exception handling in tool execution."""
        tool = NetworkTool()
        
        with patch('asyncio.create_subprocess_exec') as mock_subprocess:
            mock_subprocess.side_effect = Exception("Test exception")
            
            result = await tool.execute(action="ping", target="google.com")
            
            assert result.success is False
            assert "Test exception" in result.error
