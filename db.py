import sqlite3
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    level TEXT CHECK(level IN ('newbie', 'known')),
    consent_at TEXT,
    state TEXT NOT NULL DEFAULT 'START',
    crystals INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fact_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    fact_id TEXT NOT NULL,
    is_correct INTEGER NOT NULL DEFAULT 0,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, fact_id)
);

CREATE TABLE IF NOT EXISTS crystals_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS quest_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    step_code TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, step_code)
);

CREATE TABLE IF NOT EXISTS badges (
    code TEXT PRIMARY KEY,
    title TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_badges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    badge_code TEXT NOT NULL,
    awarded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, badge_code)
);

CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    code TEXT NOT NULL,
    reward_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_manual',
    wallet_address TEXT,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tg_id, code)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_or_create_user(tg_id, username=None, first_name=None):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO users (tg_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = datetime('now')
            """,
            (tg_id, username, first_name),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_user(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM users WHERE tg_id = ?", (tg_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_level(tg_id, level):
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE users
            SET level = ?,
                state = 'MENU',
                consent_at = COALESCE(consent_at, datetime('now')),
                updated_at = datetime('now')
            WHERE tg_id = ?
            """,
            (level, tg_id),
        )
        conn.commit()
    finally:
        conn.close()


def is_fact_done(tg_id, fact_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM fact_progress WHERE tg_id = ? AND fact_id = ?",
            (tg_id, fact_id),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def mark_fact_done(tg_id, fact_id, is_correct):
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO fact_progress (tg_id, fact_id, is_correct)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id, fact_id) DO UPDATE SET
                is_correct = excluded.is_correct,
                completed_at = datetime('now')
            """,
            (tg_id, fact_id, int(is_correct)),
        )
        conn.commit()
    finally:
        conn.close()


def count_done_facts(tg_id):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM fact_progress WHERE tg_id = ?",
            (tg_id,),
        ).fetchone()
        return row["cnt"]
    finally:
        conn.close()


def add_crystals(tg_id, amount, reason):
    if amount == 0:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO crystals_ledger (tg_id, amount, reason) VALUES (?, ?, ?)",
            (tg_id, amount, reason),
        )
        conn.execute(
            """
            UPDATE users
            SET crystals = crystals + ?, updated_at = datetime('now')
            WHERE tg_id = ?
            """,
            (amount, tg_id),
        )
        conn.commit()
    finally:
        conn.close()