"""Memory and context management for GNOME AI Assistant."""

import asyncio
import sqlite3
import json
import pickle
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import hashlib

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False

from ..utils.logger import get_logger
from ..llm.base import Message, MessageRole

logger = get_logger("memory")


@dataclass
class MemoryEntry:
    """Represents a memory entry."""
    id: str
    content: str
    entry_type: str  # conversation, fact, skill, preference
    importance: float  # 0.0 to 1.0
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    metadata: Optional[Dict[str, Any]] = None
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Create from dictionary."""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["last_accessed"] = datetime.fromisoformat(data["last_accessed"])
        return cls(**data)


@dataclass
class ConversationContext:
    """Represents conversation context."""
    session_id: str
    user_id: str
    messages: List[Message]
    start_time: datetime
    last_activity: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def add_message(self, message: Message) -> None:
        """Add message to conversation."""
        self.messages.append(message)
        self.last_activity = datetime.now()
    
    def get_context_window(self, max_messages: int = 20) -> List[Message]:
        """Get recent messages within context window."""
        return self.messages[-max_messages:]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "messages": [msg.to_dict() for msg in self.messages],
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "metadata": self.metadata
        }


class MemoryManager:
    """Manages memory, context, and embeddings for the AI assistant."""
    
    def __init__(self, sqlite_path: str, chromadb_path: str):
        """
        Initialize memory manager.
        
        Args:
            sqlite_path: Path to SQLite database
            chromadb_path: Path to ChromaDB storage
        """
        self.sqlite_path = sqlite_path
        self.chromadb_path = chromadb_path
        
        # Active conversations
        self.conversations: Dict[str, ConversationContext] = {}
        
        # Memory storage
        self.memory_entries: Dict[str, MemoryEntry] = {}
        
        # Vector database
        self.chroma_client = None
        self.memory_collection = None
        
        # Configuration
        self.max_memory_entries = 10000
        self.conversation_timeout = timedelta(hours=24)
        self.memory_cleanup_interval = timedelta(hours=1)
        
        # Ensure directories exist
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        Path(chromadb_path).mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Initialize memory manager."""
        try:
            await self._initialize_sqlite()
            await self._initialize_chromadb()
            await self._load_active_conversations()
            await self._load_memory_entries()
            
            # Start cleanup task
            asyncio.create_task(self._cleanup_task())
            
            logger.info("Memory manager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize memory manager: {e}")
            raise
    
    async def cleanup(self) -> None:
        """Cleanup memory manager resources."""
        try:
            # Save active conversations
            await self._save_conversations()
            
            # Save memory entries
            await self._save_memory_entries()
            
            logger.info("Memory manager cleanup completed")
        except Exception as e:
            logger.error(f"Error during memory manager cleanup: {e}")
    
    async def _initialize_sqlite(self) -> None:
        """Initialize SQLite database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Create conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    last_activity TIMESTAMP NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    function_call TEXT,
                    function_name TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES conversations (session_id)
                )
            """)
            
            # Create memory entries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    content TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    importance REAL NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    last_accessed TIMESTAMP NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    metadata TEXT,
                    embedding BLOB
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_conversations_last_activity ON conversations(last_activity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_type ON memory_entries(entry_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_importance ON memory_entries(importance)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memory_entries_last_accessed ON memory_entries(last_accessed)")
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"SQLite initialization error: {e}")
            raise
    
    async def _initialize_chromadb(self) -> None:
        """Initialize ChromaDB for vector storage."""
        try:
            if not CHROMADB_AVAILABLE:
                logger.warning("ChromaDB not available, vector search will be disabled")
                return
            
            # Initialize ChromaDB client
            self.chroma_client = chromadb.PersistentClient(
                path=self.chromadb_path,
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create memory collection
            self.memory_collection = self.chroma_client.get_or_create_collection(
                name="memory_entries",
                metadata={"description": "AI assistant memory entries"}
            )
            
            logger.info("ChromaDB initialized successfully")
            
        except Exception as e:
            logger.error(f"ChromaDB initialization error: {e}")
            # Continue without vector search
    
    async def _load_active_conversations(self) -> None:
        """Load active conversations from database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Load recent conversations
            cutoff_time = datetime.now() - self.conversation_timeout
            cursor.execute("""
                SELECT session_id, user_id, start_time, last_activity, metadata
                FROM conversations
                WHERE last_activity > ?
                ORDER BY last_activity DESC
                LIMIT 100
            """, (cutoff_time.isoformat(),))
            
            for row in cursor.fetchall():
                session_id, user_id, start_time, last_activity, metadata = row
                
                # Load messages for this conversation
                cursor.execute("""
                    SELECT role, content, function_call, function_name, timestamp, metadata
                    FROM messages
                    WHERE session_id = ?
                    ORDER BY timestamp ASC
                """, (session_id,))
                
                messages = []
                for msg_row in cursor.fetchall():
                    role, content, function_call, function_name, timestamp, msg_metadata = msg_row
                    
                    message = Message(
                        role=MessageRole(role),
                        content=content,
                        function_call=json.loads(function_call) if function_call else None,
                        function_name=function_name,
                        metadata=json.loads(msg_metadata) if msg_metadata else None
                    )
                    messages.append(message)
                
                # Create conversation context
                conversation = ConversationContext(
                    session_id=session_id,
                    user_id=user_id,
                    messages=messages,
                    start_time=datetime.fromisoformat(start_time),
                    last_activity=datetime.fromisoformat(last_activity),
                    metadata=json.loads(metadata) if metadata else None
                )
                
                self.conversations[session_id] = conversation
            
            conn.close()
            logger.info(f"Loaded {len(self.conversations)} active conversations")
            
        except Exception as e:
            logger.error(f"Error loading conversations: {e}")
    
    async def _load_memory_entries(self) -> None:
        """Load memory entries from database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, content, entry_type, importance, created_at, last_accessed, access_count, metadata, embedding
                FROM memory_entries
                ORDER BY importance DESC, last_accessed DESC
                LIMIT ?
            """, (self.max_memory_entries,))
            
            for row in cursor.fetchall():
                id, content, entry_type, importance, created_at, last_accessed, access_count, metadata, embedding = row
                
                # Deserialize embedding if present
                embedding_data = None
                if embedding:
                    try:
                        embedding_data = pickle.loads(embedding)
                    except Exception:
                        pass
                
                memory_entry = MemoryEntry(
                    id=id,
                    content=content,
                    entry_type=entry_type,
                    importance=importance,
                    created_at=datetime.fromisoformat(created_at),
                    last_accessed=datetime.fromisoformat(last_accessed),
                    access_count=access_count,
                    metadata=json.loads(metadata) if metadata else None,
                    embedding=embedding_data
                )
                
                self.memory_entries[id] = memory_entry
            
            conn.close()
            logger.info(f"Loaded {len(self.memory_entries)} memory entries")
            
        except Exception as e:
            logger.error(f"Error loading memory entries: {e}")
    
    async def create_conversation(self, user_id: str, session_id: Optional[str] = None) -> str:
        """
        Create new conversation context.
        
        Args:
            user_id: User identifier
            session_id: Optional session ID (generated if not provided)
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = self._generate_session_id(user_id)
        
        conversation = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            messages=[],
            start_time=datetime.now(),
            last_activity=datetime.now()
        )
        
        self.conversations[session_id] = conversation
        
        # Save to database
        await self._save_conversation(conversation)
        
        logger.info(f"Created new conversation: {session_id} for user: {user_id}")
        return session_id
    
    async def add_message(self, session_id: str, message: Message) -> None:
        """
        Add message to conversation.
        
        Args:
            session_id: Session identifier
            message: Message to add
        """
        if session_id not in self.conversations:
            logger.warning(f"Conversation {session_id} not found")
            return
        
        conversation = self.conversations[session_id]
        conversation.add_message(message)
        
        # Save message to database
        await self._save_message(session_id, message)
        
        # Extract important information for long-term memory
        if message.role == MessageRole.USER and len(message.content) > 50:
            await self._extract_memory_from_message(message)
    
    async def get_conversation_context(self, session_id: str, max_messages: int = 20) -> List[Message]:
        """
        Get conversation context.
        
        Args:
            session_id: Session identifier
            max_messages: Maximum number of messages to return
            
        Returns:
            List of recent messages
        """
        if session_id not in self.conversations:
            return []
        
        conversation = self.conversations[session_id]
        return conversation.get_context_window(max_messages)
    
    async def search_memory(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """
        Search memory entries.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of relevant memory entries
        """
        try:
            # Try vector search first if available
            if self.memory_collection:
                vector_results = await self._vector_search(query, limit)
                if vector_results:
                    return vector_results
            
            # Fallback to text search
            return await self._text_search(query, limit)
            
        except Exception as e:
            logger.error(f"Error searching memory: {e}")
            return []
    
    async def add_memory(self, content: str, entry_type: str = "fact", 
                        importance: float = 0.5, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Add memory entry.
        
        Args:
            content: Memory content
            entry_type: Type of memory (fact, skill, preference, etc.)
            importance: Importance score (0.0 to 1.0)
            metadata: Additional metadata
            
        Returns:
            Memory entry ID
        """
        # Generate ID
        memory_id = self._generate_memory_id(content)
        
        # Create memory entry
        memory_entry = MemoryEntry(
            id=memory_id,
            content=content,
            entry_type=entry_type,
            importance=min(max(importance, 0.0), 1.0),
            created_at=datetime.now(),
            last_accessed=datetime.now(),
            metadata=metadata
        )
        
        # Generate embedding if possible
        if self.memory_collection:
            try:
                memory_entry.embedding = await self._generate_embedding(content)
            except Exception as e:
                logger.warning(f"Failed to generate embedding: {e}")
        
        # Store memory
        self.memory_entries[memory_id] = memory_entry
        
        # Save to database
        await self._save_memory_entry(memory_entry)
        
        # Add to vector database
        if self.memory_collection and memory_entry.embedding:
            try:
                self.memory_collection.add(
                    embeddings=[memory_entry.embedding],
                    documents=[content],
                    metadatas=[{
                        "entry_type": entry_type,
                        "importance": importance,
                        "created_at": memory_entry.created_at.isoformat()
                    }],
                    ids=[memory_id]
                )
            except Exception as e:
                logger.warning(f"Failed to add to vector database: {e}")
        
        logger.info(f"Added memory entry: {memory_id} ({entry_type})")
        return memory_id
    
    async def _vector_search(self, query: str, limit: int) -> List[MemoryEntry]:
        """Search using vector similarity."""
        try:
            if not self.memory_collection:
                return []
            
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                return []
            
            # Search similar entries
            results = self.memory_collection.query(
                query_embeddings=[query_embedding],
                n_results=limit
            )
            
            memory_entries = []
            for memory_id in results["ids"][0]:
                if memory_id in self.memory_entries:
                    entry = self.memory_entries[memory_id]
                    entry.access_count += 1
                    entry.last_accessed = datetime.now()
                    memory_entries.append(entry)
            
            return memory_entries
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
    
    async def _text_search(self, query: str, limit: int) -> List[MemoryEntry]:
        """Search using text matching."""
        query_lower = query.lower()
        matches = []
        
        for entry in self.memory_entries.values():
            if query_lower in entry.content.lower():
                # Update access tracking
                entry.access_count += 1
                entry.last_accessed = datetime.now()
                matches.append(entry)
        
        # Sort by importance and recency
        matches.sort(key=lambda x: (x.importance, x.last_accessed), reverse=True)
        return matches[:limit]
    
    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text."""
        try:
            # This would typically use the LLM provider's embedding endpoint
            # For now, return None to indicate embeddings not available
            # TODO: Integrate with LLM provider embedding API
            return None
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return None
    
    async def _extract_memory_from_message(self, message: Message) -> None:
        """Extract important information from message for long-term memory."""
        try:
            content = message.content
            
            # Simple heuristics for extracting important information
            if any(keyword in content.lower() for keyword in ["remember", "important", "note", "save"]):
                await self.add_memory(
                    content=content,
                    entry_type="conversation",
                    importance=0.7,
                    metadata={"source": "user_message", "timestamp": datetime.now().isoformat()}
                )
        
        except Exception as e:
            logger.error(f"Error extracting memory from message: {e}")
    
    def _generate_session_id(self, user_id: str) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        data = f"{user_id}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def _generate_memory_id(self, content: str) -> str:
        """Generate unique memory ID."""
        timestamp = datetime.now().isoformat()
        data = f"{content}:{timestamp}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    async def _save_conversation(self, conversation: ConversationContext) -> None:
        """Save conversation to database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO conversations 
                (session_id, user_id, start_time, last_activity, message_count, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                conversation.session_id,
                conversation.user_id,
                conversation.start_time.isoformat(),
                conversation.last_activity.isoformat(),
                len(conversation.messages),
                json.dumps(conversation.metadata) if conversation.metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
    
    async def _save_message(self, session_id: str, message: Message) -> None:
        """Save message to database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO messages 
                (session_id, role, content, function_call, function_name, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id,
                message.role.value,
                message.content,
                json.dumps(message.function_call) if message.function_call else None,
                message.function_name,
                datetime.now().isoformat(),
                json.dumps(message.metadata) if message.metadata else None
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving message: {e}")
    
    async def _save_memory_entry(self, entry: MemoryEntry) -> None:
        """Save memory entry to database."""
        try:
            conn = sqlite3.connect(self.sqlite_path)
            cursor = conn.cursor()
            
            # Serialize embedding
            embedding_blob = None
            if entry.embedding:
                embedding_blob = pickle.dumps(entry.embedding)
            
            cursor.execute("""
                INSERT OR REPLACE INTO memory_entries 
                (id, content, entry_type, importance, created_at, last_accessed, access_count, metadata, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.content,
                entry.entry_type,
                entry.importance,
                entry.created_at.isoformat(),
                entry.last_accessed.isoformat(),
                entry.access_count,
                json.dumps(entry.metadata) if entry.metadata else None,
                embedding_blob
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving memory entry: {e}")
    
    async def _save_conversations(self) -> None:
        """Save all active conversations."""
        for conversation in self.conversations.values():
            await self._save_conversation(conversation)
    
    async def _save_memory_entries(self) -> None:
        """Save all memory entries."""
        for entry in self.memory_entries.values():
            await self._save_memory_entry(entry)
    
    async def _cleanup_task(self) -> None:
        """Background cleanup task."""
        while True:
            try:
                await asyncio.sleep(self.memory_cleanup_interval.total_seconds())
                await self._cleanup_old_data()
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
    
    async def _cleanup_old_data(self) -> None:
        """Cleanup old conversations and memory entries."""
        try:
            cutoff_time = datetime.now() - self.conversation_timeout
            
            # Remove old conversations from memory
            expired_sessions = [
                session_id for session_id, conv in self.conversations.items()
                if conv.last_activity < cutoff_time
            ]
            
            for session_id in expired_sessions:
                del self.conversations[session_id]
            
            if expired_sessions:
                logger.info(f"Cleaned up {len(expired_sessions)} expired conversations")
            
            # Cleanup low-importance memory entries if we have too many
            if len(self.memory_entries) > self.max_memory_entries:
                # Sort by importance and access frequency
                sorted_entries = sorted(
                    self.memory_entries.values(),
                    key=lambda x: (x.importance, x.access_count, x.last_accessed),
                    reverse=True
                )
                
                # Keep only the most important entries
                to_keep = sorted_entries[:self.max_memory_entries]
                to_remove = [entry.id for entry in sorted_entries[self.max_memory_entries:]]
                
                for entry_id in to_remove:
                    del self.memory_entries[entry_id]
                
                logger.info(f"Cleaned up {len(to_remove)} low-importance memory entries")
        
        except Exception as e:
            logger.error(f"Data cleanup error: {e}")
