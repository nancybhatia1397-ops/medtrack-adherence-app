"""
database.py – SQLite schema initialisation and low-level query helpers.
All higher-level logic lives in the feature modules.
"""
import sqlite3
import contextlib
from config import DB_PATH


# ── Connection factory ────────────────────────────────────────────────────────

@contextlib.contextmanager
def get_connection():
    """Yield a thread-safe SQLite connection with WAL mode enabled."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema initialisation ─────────────────────────────────────────────────────

def init_db():
    """Create all tables if they do not already exist."""
    with get_connection() as conn:
        conn.executescript("""
        -- Users (patients, caregivers, doctors)
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            full_name     TEXT    NOT NULL,
            role          TEXT    NOT NULL CHECK(role IN ('patient','caregiver','doctor')),
            email         TEXT,
            timezone      TEXT    DEFAULT 'UTC',
            created_at    TEXT    DEFAULT (datetime('now'))
        );

        -- Caregiver / doctor → patient relationships
        CREATE TABLE IF NOT EXISTS care_relationships (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            caregiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            patient_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(caregiver_id, patient_id)
        );

        -- Medications assigned to a patient
        CREATE TABLE IF NOT EXISTS medications (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name         TEXT    NOT NULL,
            dosage       TEXT    NOT NULL,
            unit         TEXT    NOT NULL,
            frequency    TEXT    NOT NULL,
            instructions TEXT,
            start_date   TEXT    NOT NULL,
            end_date     TEXT,
            is_active    INTEGER DEFAULT 1,
            created_by   INTEGER REFERENCES users(id),
            created_at   TEXT    DEFAULT (datetime('now'))
        );

        -- Scheduled reminder times for a medication (e.g. "08:00", "20:00")
        CREATE TABLE IF NOT EXISTS reminders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
            reminder_time TEXT    NOT NULL,   -- "HH:MM" 24-h format
            is_active     INTEGER DEFAULT 1
        );

        -- Each time a patient logs a dose
        CREATE TABLE IF NOT EXISTS adherence_logs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            medication_id INTEGER NOT NULL REFERENCES medications(id) ON DELETE CASCADE,
            patient_id    INTEGER NOT NULL REFERENCES users(id)  ON DELETE CASCADE,
            scheduled_for TEXT    NOT NULL,   -- ISO datetime the dose was due
            taken_at      TEXT,               -- ISO datetime actually taken (NULL = missed)
            status        TEXT    NOT NULL CHECK(status IN ('taken','missed','skipped')),
            notes         TEXT,
            logged_at     TEXT    DEFAULT (datetime('now'))
        );

        -- AI-generated insights stored per patient per session
        CREATE TABLE IF NOT EXISTS ai_insights (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            insight    TEXT    NOT NULL,
            created_at TEXT    DEFAULT (datetime('now'))
        );
        """)


# ── Generic helpers ───────────────────────────────────────────────────────────

def fetchall(query: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def fetchone(query: str, params: tuple = ()) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def execute(query: str, params: tuple = ()) -> int:
    """Execute a write query and return lastrowid."""
    with get_connection() as conn:
        cur = conn.execute(query, params)
    return cur.lastrowid
