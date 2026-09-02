from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.database import get_db_connection

def set_sync_state(key: str, value: str):
    now = datetime.now().isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sync_state (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, str(value), now))
        conn.commit()

def get_sync_state(key: str, default: str = "") -> str:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM sync_state WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default
