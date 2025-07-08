"""Main service implementation for GNOME AI Assistant."""

import asyncio
import signal
import sys
import os
import socket
from pathlib import Path
from typing import Dict, Any, Optional
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
import uvicorn
from pydantic import BaseModel

from ..utils.logger import get_logger
from .config import get_config, AssistantConfig
from .permissions import PermissionManager, PermissionRequest, PermissionLevel
from .memory import MemoryManager
from .agentic_engine import AgenticEngine
from ..llm.base import BaseLLM, Message
from ..tools.base import ToolRegistry, ToolResponse

logger = get_logger("service")


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    function_calls: Optional[list] = None
    context: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None


class ToolExecutionRequest(BaseModel):
    tool_name: str
    parameters: Dict[str, Any]
    require_permission: bool = True


class PermissionResponse(BaseModel):
    granted: bool
    level: str
    expires_at: Optional[str] = None


class ServiceStatus(BaseModel):
    status: str
    version: str
    uptime: int
    active_connections: int
    llm_status: str
    tools_loaded: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    # Startup
    logger.info("Starting GNOME AI Assistant Service")
    
    # Initialize subsystems
    try:
        service = app.state.service
        await service.initialize()
        logger.info("Service initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down GNOME AI Assistant Service")
    try:
        service = app.state.service
        await service.cleanup()
        logger.info("Service cleanup completed")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")


