"""SQLite persistence for pin collection and search history."""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "pins.db")


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS collection (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            pin_number  TEXT,
            series      TEXT,
            year        TEXT,
            edition_size TEXT,
            image_url   TEXT,
            source      TEXT,
            source_url  TEXT,
            added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes       TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS search_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            search_type TEXT NOT NULL,
            query       TEXT NOT NULL,
            result_count INTEGER DEFAULT 0,
            searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.close()


def add_to_collection(pin_dict: dict) -> int:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO collection (name, pin_number, series, year, edition_size,
           image_url, source, source_url)
           VALUES (:name, :pin_number, :series, :year, :edition_size,
           :image_url, :source, :source_url)""",
        pin_dict,
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def remove_from_collection(pin_id: int) -> bool:
    conn = _connect()
    cur = conn.execute("DELETE FROM collection WHERE id = ?", (pin_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def get_collection() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM collection ORDER BY added_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_in_collection(name: str, pin_number: str, source: str) -> bool:
    conn = _connect()
    row = conn.execute(
        """SELECT 1 FROM collection
           WHERE name = ? AND (pin_number = ? OR (pin_number IS NULL AND ? IS NULL))
           AND source = ? LIMIT 1""",
        (name, pin_number, pin_number, source),
    ).fetchone()
    conn.close()
    return row is not None


def add_search_history(search_type: str, query: str, result_count: int):
    conn = _connect()
    conn.execute(
        "INSERT INTO search_history (search_type, query, result_count) VALUES (?, ?, ?)",
        (search_type, query, result_count),
    )
    conn.commit()
    conn.close()


def get_search_history(limit: int = 50) -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM search_history ORDER BY searched_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_search_history():
    conn = _connect()
    conn.execute("DELETE FROM search_history")
    conn.commit()
    conn.close()
