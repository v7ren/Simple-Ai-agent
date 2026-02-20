"""Long-term memory store."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import sqlite3
import json
import os
import threading
import hashlib


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    session_id: str
    content: str
    category: str  # e.g., 'preference', 'fact', 'context'
    importance: float  # 0.0 - 1.0
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None


class LongTermMemoryStore:
    """SQLite-based long-term memory store."""
    
    def __init__(self, db_path: str = "agent_ltm.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._ensure_table()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _ensure_table(self):
        """Ensure memory table exists."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    importance REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    embedding TEXT
                )
            """)
            
            # Index on session_id for fast lookup
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session ON memories(session_id)
            """)
            
            # Index on category for filtering
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category ON memories(category)
            """)
            
            conn.commit()
            conn.close()
    
    def _generate_id(self, content: str, session_id: str) -> str:
        """Generate unique ID for memory entry."""
        hash_input = f"{session_id}:{content}:{datetime.utcnow().isoformat()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def store(
        self,
        session_id: str,
        content: str,
        category: str = "fact",
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """Store a memory entry. Returns the memory ID."""
        memory_id = self._generate_id(content, session_id)
        timestamp = datetime.utcnow()
        
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO memories
                (id, session_id, content, category, importance, timestamp, metadata, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory_id,
                session_id,
                content,
                category,
                importance,
                timestamp.isoformat(),
                json.dumps(metadata or {}),
                json.dumps(embedding) if embedding else None,
            ))
            
            conn.commit()
            conn.close()
        
        return memory_id
    
    def retrieve(
        self,
        session_id: str,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
        since: Optional[datetime] = None,
    ) -> List[MemoryEntry]:
        """Retrieve memories for a session."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Build query
            conditions = ["session_id = ?"]
            params: List[Any] = [session_id]
            
            if category:
                conditions.append("category = ?")
                params.append(category)
            
            if since:
                conditions.append("timestamp > ?")
                params.append(since.isoformat())
            
            if query:
                conditions.append("content LIKE ?")
                params.append(f"%{query}%")
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(f"""
                SELECT * FROM memories
                WHERE {where_clause}
                ORDER BY importance DESC, timestamp DESC
                LIMIT ?
            """, params + [limit])
            
            rows = cursor.fetchall()
            conn.close()
            
            return [self._row_to_entry(row) for row in rows]
    
    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        embedding = json.loads(row["embedding"]) if row["embedding"] else None
        
        return MemoryEntry(
            id=row["id"],
            session_id=row["session_id"],
            content=row["content"],
            category=row["category"],
            importance=row["importance"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=metadata,
            embedding=embedding,
        )
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry. Returns True if deleted."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            conn.close()
        
        return deleted
    
    def clear_session(self, session_id: str) -> int:
        """Clear all memories for a session. Returns count deleted."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM memories WHERE session_id = ?", (session_id,))
            count = cursor.rowcount
            
            conn.commit()
            conn.close()
        
        return count
