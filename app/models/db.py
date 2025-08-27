import sqlite3
from pathlib import Path
from typing import Optional
import os

DB_PATH = os.getenv("DB_PATH", "storage/events.sqlite")
Path("storage").mkdir(exist_ok=True, parents=True)

_conn: Optional[sqlite3.Connection] = None

def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn

def init_db():
    conn = get_conn()
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            version TEXT,
            yaml TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS pattern_media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern_id INTEGER,
            kind TEXT DEFAULT 'template',
            filename TEXT,
            mime TEXT,
            width INTEGER,
            height INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            timeframe TEXT,
            threshold REAL DEFAULT 0.7,
            min_vol_usd REAL DEFAULT 30000000,
            active INTEGER DEFAULT 1,
            last_scan_at TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            timeframe TEXT,
            bar_time TIMESTAMP,
            pattern_name TEXT,
            score REAL,
            status TEXT,
            unique_key TEXT,
            payload_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            telegram_msg_id TEXT,
            image_path TEXT
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        '''
    )
    conn.commit()
