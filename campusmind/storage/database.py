"""SQLite connection and idempotent schema management."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS student_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    major TEXT,
    grade TEXT,
    timezone TEXT NOT NULL,
    quiet_hours_start TEXT,
    quiet_hours_end TEXT,
    interests_json TEXT NOT NULL,
    reminder_preferences_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS notices (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    audience_json TEXT NOT NULL,
    published_at TEXT,
    deadline TEXT,
    actions_json TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'normal')),
    source_type TEXT NOT NULL CHECK (source_type IN ('demo', 'document', 'url', 'user_input')),
    source_ref TEXT,
    confidence REAL NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    needs_confirmation INTEGER NOT NULL CHECK (needs_confirmation IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    teacher TEXT,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 1 AND 7),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    location TEXT,
    start_week INTEGER NOT NULL CHECK (start_week >= 1),
    end_week INTEGER NOT NULL CHECK (end_week >= start_week),
    week_pattern TEXT NOT NULL CHECK (week_pattern IN ('all', 'odd', 'even', 'custom')),
    custom_weeks_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_courses_student_weekday
    ON courses(student_id, weekday);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    task_type TEXT NOT NULL CHECK (task_type IN ('registration', 'exam', 'assignment', 'course', 'activity', 'general')),
    priority TEXT NOT NULL CHECK (priority IN ('critical', 'high', 'medium', 'normal')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'cancelled')),
    due_at TEXT,
    source_notice_id TEXT REFERENCES notices(id) ON DELETE SET NULL,
    dedupe_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_dedupe_key ON tasks(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_tasks_student_status_due
    ON tasks(student_id, status, due_at);

CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    trigger_at TEXT NOT NULL,
    channel TEXT NOT NULL CHECK (channel = 'in_app'),
    status TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'skipped', 'failed')),
    sent_at TEXT,
    failure_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_reminders_status_trigger
    ON reminders(status, trigger_at);

CREATE TABLE IF NOT EXISTS rag_sources (
    source_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    published_at TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    expires_at TEXT,
    source_ref TEXT NOT NULL,
    is_demo INTEGER NOT NULL CHECK (is_demo IN (0, 1)),
    content_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL REFERENCES rag_sources(source_id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    search_text TEXT NOT NULL,
    UNIQUE(source_id, position)
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_source ON rag_chunks(source_id);
"""


class SQLiteDatabase:
    """A small connection factory that always enables SQLite foreign keys."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._memory_connection: sqlite3.Connection | None = None

    def _new_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self.path == ":memory:":
            if self._memory_connection is None:
                self._memory_connection = self._new_connection()
            yield self._memory_connection
            return

        connection = self._new_connection()
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.commit()

    def close(self) -> None:
        if self._memory_connection is not None:
            self._memory_connection.close()
            self._memory_connection = None
