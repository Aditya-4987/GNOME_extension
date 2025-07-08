"""
Command-line interface for GNOME AI Assistant.

This module provides a CLI for interacting with the AI assistant
when the GNOME extension is not available or for scripting purposes.
"""

import argparse
import asyncio
import json
import sys
import time
from typing import Any, Dict, List, Optional
import aiohttp
import os

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CLIInterface:
    """Command-line interface for the AI assistant."""
    
    def __init__(self, socket_path: str = "/tmp/gnome_ai_assistant.sock"):
        self.socket_path = socket_path
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.UnixConnector(path=self.socket_path)
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session
    
    async def _close_session(self):
        """Close HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to the AI assistant service."""
        try:
            session = await self._get_session()
            url = f"http://localhost{endpoint}"
            
            if method.upper() == "GET":
                async with session.get(url, params=data) as response:
                    return await response.json()
            elif method.upper() == "POST":
                async with session.post(url, json=data) as response:
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
                
        except aiohttp.ClientError as e:
            return {"error": f"Connection error: {e}"}
        except Exception as e:
            return {"error": f"Request error: {e}"}
    
    async def send_message(self, message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to the AI assistant."""
        data = {
            "message": message,
            "conversation_id": conversation_id
        }
        
        return await self._make_request("POST", "/chat", data)
    
    async def get_status(self) -> Dict[str, Any]:
        """Get the status of the AI assistant service."""
        return await self._make_request("GET", "/status")
    
    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        return await self._make_request("GET", "/tools")
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific tool."""
        data = {
            "tool_name": tool_name,
            "parameters": parameters
        }
        
        return await self._make_request("POST", "/tools/execute", data)
    
    async def get_conversations(self) -> Dict[str, Any]:
        """Get list of conversations."""
        return await self._make_request("GET", "/conversations")
    
    async def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get a specific conversation."""
        return await self._make_request("GET", f"/conversations/{conversation_id}")
    
    async def delete_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Delete a conversation."""
        return await self._make_request("DELETE", f"/conversations/{conversation_id}")
    
    async def emergency_stop(self) -> Dict[str, Any]:
        """Emergency stop the AI assistant."""
        return await self._make_request("POST", "/emergency_stop")


def format_response(response: Dict[str, Any], verbose: bool = False) -> str:
    """Format response for CLI output."""
    if "error" in response:
        return f"Error: {response['error']}"
    
    if "message" in response:
        result = response["message"]
        
        if verbose and "metadata" in response:
            result += f"\n\nMetadata: {json.dumps(response['metadata'], indent=2)}"
        
        return result
    
    # For other responses, pretty print JSON
    return json.dumps(response, indent=2)


async def interactive_mode(cli: CLIInterface):
    """Run interactive chat mode."""
    print("GNOME AI Assistant - Interactive Mode")
    print("Type 'exit' to quit, 'help' for commands")
    print("-" * 40)
    
    conversation_id = None
    
    while True:
        try:
            user_input = input("\n> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit']:
                break
            
            if user_input.lower() == 'help':
                print("""
Available commands:
  help                 - Show this help
  status              - Show service status
  tools               - List available tools
  conversations       - List conversations
  new                 - Start new conversation
  exit/quit           - Exit interactive mode
  
  Or just type your message to chat with the AI assistant.
                """)
                continue
            
            if user_input.lower() == 'status':
                response = await cli.get_status()
                print(format_response(response, verbose=True))
                continue
            
            if user_input.lower() == 'tools':
                response = await cli.list_tools()
                print(format_response(response, verbose=True))
                continue
            
            if user_input.lower() == 'conversations':
                response = await cli.get_conversations()
                print(format_response(response, verbose=True))
                continue
            
            if user_input.lower() == 'new':
                conversation_id = None
                print("Started new conversation")
                continue
            
            # Send message to AI assistant
            response = await cli.send_message(user_input, conversation_id)
            
            if "conversation_id" in response:
                conversation_id = response["conversation_id"]
            
            print(format_response(response))
            
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}")


async def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="GNOME AI Assistant CLI")
    parser.add_argument("--socket", default="/tmp/gnome_ai_assistant.sock",
                       help="Unix socket path for the service")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Chat command
    chat_parser = subparsers.add_parser("chat", help="Send a message")
    chat_parser.add_argument("message", help="Message to send")
    chat_parser.add_argument("--conversation-id", help="Conversation ID")
    
    # Interactive command
    interactive_parser = subparsers.add_parser("interactive", help="Interactive chat mode")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Get service status")
    
    # Tools command
    tools_parser = subparsers.add_parser("tools", help="List or execute tools")
    tools_parser.add_argument("--list", action="store_true", help="List available tools")
    tools_parser.add_argument("--execute", help="Tool name to execute")
    tools_parser.add_argument("--parameters", help="Tool parameters as JSON")
    
    # Conversations command
    conv_parser = subparsers.add_parser("conversations", help="Manage conversations")
    conv_parser.add_argument("--list", action="store_true", help="List conversations")
    conv_parser.add_argument("--get", help="Get specific conversation")
    conv_parser.add_argument("--delete", help="Delete conversation")
    
    # Emergency stop command
    stop_parser = subparsers.add_parser("stop", help="Emergency stop the service")
    
    args = parser.parse_args()
    
    # Create CLI interface
    cli = CLIInterface(args.socket)
    
    try:
        if args.command == "chat":
            response = await cli.send_message(args.message, args.conversation_id)
            print(format_response(response, args.verbose))
        
        elif args.command == "interactive":
            await interactive_mode(cli)
        
        elif args.command == "status":
            response = await cli.get_status()
            print(format_response(response, args.verbose))
        
        elif args.command == "tools":
            if args.list or not args.execute:
                response = await cli.list_tools()
                print(format_response(response, args.verbose))
            elif args.execute:
                parameters = {}
                if args.parameters:
                    try:
                        parameters = json.loads(args.parameters)
                    except json.JSONDecodeError as e:
                        print(f"Error parsing parameters JSON: {e}")
                        return 1
                
                response = await cli.execute_tool(args.execute, parameters)
                print(format_response(response, args.verbose))
        
        elif args.command == "conversations":
            if args.list or (not args.get and not args.delete):
                response = await cli.get_conversations()
                print(format_response(response, args.verbose))
            elif args.get:
                response = await cli.get_conversation(args.get)
                print(format_response(response, args.verbose))
            elif args.delete:
                response = await cli.delete_conversation(args.delete)
                print(format_response(response, args.verbose))
        
        elif args.command == "stop":
            response = await cli.emergency_stop()
            print(format_response(response, args.verbose))
        
        else:
            # No command specified, default to interactive mode
            await interactive_mode(cli)
    
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        await cli._close_session()
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
