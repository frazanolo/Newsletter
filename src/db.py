import sqlite3
from pathlib import Path
from typing import Optional, Iterable, Dict, Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TEXT,
    content TEXT,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_news_published ON news_items(published_at);
CREATE INDEX IF NOT EXISTS idx_news_category ON news_items(category);
"""

def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA)
    return conn

def upsert_item(conn: sqlite3.Connection, item: Dict[str, Any]) -> bool:
    """
    Returns True if inserted, False if already existed.
    """
    try:
        conn.execute(
            """
            INSERT INTO news_items (source, category, title, url, published_at, content, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["source"],
                item["category"],
                item["title"],
                item["url"],
                item.get("published_at"),
                item.get("content"),
                item["inserted_at"],
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def fetch_recent(conn: sqlite3.Connection, since_iso: str) -> list[dict]:
    cur = conn.execute(
        """
        SELECT id, source, category, title, url, published_at, content
        FROM news_items
        WHERE inserted_at >= ?
        ORDER BY inserted_at DESC
        """,
        (since_iso,),
    )
    rows = cur.fetchall()
    keys = ["id","source","category","title","url","published_at","content"]
    return [dict(zip(keys, r)) for r in rows]
