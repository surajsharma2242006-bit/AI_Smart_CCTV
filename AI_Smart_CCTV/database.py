"""SQLite persistence layer. All statements use parameterized values."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd

from config import settings


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initialise_database() -> None:
    with connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                people_count INTEGER NOT NULL DEFAULT 0,
                snapshot_path TEXT,
                metadata TEXT
            );
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER,
                created_at TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                snapshot_path TEXT,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                acknowledged_at TEXT,
                FOREIGN KEY(event_id) REFERENCES events(id)
            );
            CREATE TABLE IF NOT EXISTS face_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL UNIQUE,
                consent_at TEXT NOT NULL,
                image_path TEXT NOT NULL,
                encoding_path TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            """
        )


def add_event(event_type: str, severity: str, message: str, people_count: int = 0,
              snapshot_path: Optional[str] = None, metadata: str = "") -> int:
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO events (created_at, event_type, severity, message, people_count, snapshot_path, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(timespec="seconds"), event_type, severity, message,
             people_count, snapshot_path, metadata),
        )
        return int(cursor.lastrowid)


def add_alert(event_id: Optional[int], alert_type: str, severity: str, message: str,
              snapshot_path: Optional[str] = None) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """INSERT INTO alerts (event_id, created_at, alert_type, severity, message, snapshot_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (event_id, datetime.now().isoformat(timespec="seconds"), alert_type, severity, message, snapshot_path),
        )
        return int(cursor.lastrowid)


def acknowledge_alert(alert_id: int) -> None:
    with connection() as conn:
        conn.execute("UPDATE alerts SET acknowledged = 1, acknowledged_at = ? WHERE id = ?", (datetime.now().isoformat(timespec="seconds"), alert_id))


def get_events(start: Optional[date] = None, end: Optional[date] = None, event_type: str = "All") -> pd.DataFrame:
    query = "SELECT * FROM events WHERE 1=1"
    params: list[str] = []
    if start:
        query += " AND date(created_at) >= date(?)"
        params.append(start.isoformat())
    if end:
        query += " AND date(created_at) <= date(?)"
        params.append(end.isoformat())
    if event_type != "All":
        query += " AND event_type = ?"
        params.append(event_type)
    query += " ORDER BY created_at DESC"
    with connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def get_alerts(include_acknowledged: bool = True) -> pd.DataFrame:
    query = "SELECT * FROM alerts"
    if not include_acknowledged:
        query += " WHERE acknowledged = 0"
    query += " ORDER BY acknowledged ASC, created_at DESC"
    with connection() as conn:
        return pd.read_sql_query(query, conn)


def dashboard_metrics() -> dict[str, int]:
    with connection() as conn:
        return {
            "events": conn.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            "registered": conn.execute("SELECT COUNT(*) FROM face_profiles WHERE active = 1").fetchone()[0],
            "unknown": conn.execute("SELECT COUNT(*) FROM events WHERE event_type = 'Unknown face observed'").fetchone()[0],
            "open_alerts": conn.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0").fetchone()[0],
        }


def add_face_profile(name: str, image_path: str, encoding_path: str) -> None:
    with connection() as conn:
        conn.execute(
            "INSERT INTO face_profiles (display_name, consent_at, image_path, encoding_path) VALUES (?, ?, ?, ?)",
            (name, datetime.now().isoformat(timespec="seconds"), image_path, encoding_path),
        )


def get_face_profiles() -> pd.DataFrame:
    with connection() as conn:
        return pd.read_sql_query("SELECT * FROM face_profiles WHERE active = 1 ORDER BY display_name", conn)


def delete_face_profile(profile_id: int) -> tuple[str, str] | None:
    with connection() as conn:
        row = conn.execute("SELECT image_path, encoding_path FROM face_profiles WHERE id = ? AND active = 1", (profile_id,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE face_profiles SET active = 0 WHERE id = ?", (profile_id,))
        return str(row["image_path"]), str(row["encoding_path"])

