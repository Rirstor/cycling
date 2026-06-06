from datetime import datetime

from cycling.data.models import CyclingRecord, FTPConfig, Session
from cycling.data.storage import (
    create_session,
    end_session,
    get_connection,
    init_db,
    load_latest_ftp,
    load_session,
    load_sessions,
    save_ftp,
    save_record,
)


def _setup():
    init_db()
    with get_connection() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM ftp_history")


def test_init_db():
    _setup()
    conn = get_connection()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t["name"] for t in tables}
    assert "sessions" in table_names
    assert "records" in table_names
    assert "ftp_history" in table_names


def test_create_and_end_session():
    _setup()
    session_id = create_session("Test Trainer", 200)
    assert session_id > 0
    records = [
        CyclingRecord(timestamp=datetime.now(), power_watts=150, cadence_rpm=85, heart_rate_bpm=140, zone=2)
        for _ in range(5)
    ]
    for r in records:
        save_record(session_id, r)
    s = Session(
        id=session_id,
        start_time=datetime.now(),
        end_time=datetime.now(),
        device_name="Test Trainer",
        ftp_at_time=200,
        records=records,
    )
    end_session(session_id, s)
    loaded = load_session(session_id)
    assert loaded is not None
    assert loaded.id == session_id
    assert len(loaded.records) == 5


def test_save_and_load_ftp():
    _setup()
    save_ftp(250)
    result = load_latest_ftp()
    assert result is not None
    assert result.value_watts == 250


def test_load_sessions_empty():
    _setup()
    sessions = load_sessions()
    assert len(sessions) == 0


def test_load_sessions_with_data():
    _setup()
    sid = create_session("Trainer A", 200)
    end_session(sid, Session(id=sid, start_time=datetime.now(), end_time=datetime.now(), device_name="Trainer A", ftp_at_time=200))
    sessions = load_sessions()
    assert len(sessions) >= 1