class AssistantService:
    """Main service class for the AI assistant."""
    
    def __init__(self):
        """Initialize the assistant service."""
        self.config: AssistantConfig = get_config()
        self.app = FastAPI(
            title="GNOME AI Assistant",
            description="AI-powered personal assistant for GNOME desktop",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # Store service reference in app state
        self.app.state.service = self
        
        # Core components
        self.llm_engine: Optional[BaseLLM] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.permission_manager: Optional[PermissionManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.agentic_engine: Optional[AgenticEngine] = None
        
        # Service state
        self.is_initialized = False
        self.start_time = asyncio.get_event_loop().time()
        self.active_connections = set()
        
        # Setup CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
        
        # Setup signal handlers
        self._setup_signal_handlers()
    
    async def initialize(self) -> None:
        """Initialize all subsystems."""
        try:
            logger.info("Initializing subsystems...")
            
            # Initialize permission manager
            self.permission_manager = PermissionManager(
                db_path=self.config.database.sqlite_path
            )
            await self.permission_manager.initialize()
            logger.info("Permission manager initialized")
            
            # Initialize memory manager
            self.memory_manager = MemoryManager(
                sqlite_path=self.config.database.sqlite_path,
                chromadb_path=self.config.database.chromadb_path
            )
            await self.memory_manager.initialize()
            logger.info("Memory manager initialized")
            
            # Initialize tool registry
            self.tool_registry = ToolRegistry()
            await self.tool_registry.initialize()
            logger.info("Tool registry initialized")
            
            # Initialize LLM engine
            await self._initialize_llm()
            logger.info("LLM engine initialized")
            
            # Initialize agentic engine
            self.agentic_engine = AgenticEngine(
                llm_engine=self.llm_engine,
                tool_registry=self.tool_registry,
                permission_manager=self.permission_manager,
                memory_manager=self.memory_manager
            )
            await self.agentic_engine.initialize()
            logger.info("Agentic engine initialized")
            
            self.is_initialized = True
            logger.info("All subsystems initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize subsystems: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup all subsystems."""
        try:
            logger.info("Cleaning up subsystems...")
            
            # Close active WebSocket connections
            for websocket in self.active_connections.copy():
                try:
                    await websocket.close()
                except Exception:
                    pass
            
            # Cleanup subsystems
            if self.agentic_engine:
                await self.agentic_engine.cleanup()
            
            if self.memory_manager:
                await self.memory_manager.cleanup()
            
            if self.permission_manager:
                await self.permission_manager.cleanup()
            
            if self.tool_registry:
                await self.tool_registry.cleanup()
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
    
    async def _initialize_llm(self) -> None:
        """Initialize the LLM engine based on configuration."""
        from ..llm.ollama import OllamaLLM
        from ..llm.openai import OpenAILLM
        from ..llm.anthropic import AnthropicLLM
        
        provider = self.config.llm.provider.lower()
        
        if provider == "ollama":
            self.llm_engine = OllamaLLM(self.config.llm)
        elif provider == "openai":
            self.llm_engine = OpenAILLM(self.config.llm)
        elif provider == "anthropic":
            self.llm_engine = AnthropicLLM(self.config.llm)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
        
        # Test connection
        await self.llm_engine.test_connection()
    
    def _register_routes(self) -> None:
        """Register FastAPI routes."""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "initialized": self.is_initialized}
        
        @self.app.get("/status", response_model=ServiceStatus)
        async def get_status():
            """Get service status."""
            uptime = int(asyncio.get_event_loop().time() - self.start_time)
            
            llm_status = "unknown"
            if self.llm_engine:
                try:
                    await self.llm_engine.test_connection()
                    llm_status = "connected"
                except Exception:
                    llm_status = "disconnected"
            
            tools_loaded = 0
            if self.tool_registry:
                tools_loaded = len(self.tool_registry.tools)
            
            return ServiceStatus(
                status="running" if self.is_initialized else "initializing",
                version="1.0.0",
                uptime=uptime,
                active_connections=len(self.active_connections),
                llm_status=llm_status,
                tools_loaded=tools_loaded
            )
        
        @self.app.post("/chat", response_model=ChatResponse)
        async def chat(request: ChatRequest):
            """Main chat interface."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                # Process the request through the agentic engine
                result = await self.agentic_engine.process_request(
                    user_request=request.message,
                    context=request.context or {}
                )
                
                return ChatResponse(
                    response=result.response,
                    function_calls=result.function_calls,
                    context=result.context,
                    task_id=result.task_id
                )
                
            except Exception as e:
                logger.error(f"Error processing chat request: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/execute_tool", response_model=Dict[str, Any])
        async def execute_tool(request: ToolExecutionRequest):
            """Execute a specific tool."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                result = await self.tool_registry.execute_tool(
                    name=request.tool_name,
                    **request.parameters
                )
                
                return {
                    "success": result.success,
                    "result": result.result,
                    "error": result.error,
                    "requires_permission": result.requires_permission
                }
                
            except Exception as e:
                logger.error(f"Error executing tool: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/tools")
        async def get_tools():
            """Get available tools."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            return {
                "tools": self.tool_registry.get_tool_schemas(),
                "count": len(self.tool_registry.tools)
            }
        
        @self.app.post("/permissions", response_model=PermissionResponse)
        async def handle_permission(request: PermissionRequest):
            """Handle permission requests."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                level = await self.permission_manager.request_permission(request)
                
                return PermissionResponse(
                    granted=level != PermissionLevel.DENY,
                    level=level.value,
                    expires_at=None  # TODO: Implement expiration
                )
                
            except Exception as e:
                logger.error(f"Error handling permission request: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time communication."""
            await websocket.accept()
            self.active_connections.add(websocket)
            logger.info("WebSocket connection established")
            
            try:
                while True:
                    # Receive message
                    data = await websocket.receive_json()
                    
                    # Process based on message type
                    message_type = data.get("type", "chat")
                    
                    if message_type == "chat":
                        # Handle chat message
                        result = await self.agentic_engine.process_request(
                            user_request=data.get("message", ""),
                            context=data.get("context", {})
                        )
                        
                        await websocket.send_json({
                            "type": "response",
                            "response": result.response,
                            "function_calls": result.function_calls,
                            "context": result.context,
                            "task_id": result.task_id
                        })
                    
                    elif message_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    
            except WebSocketDisconnect:
                logger.info("WebSocket connection closed")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            finally:
                self.active_connections.discard(websocket)
        
        @self.app.get("/conversations")
        async def get_conversations():
            """Get conversation history."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                conversations = await self.memory_manager.get_conversations()
                return {"conversations": conversations}
            except Exception as e:
                logger.error(f"Error getting conversations: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/conversations/{conversation_id}")
        async def get_conversation(conversation_id: str):
            """Get specific conversation."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                conversation = await self.memory_manager.get_conversation(conversation_id)
                if not conversation:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                return conversation
            except Exception as e:
                logger.error(f"Error getting conversation {conversation_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.delete("/conversations/{conversation_id}")
        async def delete_conversation(conversation_id: str):
            """Delete a conversation."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                success = await self.memory_manager.delete_conversation(conversation_id)
                if not success:
                    raise HTTPException(status_code=404, detail="Conversation not found")
                return {"success": True, "message": "Conversation deleted"}
            except Exception as e:
                logger.error(f"Error deleting conversation {conversation_id}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/voice/synthesize")
        async def synthesize_speech(request: dict):
            """Synthesize speech from text."""
            if not self.is_initialized:
                raise HTTPException(status_code=503, detail="Service not initialized")
            
            try:
                # Import voice interface
                from ..interfaces.voice import VoiceInterface
                voice = VoiceInterface()
                
                text = request.get("text", "")
                if not text:
                    raise HTTPException(status_code=400, detail="Text is required")
                
                audio_data = await voice.synthesize_speech(text)
                return {"audio_data": audio_data, "format": "wav"}
            except Exception as e:
                logger.error(f"Error synthesizing speech: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/emergency/stop")
        async def emergency_stop():
            """Emergency stop all operations."""
            try:
                # Cancel all active tasks
                if self.agentic_engine:
                    await self.agentic_engine.emergency_stop()
                
                # Clear active connections
                for websocket in self.active_connections.copy():
                    try:
                        await websocket.close()
                    except Exception:
                        pass
                
                logger.warning("Emergency stop executed")
                return {"success": True, "message": "Emergency stop executed"}
            except Exception as e:
                logger.error(f"Error during emergency stop: {e}")
                raise HTTPException(status_code=500, detail=str(e))
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown")
            asyncio.create_task(self._graceful_shutdown())
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    async def _graceful_shutdown(self) -> None:
        """Perform graceful shutdown."""
        logger.info("Starting graceful shutdown...")
        
        # Stop accepting new connections
        # (This would be handled by uvicorn in a real deployment)
        
        # Cleanup
        await self.cleanup()
        
        # Exit
        sys.exit(0)
    
    async def start(self) -> None:
        """Start the FastAPI server."""
        # Ensure socket directory exists and is writable
        socket_path = Path(self.config.service.socket_path)
        socket_dir = socket_path.parent
        socket_dir.mkdir(parents=True, exist_ok=True)
        
        # Remove existing socket file if it exists
        if socket_path.exists():
            try:
                socket_path.unlink()
            except OSError as e:
                logger.error(f"Failed to remove existing socket: {e}")
                raise
        
        # Configure uvicorn
        config = uvicorn.Config(
            app=self.app,
            uds=str(socket_path),
            log_level=self.config.service.log_level.lower(),
            access_log=True,
            loop="asyncio"
        )
        
        # Create and start server
        server = uvicorn.Server(config)
        
        logger.info(f"Starting server on Unix socket: {socket_path}")
        await server.serve()


# Convenience function for testing
async def create_test_service() -> AssistantService:
    """Create a service instance for testing."""
    service = AssistantService()
    await service.initialize()
    return service
