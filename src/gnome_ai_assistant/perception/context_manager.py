"""
Context manager for GNOME AI Assistant.

This module manages the contextual information about the user's
current environment, including active applications, recent actions,
and environmental context to provide better AI assistance.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import json

from .screen_reader import ScreenReader, ScreenContent
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContextType(Enum):
    """Types of context information."""
    APPLICATION = "application"
    DOCUMENT = "document"
    WEBSITE = "website"
    FILE_SYSTEM = "file_system"
    SYSTEM_STATE = "system_state"
    USER_ACTION = "user_action"
    TIME_BASED = "time_based"


@dataclass
class ContextItem:
    """A single piece of context information."""
    context_type: ContextType
    data: Dict[str, Any]
    timestamp: float
    confidence: float
    source: str
    expires_at: Optional[float] = None


@dataclass
class ApplicationContext:
    """Context information about an application."""
    name: str
    process_name: str
    window_title: str
    is_active: bool
    last_active_time: float
    documents: List[str] = field(default_factory=list)
    recent_actions: List[str] = field(default_factory=list)


@dataclass
class DocumentContext:
    """Context information about a document or file."""
    file_path: str
    file_type: str
    application: str
    last_modified: float
    content_preview: str
    is_open: bool


@dataclass
class UserActivity:
    """Information about user activity patterns."""
    active_hours: List[int]
    frequent_applications: Dict[str, int]
    common_tasks: List[str]
    work_patterns: Dict[str, Any]


class ContextManager:
    """Manages contextual information for the AI assistant."""
    
    def __init__(self, screen_reader: Optional[ScreenReader] = None):
        self.screen_reader = screen_reader or ScreenReader()
        
        # Context storage
        self._context_items: List[ContextItem] = []
        self._application_contexts: Dict[str, ApplicationContext] = {}
        self._document_contexts: Dict[str, DocumentContext] = {}
        
        # Activity tracking
        self._user_activity = UserActivity(
            active_hours=[],
            frequent_applications={},
            common_tasks=[],
            work_patterns={}
        )
        
        # State tracking
        self._last_active_window = None
        self._last_screen_content: Optional[ScreenContent] = None
        self._context_update_interval = 5.0  # seconds
        self._max_context_items = 1000
        
        # Running state
        self._running = False
        self._update_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the context manager."""
        if not self._running:
            self._running = True
            self._update_task = asyncio.create_task(self._context_update_loop())
            logger.info("Context manager started")
    
    async def stop(self):
        """Stop the context manager."""
        if self._running:
            self._running = False
            if self._update_task:
                self._update_task.cancel()
                try:
                    await self._update_task
                except asyncio.CancelledError:
                    pass
            logger.info("Context manager stopped")
    
    async def _context_update_loop(self):
        """Main context update loop."""
        while self._running:
            try:
                await self._update_context()
                await asyncio.sleep(self._context_update_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in context update loop: {e}")
                await asyncio.sleep(1.0)  # Brief pause on error
    
    async def _update_context(self):
        """Update the current context information."""
        try:
            current_time = time.time()
            
            # Get current screen content
            screen_content = await self.screen_reader.read_screen()
            
            # Update application context
            await self._update_application_context(screen_content, current_time)
            
            # Update document context
            await self._update_document_context(screen_content, current_time)
            
            # Update system state context
            await self._update_system_context(current_time)
            
            # Clean up expired context items
            self._cleanup_expired_context()
            
            # Limit context items to prevent memory growth
            if len(self._context_items) > self._max_context_items:
                # Remove oldest items
                self._context_items = self._context_items[-self._max_context_items:]
            
            self._last_screen_content = screen_content
            
        except Exception as e:
            logger.error(f"Error updating context: {e}")
    
    async def _update_application_context(self, screen_content: ScreenContent, current_time: float):
        """Update application context information."""
        try:
            if screen_content.active_window:
                window_title = screen_content.active_window.name
                
                # Extract application name (simplified)
                app_name = window_title.split(" - ")[-1] if " - " in window_title else window_title
                
                # Update or create application context
                if app_name not in self._application_contexts:
                    self._application_contexts[app_name] = ApplicationContext(
                        name=app_name,
                        process_name="",  # Would need process detection
                        window_title=window_title,
                        is_active=True,
                        last_active_time=current_time
                    )
                else:
                    context = self._application_contexts[app_name]
                    context.window_title = window_title
                    context.is_active = True
                    context.last_active_time = current_time
                
                # Mark other applications as inactive
                for other_app in self._application_contexts:
                    if other_app != app_name:
                        self._application_contexts[other_app].is_active = False
                
                # Track application switching
                if self._last_active_window and self._last_active_window != window_title:
                    self._add_context_item(
                        ContextType.USER_ACTION,
                        {
                            "action": "application_switch",
                            "from": self._last_active_window,
                            "to": window_title
                        },
                        current_time,
                        confidence=0.9,
                        source="window_manager"
                    )
                
                self._last_active_window = window_title
                
                # Update activity statistics
                self._user_activity.frequent_applications[app_name] = \
                    self._user_activity.frequent_applications.get(app_name, 0) + 1
            
        except Exception as e:
            logger.error(f"Error updating application context: {e}")
    
    async def _update_document_context(self, screen_content: ScreenContent, current_time: float):
        """Update document context information."""
        try:
            # Look for document-related information in screen content
            text_elements = [elem for elem in screen_content.elements 
                           if elem.text_content and len(elem.text_content) > 10]
            
            # Try to detect file paths or document names
            for element in text_elements:
                text = element.text_content
                
                # Simple file path detection
                if "/" in text and ("." in text.split("/")[-1]):
                    potential_path = text.strip()
                    
                    if potential_path not in self._document_contexts:
                        self._document_contexts[potential_path] = DocumentContext(
                            file_path=potential_path,
                            file_type=potential_path.split(".")[-1] if "." in potential_path else "",
                            application=screen_content.active_window.name if screen_content.active_window else "",
                            last_modified=current_time,
                            content_preview=text[:200],
                            is_open=True
                        )
                    else:
                        doc_context = self._document_contexts[potential_path]
                        doc_context.last_modified = current_time
                        doc_context.is_open = True
                        doc_context.content_preview = text[:200]
            
        except Exception as e:
            logger.error(f"Error updating document context: {e}")
    
    async def _update_system_context(self, current_time: float):
        """Update system state context."""
        try:
            # Track time-based context
            current_hour = int(time.strftime("%H", time.localtime(current_time)))
            
            if current_hour not in self._user_activity.active_hours:
                self._user_activity.active_hours.append(current_hour)
            
            # Add time-based context item
            self._add_context_item(
                ContextType.TIME_BASED,
                {
                    "hour": current_hour,
                    "day_of_week": time.strftime("%A", time.localtime(current_time)),
                    "date": time.strftime("%Y-%m-%d", time.localtime(current_time))
                },
                current_time,
                confidence=1.0,
                source="system_clock",
                expires_at=current_time + 3600  # Expire after 1 hour
            )
            
        except Exception as e:
            logger.error(f"Error updating system context: {e}")
    
    def _add_context_item(self, context_type: ContextType, data: Dict[str, Any], 
                         timestamp: float, confidence: float, source: str,
                         expires_at: Optional[float] = None):
        """Add a context item to the collection."""
        context_item = ContextItem(
            context_type=context_type,
            data=data,
            timestamp=timestamp,
            confidence=confidence,
            source=source,
            expires_at=expires_at
        )
        
        self._context_items.append(context_item)
    
    def _cleanup_expired_context(self):
        """Remove expired context items."""
        current_time = time.time()
        
        self._context_items = [
            item for item in self._context_items
            if item.expires_at is None or item.expires_at > current_time
        ]
    
    def get_current_context(self) -> Dict[str, Any]:
        """Get the current context summary."""
        current_time = time.time()
        
        # Get recent context items (last 30 minutes)
        recent_threshold = current_time - 1800
        recent_items = [
            item for item in self._context_items
            if item.timestamp > recent_threshold
        ]
        
        # Get active application
        active_app = None
        for app_context in self._application_contexts.values():
            if app_context.is_active:
                active_app = {
                    "name": app_context.name,
                    "window_title": app_context.window_title,
                    "recent_actions": app_context.recent_actions[-5:]  # Last 5 actions
                }
                break
        
        # Get open documents
        open_documents = [
            {
                "path": doc.file_path,
                "type": doc.file_type,
                "application": doc.application,
                "preview": doc.content_preview
            }
            for doc in self._document_contexts.values()
            if doc.is_open and current_time - doc.last_modified < 3600  # Active in last hour
        ]
        
        return {
            "timestamp": current_time,
            "active_application": active_app,
            "open_documents": open_documents,
            "recent_activities": [
                {
                    "type": item.context_type.value,
                    "data": item.data,
                    "timestamp": item.timestamp,
                    "source": item.source
                }
                for item in recent_items[-10:]  # Last 10 activities
            ],
            "user_patterns": {
                "active_hours": list(set(self._user_activity.active_hours)),
                "frequent_apps": dict(sorted(
                    self._user_activity.frequent_applications.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:5])  # Top 5 most used apps
            }
        }
    
    def get_context_for_query(self, query: str) -> Dict[str, Any]:
        """Get relevant context for a specific query."""
        query_lower = query.lower()
        relevant_context = {
            "query": query,
            "relevant_items": [],
            "current_state": self.get_current_context()
        }
        
        # Find context items relevant to the query
        for item in self._context_items[-50:]:  # Check last 50 items
            item_text = json.dumps(item.data).lower()
            
            # Simple relevance scoring based on keyword matches
            relevance_score = 0
            for word in query_lower.split():
                if len(word) > 2 and word in item_text:
                    relevance_score += 1
            
            if relevance_score > 0:
                relevant_context["relevant_items"].append({
                    "type": item.context_type.value,
                    "data": item.data,
                    "timestamp": item.timestamp,
                    "relevance": relevance_score,
                    "source": item.source
                })
        
        # Sort by relevance and timestamp
        relevant_context["relevant_items"].sort(
            key=lambda x: (x["relevance"], x["timestamp"]),
            reverse=True
        )
        
        return relevant_context
    
    def add_user_action(self, action: str, details: Dict[str, Any]):
        """Add a user action to the context."""
        current_time = time.time()
        
        self._add_context_item(
            ContextType.USER_ACTION,
            {
                "action": action,
                "details": details
            },
            current_time,
            confidence=1.0,
            source="user_interface"
        )
        
        # Update application context if relevant
        if "application" in details:
            app_name = details["application"]
            if app_name in self._application_contexts:
                self._application_contexts[app_name].recent_actions.append(action)
                # Keep only last 10 actions
                if len(self._application_contexts[app_name].recent_actions) > 10:
                    self._application_contexts[app_name].recent_actions = \
                        self._application_contexts[app_name].recent_actions[-10:]
    
    def get_application_context(self, app_name: str) -> Optional[ApplicationContext]:
        """Get context for a specific application."""
        return self._application_contexts.get(app_name)
    
    def get_document_context(self, file_path: str) -> Optional[DocumentContext]:
        """Get context for a specific document."""
        return self._document_contexts.get(file_path)
    
    def export_context(self) -> Dict[str, Any]:
        """Export context data for persistence or analysis."""
        return {
            "context_items": [
                {
                    "type": item.context_type.value,
                    "data": item.data,
                    "timestamp": item.timestamp,
                    "confidence": item.confidence,
                    "source": item.source,
                    "expires_at": item.expires_at
                }
                for item in self._context_items
            ],
            "applications": {
                name: {
                    "name": ctx.name,
                    "process_name": ctx.process_name,
                    "window_title": ctx.window_title,
                    "is_active": ctx.is_active,
                    "last_active_time": ctx.last_active_time,
                    "documents": ctx.documents,
                    "recent_actions": ctx.recent_actions
                }
                for name, ctx in self._application_contexts.items()
            },
            "documents": {
                path: {
                    "file_path": ctx.file_path,
                    "file_type": ctx.file_type,
                    "application": ctx.application,
                    "last_modified": ctx.last_modified,
                    "content_preview": ctx.content_preview,
                    "is_open": ctx.is_open
                }
                for path, ctx in self._document_contexts.items()
            },
            "user_activity": {
                "active_hours": self._user_activity.active_hours,
                "frequent_applications": self._user_activity.frequent_applications,
                "common_tasks": self._user_activity.common_tasks,
                "work_patterns": self._user_activity.work_patterns
            }
        }
