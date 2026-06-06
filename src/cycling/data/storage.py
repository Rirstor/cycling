from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from cycling.data.models import CyclingRecord, FTPConfig, Session

DB_PATH = Path.home() / ".cycling" / "cycling.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                device_name TEXT DEFAULT '',
                ftp_at_time INTEGER DEFAULT 200,
                avg_power REAL,
                normalized_power REAL,
                max_power REAL,
                avg_hr REAL,
                max_hr REAL,
                avg_cadence REAL,
                tss REAL,
                notes TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                power_watts REAL,
                cadence_rpm REAL,
                heart_rate_bpm REAL,
                speed_kph REAL,
                zone INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS ftp_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value_watts INTEGER NOT NULL,
                date_set TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_records_session ON records(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time);
        """)


def create_session(device_name: str, ftp: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (start_time, device_name, ftp_at_time) VALUES (?, ?, ?)",
            (datetime.now().isoformat(), device_name, ftp),
        )
        return cur.lastrowid


def end_session(session_id: int, session: Session) -> None:
    with get_connection() as conn:
        conn.execute(
            """UPDATE sessions SET end_time=?, avg_power=?, normalized_power=?,
               max_power=?, avg_hr=?, max_hr=?, avg_cadence=?, tss=?
               WHERE id=?""",
            (
                datetime.now().isoformat(),
                session.avg_power,
                session.normalized_power,
                session.max_power,
                session.avg_hr,
                session.max_hr,
                session.avg_cadence,
                session.tss,
                session_id,
            ),
        )


def save_record(session_id: int, record: CyclingRecord) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO records (session_id, timestamp, power_watts, cadence_rpm, heart_rate_bpm, speed_kph, zone) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                record.timestamp.isoformat(),
                record.power_watts,
                record.cadence_rpm,
                record.heart_rate_bpm,
                record.speed_kph,
                record.zone,
            ),
        )


def load_sessions(limit: int = 20) -> list[Session]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)
        ).fetchall()
    sessions = []
    for row in rows:
        sessions.append(Session(
            id=row["id"],
            start_time=datetime.fromisoformat(row["start_time"]),
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            device_name=row["device_name"],
            ftp_at_time=row["ftp_at_time"],
            notes=row["notes"] or "",
            _avg_power=row["avg_power"],
            _normalized_power=row["normalized_power"],
            _max_power=row["max_power"],
            _avg_hr=row["avg_hr"],
            _max_hr=row["max_hr"],
            _avg_cadence=row["avg_cadence"],
            _tss=row["tss"],
        ))
    return sessions


def load_session(session_id: int) -> Optional[Session]:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            return None
        record_rows = conn.execute(
            "SELECT * FROM records WHERE session_id=? ORDER BY timestamp", (session_id,)
        ).fetchall()
    records = []
    for r in record_rows:
        records.append(CyclingRecord(
            timestamp=datetime.fromisoformat(r["timestamp"]),
            power_watts=r["power_watts"],
            cadence_rpm=r["cadence_rpm"],
            heart_rate_bpm=r["heart_rate_bpm"],
            speed_kph=r["speed_kph"],
            zone=r["zone"],
        ))
    return Session(
        id=row["id"],
        start_time=datetime.fromisoformat(row["start_time"]),
        end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
        device_name=row["device_name"],
        ftp_at_time=row["ftp_at_time"],
        records=records,
        notes=row["notes"] or "",
    )


def save_ftp(ftp: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO ftp_history (value_watts, date_set) VALUES (?, ?)",
            (ftp, datetime.now().isoformat()),
        )
        conn.execute(
            "UPDATE sessions SET ftp_at_time=? WHERE ftp_at_time IS NULL OR ftp_at_time=200",
            (ftp,),
        )


def load_latest_ftp() -> Optional[FTPConfig]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value_watts, date_set FROM ftp_history ORDER BY date_set DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return FTPConfig(
            value_watts=row["value_watts"],
            date_set=datetime.fromisoformat(row["date_set"]),
        )
