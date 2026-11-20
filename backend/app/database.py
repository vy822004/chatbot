import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.config import settings


def get_db_path() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite:////"):
        return "/" + url[len("sqlite:////") :]
    elif url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    elif url.startswith("sqlite://"):
        return url[len("sqlite://") :]
    return url


def get_db_connection() -> sqlite3.Connection:
    db_path = get_db_path()
    parent_dir = os.path.dirname(db_path)
    if parent_dir and not os.path.exists(parent_dir):
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages (session_id);
            """
        )
        conn.commit()
    finally:
        conn.close()


def check_db_health() -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM messages LIMIT 1;")
        conn.close()
        return True
    except Exception:
        return False


def session_exists(session_id: str) -> bool:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1;", (session_id,)
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def get_messages_for_llm(session_id: str) -> List[Dict[str, str]]:
    """Returns conversation history formatted for LLM context."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM messages 
            WHERE session_id = ? 
            ORDER BY id ASC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]
    finally:
        conn.close()


def get_session_history(session_id: str) -> Optional[List[Dict[str, Any]]]:
    """Returns stored history for GET /sessions/{session_id}/messages."""
    if not session_exists(session_id):
        return None

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content, metadata FROM messages 
            WHERE session_id = ? 
            ORDER BY id ASC;
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            msg: Dict[str, Any] = {
                "role": row["role"],
                "content": row["content"],
            }
            if row["metadata"]:
                try:
                    meta = json.loads(row["metadata"])
                    msg["metadata"] = meta
                except Exception:
                    pass
            result.append(msg)
        return result
    finally:
        conn.close()


def save_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        meta_json = json.dumps(metadata) if metadata is not None else None
        cursor.execute(
            """
            INSERT INTO messages (session_id, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?);
            """,
            (session_id, role, content, meta_json, now_iso),
        )
        conn.commit()
    finally:
        conn.close()
