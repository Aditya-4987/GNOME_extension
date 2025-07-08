"""
Web interface for GNOME AI Assistant.

This module provides a web-based interface using FastAPI
for browser-based interaction with the AI assistant.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

from ..core.service import AIAssistantService
from ..utils.logger import get_logger

logger = get_logger(__name__)


class WebInterface:
    """Web interface for the AI assistant."""
    
    def __init__(self, service: AIAssistantService, host: str = "localhost", port: int = 8080):
        self.service = service
        self.host = host
        self.port = port
        
        # Create FastAPI app
        self.app = FastAPI(
            title="GNOME AI Assistant Web Interface",
            description="Web-based interface for GNOME AI Assistant",
            version="1.0.0"
        )
        
        # WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Setup routes
        self._setup_routes()
        
        # Setup static files and templates
        self._setup_static_files()
    
    def _setup_static_files(self):
        """Setup static files and templates."""
        # In a real implementation, you would have actual static files
        # For now, we'll create the HTML inline
        pass
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def get_index(request: Request):
            """Serve the main web interface."""
            html_content = self._get_main_html()
            return HTMLResponse(content=html_content)
        
        @self.app.get("/api/status")
        async def get_status():
            """Get service status."""
            try:
                status = await self.service.get_status()
                return status
            except Exception as e:
                logger.error(f"Error getting status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/tools")
        async def get_tools():
            """Get available tools."""
            try:
                tools = await self.service.list_tools()
                return {"tools": tools}
            except Exception as e:
                logger.error(f"Error getting tools: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations")
        async def get_conversations():
            """Get conversations."""
            try:
                conversations = await self.service.get_conversations()
                return conversations
            except Exception as e:
                logger.error(f"Error getting conversations: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/conversations/{conversation_id}")
        async def get_conversation(conversation_id: str):
            """Get specific conversation."""
            try:
                conversation = await self.service.get_conversation(conversation_id)
                return conversation
            except Exception as e:
                logger.error(f"Error getting conversation {conversation_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time chat."""
            await self.manager.connect(websocket)
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_json()
                    
                    # Process message
                    response = await self._process_websocket_message(data)
                    
                    # Send response back
                    await websocket.send_json(response)
                    
            except WebSocketDisconnect:
                self.manager.disconnect(websocket)
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                await websocket.send_json({"error": str(e)})
                self.manager.disconnect(websocket)
    
    async def _process_websocket_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a WebSocket message."""
        try:
            message_type = data.get("type", "chat")
            
            if message_type == "chat":
                message = data.get("message", "")
                conversation_id = data.get("conversation_id")
                
                # Send to AI assistant
                response = await self.service.process_message(message, conversation_id)
                
                return {
                    "type": "chat_response",
                    "response": response
                }
            
            elif message_type == "tool_execute":
                tool_name = data.get("tool_name", "")
                parameters = data.get("parameters", {})
                
                # Execute tool
                result = await self.service.execute_tool(tool_name, parameters)
                
                return {
                    "type": "tool_result",
                    "result": result
                }
            
            elif message_type == "status":
                status = await self.service.get_status()
                
                return {
                    "type": "status",
                    "status": status
                }
            
            else:
                return {
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                }
                
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
            return {
                "type": "error",
                "error": str(e)
            }
    
    def _get_main_html(self) -> str:
        """Get the main HTML page."""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GNOME AI Assistant</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
            display: flex;
            height: 100vh;
        }
        
        .sidebar {
            width: 300px;
            background: white;
            border-right: 1px solid #ddd;
            padding: 20px;
            overflow-y: auto;
        }
        
        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .chat-container {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: white;
            margin: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .input-container {
            padding: 20px;
            background: white;
            border-top: 1px solid #ddd;
            display: flex;
            gap: 10px;
        }
        
        .message {
            margin-bottom: 15px;
            padding: 10px 15px;
            border-radius: 10px;
            max-width: 70%;
        }
        
        .message.user {
            background: #007AFF;
            color: white;
            margin-left: auto;
        }
        
        .message.assistant {
            background: #f0f0f0;
            color: #333;
        }
        
        .message.error {
            background: #FF3B30;
            color: white;
        }
        
        input[type="text"] {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 16px;
        }
        
        button {
            padding: 10px 20px;
            background: #007AFF;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        
        button:hover {
            background: #0056CC;
        }
        
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .status {
            padding: 10px;
            margin-bottom: 20px;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .status.connected {
            background: #D1F2EB;
            color: #00695C;
        }
        
        .status.disconnected {
            background: #FADBD8;
            color: #B71C1C;
        }
        
        .tools-section {
            margin-top: 20px;
        }
        
        .tool-item {
            padding: 8px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .tool-item:hover {
            background: #e9ecef;
        }
        
        h3 {
            margin-top: 0;
            color: #333;
        }
        
        .conversation-list {
            list-style: none;
            padding: 0;
        }
        
        .conversation-item {
            padding: 8px;
            margin: 5px 0;
            background: #f8f9fa;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .conversation-item:hover {
            background: #e9ecef;
        }
        
        .conversation-item.active {
            background: #007AFF;
            color: white;
        }
    </style>
</head>
<body>
    <div class="sidebar">
        <h3>GNOME AI Assistant</h3>
        
        <div id="status" class="status disconnected">
            Connecting...
        </div>
        
        <div class="tools-section">
            <h4>Available Tools</h4>
            <div id="tools-list">
                Loading tools...
            </div>
        </div>
        
        <div class="conversations-section">
            <h4>Conversations</h4>
            <button onclick="newConversation()">New Conversation</button>
            <ul id="conversations-list" class="conversation-list">
                Loading conversations...
            </ul>
        </div>
    </div>
    
    <div class="main-content">
        <div id="chat-container" class="chat-container">
            <div class="message assistant">
                <strong>AI Assistant:</strong> Hello! I'm your GNOME AI Assistant. How can I help you today?
            </div>
        </div>
        
        <div class="input-container">
            <input type="text" id="message-input" placeholder="Type your message..." onkeypress="handleKeyPress(event)">
            <button onclick="sendMessage()" id="send-button">Send</button>
        </div>
    </div>
    
    <script>
        let ws = null;
        let currentConversationId = null;
        let isConnected = false;
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                isConnected = true;
                updateStatus('Connected', 'connected');
                loadTools();
                loadConversations();
            };
            
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
            
            ws.onclose = function() {
                isConnected = false;
                updateStatus('Disconnected', 'disconnected');
                // Try to reconnect after 5 seconds
                setTimeout(connectWebSocket, 5000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
                updateStatus('Connection Error', 'disconnected');
            };
        }
        
        function updateStatus(text, className) {
            const status = document.getElementById('status');
            status.textContent = text;
            status.className = `status ${className}`;
        }
        
        function handleWebSocketMessage(data) {
            if (data.type === 'chat_response') {
                addMessage('assistant', data.response.message || JSON.stringify(data.response));
                if (data.response.conversation_id) {
                    currentConversationId = data.response.conversation_id;
                }
            } else if (data.type === 'tool_result') {
                addMessage('assistant', `Tool result: ${JSON.stringify(data.result, null, 2)}`);
            } else if (data.type === 'error') {
                addMessage('error', `Error: ${data.error}`);
            }
        }
        
        function sendMessage() {
            const input = document.getElementById('message-input');
            const message = input.value.trim();
            
            if (!message || !isConnected) return;
            
            // Add user message to chat
            addMessage('user', message);
            
            // Send to WebSocket
            ws.send(JSON.stringify({
                type: 'chat',
                message: message,
                conversation_id: currentConversationId
            }));
            
            // Clear input
            input.value = '';
            
            // Disable send button temporarily
            const sendButton = document.getElementById('send-button');
            sendButton.disabled = true;
            setTimeout(() => {
                sendButton.disabled = false;
            }, 1000);
        }
        
        function addMessage(type, content) {
            const container = document.getElementById('chat-container');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${type}`;
            
            const prefix = type === 'user' ? 'You: ' : 
                          type === 'assistant' ? 'AI Assistant: ' : 
                          type === 'error' ? 'Error: ' : '';
            
            messageDiv.innerHTML = `<strong>${prefix}</strong>${content}`;
            container.appendChild(messageDiv);
            
            // Scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
        
        function loadTools() {
            fetch('/api/tools')
                .then(response => response.json())
                .then(data => {
                    const toolsList = document.getElementById('tools-list');
                    if (data.tools && data.tools.length > 0) {
                        toolsList.innerHTML = data.tools.map(tool => 
                            `<div class="tool-item" onclick="showToolInfo('${tool.name}')">
                                ${tool.name}: ${tool.description}
                            </div>`
                        ).join('');
                    } else {
                        toolsList.innerHTML = 'No tools available';
                    }
                })
                .catch(error => {
                    console.error('Error loading tools:', error);
                    document.getElementById('tools-list').innerHTML = 'Error loading tools';
                });
        }
        
        function loadConversations() {
            fetch('/api/conversations')
                .then(response => response.json())
                .then(data => {
                    const conversationsList = document.getElementById('conversations-list');
                    if (data.conversations && data.conversations.length > 0) {
                        conversationsList.innerHTML = data.conversations.map(conv => 
                            `<li class="conversation-item" onclick="loadConversation('${conv.id}')">
                                ${conv.title || conv.id.substring(0, 8)}... (${conv.message_count} messages)
                            </li>`
                        ).join('');
                    } else {
                        conversationsList.innerHTML = '<li>No conversations</li>';
                    }
                })
                .catch(error => {
                    console.error('Error loading conversations:', error);
                    document.getElementById('conversations-list').innerHTML = '<li>Error loading conversations</li>';
                });
        }
        
        function showToolInfo(toolName) {
            addMessage('assistant', `Tool: ${toolName} - Click to get more information about this tool.`);
        }
        
        function loadConversation(conversationId) {
            currentConversationId = conversationId;
            
            // Clear current chat
            const container = document.getElementById('chat-container');
            container.innerHTML = '';
            
            // Load conversation messages
            fetch(`/api/conversations/${conversationId}`)
                .then(response => response.json())
                .then(data => {
                    if (data.messages) {
                        data.messages.forEach(msg => {
                            addMessage(msg.role === 'user' ? 'user' : 'assistant', msg.content);
                        });
                    }
                })
                .catch(error => {
                    console.error('Error loading conversation:', error);
                    addMessage('error', 'Error loading conversation');
                });
            
            // Update active conversation in UI
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
            event.target.classList.add('active');
        }
        
        function newConversation() {
            currentConversationId = null;
            
            // Clear current chat
            const container = document.getElementById('chat-container');
            container.innerHTML = '';
            addMessage('assistant', 'Hello! I\'m your GNOME AI Assistant. How can I help you today?');
            
            // Clear active conversation
            document.querySelectorAll('.conversation-item').forEach(item => {
                item.classList.remove('active');
            });
        }
        
        // Initialize connection when page loads
        window.onload = function() {
            connectWebSocket();
        };
    </script>
</body>
</html>
        """
    
    async def start(self):
        """Start the web interface server."""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        
        logger.info(f"Starting web interface on http://{self.host}:{self.port}")
        await server.serve()


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected clients."""
        if self.active_connections:
            message_json = json.dumps(message)
            for connection in self.active_connections[:]:  # Copy list to avoid modification during iteration
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.error(f"Error broadcasting to WebSocket: {e}")
                    self.disconnect(connection)
