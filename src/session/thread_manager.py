"""
Multi-Thread Session and State Management for Milestone RAG.
Provides SQLite-backed persistence for isolated conversation threads,
sliding conversational memory windowing, and antecedent scheme resolution.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple
import uuid

import aiosqlite
from pydantic import BaseModel, Field

from src.config import settings, TARGET_SCHEMES
from src.guardrails.intent_router import extract_scheme_entity

logger = logging.getLogger(__name__)


class MessageModel(BaseModel):
    """Pydantic model representing a conversation message."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str
    role: str  # "user", "assistant", "system"
    content: str
    source_url: Optional[str] = None
    intent: Optional[str] = None
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ThreadSummary(BaseModel):
    """Pydantic model summarizing a conversation thread."""
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


PRONOUN_PATTERN = re.compile(
    r"\b(it|its|this\s+fund|the\s+fund|same\s+fund|this\s+scheme|the\s+scheme)\b",
    re.IGNORECASE,
)


class ThreadManager:
    """
    Manages isolated conversation threads and messages stored in SQLite.
    Supports both asynchronous (aiosqlite) and synchronous (sqlite3) operations.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path or settings.database_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_sync_db()

    def _init_sync_db(self) -> None:
        """Initialize SQLite database tables and indexes synchronously."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    intent TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON messages(thread_id);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_threads_updated_at ON threads(updated_at DESC);"
            )
            conn.commit()

    async def init_db(self) -> None:
        """Async database initialization check."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.commit()

    # ------------------------------------------------------------------
    # Asynchronous Thread Operations
    # ------------------------------------------------------------------

    async def create_thread(self, title: Optional[str] = None) -> ThreadSummary:
        """
        Spawn a new isolated conversation thread.
        
        Args:
            title: Optional user-defined thread title.
            
        Returns:
            ThreadSummary of newly created thread.
        """
        thread_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        thread_title = title.strip() if title and title.strip() else f"Conversation {thread_id[:8]}"

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute(
                "INSERT INTO threads (thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?);",
                (thread_id, thread_title, now, now),
            )
            await db.commit()

        return ThreadSummary(
            thread_id=thread_id,
            title=thread_title,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadSummary]:
        """Fetch summary of a specific thread by ID."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT t.thread_id, t.title, t.created_at, t.updated_at,
                       COUNT(m.message_id) AS message_count
                FROM threads t
                LEFT JOIN messages m ON t.thread_id = m.thread_id
                WHERE t.thread_id = ?
                GROUP BY t.thread_id;
                """,
                (thread_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return ThreadSummary(
                thread_id=row["thread_id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"],
            )

    async def list_threads(self) -> List[ThreadSummary]:
        """List all active conversation threads sorted by most recent activity."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT t.thread_id, t.title, t.created_at, t.updated_at,
                       COUNT(m.message_id) AS message_count
                FROM threads t
                LEFT JOIN messages m ON t.thread_id = m.thread_id
                GROUP BY t.thread_id
                ORDER BY t.updated_at DESC;
                """
            )
            rows = await cursor.fetchall()
            return [
                ThreadSummary(
                    thread_id=r["thread_id"],
                    title=r["title"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    message_count=r["message_count"],
                )
                for r in rows
            ]

    async def delete_thread(self, thread_id: str) -> bool:
        """
        Delete a thread and its associated message history.
        
        Args:
            thread_id: Thread ID to delete.
            
        Returns:
            True if deleted, False if thread was not found.
        """
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            cursor = await db.execute("DELETE FROM threads WHERE thread_id = ?;", (thread_id,))
            await db.commit()
            return cursor.rowcount > 0

    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        source_url: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> MessageModel:
        """
        Append a new message to a thread's history and update thread timestamp.
        Auto-generates thread title from first user query if still generic.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            # Ensure thread exists; create if not
            cursor = await db.execute("SELECT title FROM threads WHERE thread_id = ?;", (thread_id,))
            thread_row = await cursor.fetchone()
            if not thread_row:
                initial_title = content[:35] + ("..." if len(content) > 35 else "")
                await db.execute(
                    "INSERT INTO threads (thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?);",
                    (thread_id, initial_title, now, now),
                )
            else:
                # If first user message and title was generic, update with meaningful title
                current_title = thread_row[0]
                if role == "user" and current_title.startswith("Conversation "):
                    new_title = content[:35] + ("..." if len(content) > 35 else "")
                    await db.execute(
                        "UPDATE threads SET title = ?, updated_at = ? WHERE thread_id = ?;",
                        (new_title, now, thread_id),
                    )
                else:
                    await db.execute(
                        "UPDATE threads SET updated_at = ? WHERE thread_id = ?;",
                        (now, thread_id),
                    )

            # Insert message
            await db.execute(
                """
                INSERT INTO messages (message_id, thread_id, role, content, source_url, intent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (message_id, thread_id, role, content, source_url, intent, now),
            )
            await db.commit()

        return MessageModel(
            message_id=message_id,
            thread_id=thread_id,
            role=role,
            content=content,
            source_url=source_url,
            intent=intent,
            created_at=now,
        )

    async def get_thread_history(
        self,
        thread_id: str,
        limit: Optional[int] = None,
    ) -> List[MessageModel]:
        """
        Retrieve chronological message history for a specific thread.
        
        Args:
            thread_id: Target thread ID.
            limit: Optional max messages to return (most recent).
            
        Returns:
            List of MessageModel objects in chronological order.
        """
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            if limit:
                # Select last `limit` messages then order chronologically
                query = """
                    SELECT * FROM (
                        SELECT * FROM messages
                        WHERE thread_id = ?
                        ORDER BY seq DESC
                        LIMIT ?
                    ) ORDER BY seq ASC;
                """
                cursor = await db.execute(query, (thread_id, limit))
            else:
                cursor = await db.execute(
                    "SELECT * FROM messages WHERE thread_id = ? ORDER BY seq ASC;",
                    (thread_id,),
                )
            rows = await cursor.fetchall()
            return [
                MessageModel(
                    message_id=r["message_id"],
                    thread_id=r["thread_id"],
                    role=r["role"],
                    content=r["content"],
                    source_url=r["source_url"],
                    intent=r["intent"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    async def get_recent_conversation_window(
        self,
        thread_id: str,
        max_turns: int = 2,
    ) -> List[MessageModel]:
        """
        Sliding conversational memory window (default: last 2 turns = 4 messages max).
        Preserves immediate conversational context while preventing drift.
        """
        max_messages = max_turns * 2
        return await self.get_thread_history(thread_id, limit=max_messages)

    async def resolve_antecedent_context(
        self,
        query: str,
        thread_id: str,
    ) -> Tuple[str, Optional[str]]:
        """
        Resolve conversational pronouns ("it", "its", "this fund") by inspecting the
        most recent turns in the specific conversation thread.
        
        Args:
            query: Inbound user query.
            thread_id: Active thread ID.
            
        Returns:
            Tuple of (resolved_query_string, resolved_scheme_id).
        """
        # Step 1: Check if the current query directly specifies a scheme
        direct_scheme = extract_scheme_entity(query)
        if direct_scheme:
            # Explicit scheme switch or declaration: no antecedent resolution needed
            return query, direct_scheme

        # Step 2: If no direct scheme, check if the query contains conversational pronouns
        has_pronoun = bool(PRONOUN_PATTERN.search(query))
        if not has_pronoun:
            return query, None

        # Step 3: Inspect prior turns in this specific thread (strictly isolated)
        recent_messages = await self.get_recent_conversation_window(thread_id, max_turns=2)
        if not recent_messages:
            return query, None

        # Look backwards through previous user and assistant messages for a scheme mention
        prior_scheme_id = None
        for msg in reversed(recent_messages):
            # First check if the assistant message had a source_url or scheme entity
            detected = extract_scheme_entity(msg.content)
            if detected:
                prior_scheme_id = detected
                break
            if msg.source_url:
                for s_id, s_meta in TARGET_SCHEMES.items():
                    if s_meta.source_url == msg.source_url:
                        prior_scheme_id = s_id
                        break
                if prior_scheme_id:
                    break

        if not prior_scheme_id or prior_scheme_id not in TARGET_SCHEMES:
            return query, None

        # Substitute pronoun with canonical scheme name
        scheme_meta = TARGET_SCHEMES[prior_scheme_id]
        scheme_name = scheme_meta.scheme_name

        resolved_query = PRONOUN_PATTERN.sub(scheme_name, query, count=1)
        return resolved_query, prior_scheme_id

    # ------------------------------------------------------------------
    # Synchronous Convenience Methods (for testing / CLI)
    # ------------------------------------------------------------------

    def create_thread_sync(self, title: Optional[str] = None) -> ThreadSummary:
        """Synchronous wrapper for create_thread."""
        thread_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        thread_title = title.strip() if title and title.strip() else f"Conversation {thread_id[:8]}"

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute(
                "INSERT INTO threads (thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?);",
                (thread_id, thread_title, now, now),
            )
            conn.commit()

        return ThreadSummary(
            thread_id=thread_id,
            title=thread_title,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    def add_message_sync(
        self,
        thread_id: str,
        role: str,
        content: str,
        source_url: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> MessageModel:
        """Synchronous wrapper for add_message."""
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.execute("SELECT title FROM threads WHERE thread_id = ?;", (thread_id,))
            thread_row = cursor.fetchone()
            if not thread_row:
                initial_title = content[:35] + ("..." if len(content) > 35 else "")
                conn.execute(
                    "INSERT INTO threads (thread_id, title, created_at, updated_at) VALUES (?, ?, ?, ?);",
                    (thread_id, initial_title, now, now),
                )
            else:
                current_title = thread_row[0]
                if role == "user" and current_title.startswith("Conversation "):
                    new_title = content[:35] + ("..." if len(content) > 35 else "")
                    conn.execute(
                        "UPDATE threads SET title = ?, updated_at = ? WHERE thread_id = ?;",
                        (new_title, now, thread_id),
                    )
                else:
                    conn.execute(
                        "UPDATE threads SET updated_at = ? WHERE thread_id = ?;",
                        (now, thread_id),
                    )

            conn.execute(
                """
                INSERT INTO messages (message_id, thread_id, role, content, source_url, intent, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (message_id, thread_id, role, content, source_url, intent, now),
            )
            conn.commit()

        return MessageModel(
            message_id=message_id,
            thread_id=thread_id,
            role=role,
            content=content,
            source_url=source_url,
            intent=intent,
            created_at=now,
        )

    def get_thread_history_sync(
        self,
        thread_id: str,
        limit: Optional[int] = None,
    ) -> List[MessageModel]:
        """Synchronous wrapper for get_thread_history."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if limit:
                query = """
                    SELECT * FROM (
                        SELECT * FROM messages
                        WHERE thread_id = ?
                        ORDER BY seq DESC
                        LIMIT ?
                    ) ORDER BY seq ASC;
                """
                cursor = conn.execute(query, (thread_id, limit))
            else:
                cursor = conn.execute(
                    "SELECT * FROM messages WHERE thread_id = ? ORDER BY seq ASC;",
                    (thread_id,),
                )
            rows = cursor.fetchall()
            return [
                MessageModel(
                    message_id=r["message_id"],
                    thread_id=r["thread_id"],
                    role=r["role"],
                    content=r["content"],
                    source_url=r["source_url"],
                    intent=r["intent"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def delete_thread_sync(self, thread_id: str) -> bool:
        """Synchronous wrapper for delete_thread."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cursor = conn.execute("DELETE FROM threads WHERE thread_id = ?;", (thread_id,))
            conn.commit()
            return cursor.rowcount > 0


# Global singleton instance
thread_manager = ThreadManager()
