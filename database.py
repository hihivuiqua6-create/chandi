"""SQLite database layer for the Telegram Buff Bot."""
import sqlite3
import json
import os
from datetime import date, datetime
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "data/buffbot.db")


def _ensure_db_dir():
    os.makedirs(os.path.dirname(DB_PATH) if os.path.dirname(DB_PATH) else ".", exist_ok=True)


@contextmanager
def get_conn():
    _ensure_db_dir()
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


def init_db():
    _ensure_db_dir()
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            last_name TEXT DEFAULT '',
            is_banned INTEGER DEFAULT 0,
            joined_at TEXT DEFAULT (datetime('now')),
            buff_count_today INTEGER DEFAULT 0,
            last_buff_date TEXT DEFAULT '',
            total_buffs INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS required_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id TEXT NOT NULL UNIQUE,
            group_title TEXT DEFAULT '',
            group_username TEXT DEFAULT '',
            group_link TEXT DEFAULT '',
            added_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS buff_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tiktok_url TEXT DEFAULT '',
            service TEXT DEFAULT '',
            amount INTEGER DEFAULT 0,
            status TEXT DEFAULT 'ok',
            message TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS broadcasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message TEXT NOT NULL,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
        # default settings
        defaults = {
            "bot_token": "",
            "admin_ids": "",
            "buff_api_url": "",
            "daily_limit": "10",
            "admin_password": "admin123",
            "welcome_message": "Chào mừng {name} đến với Bot Buff TikTok! Dùng /buff <link> để buff.",
            "bot_name": "Buff TikTok Bot",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )


# ─── Settings ───────────────────────────────────────────────────────────────

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)
        )


def get_all_settings() -> dict:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def get_admin_ids() -> list[int]:
    raw = get_setting("admin_ids", "")
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


# ─── Users ──────────────────────────────────────────────────────────────────

def upsert_user(user_id: int, username: str = "", first_name: str = "", last_name: str = ""):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name, last_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name
        """, (user_id, username or "", first_name or "", last_name or ""))


def get_user(user_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY joined_at DESC").fetchall()
        return [dict(r) for r in rows]


def ban_user(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))


def unban_user(user_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))


def check_and_increment_buff(user_id: int, limit: int) -> tuple[bool, int]:
    """Returns (allowed, remaining). Resets count if new day."""
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return False, 0
        count = row["buff_count_today"] if row["last_buff_date"] == today else 0
        if count >= limit:
            return False, 0
        new_count = count + 1
        conn.execute(
            "UPDATE users SET buff_count_today=?, last_buff_date=?, total_buffs=total_buffs+1 WHERE user_id=?",
            (new_count, today, user_id)
        )
        return True, limit - new_count


def get_user_daily_remaining(user_id: int, limit: int) -> int:
    today = date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return limit
        count = row["buff_count_today"] if row["last_buff_date"] == today else 0
        return max(0, limit - count)


# ─── Required Groups ────────────────────────────────────────────────────────

def get_required_groups() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM required_groups ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def add_required_group(group_id: str, group_title: str, group_username: str, group_link: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO required_groups (group_id, group_title, group_username, group_link)
            VALUES (?, ?, ?, ?)
        """, (group_id, group_title, group_username, group_link))


def remove_required_group(group_id: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM required_groups WHERE group_id=?", (group_id,))


def remove_required_group_by_db_id(db_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM required_groups WHERE id=?", (db_id,))


# ─── Buff Logs ───────────────────────────────────────────────────────────────

def add_buff_log(user_id: int, tiktok_url: str, service: str, amount: int, status: str, message: str):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO buff_logs (user_id, tiktok_url, service, amount, status, message)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, tiktok_url, service, amount, status, message))


def get_buff_logs(limit: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT bl.*, u.username, u.first_name FROM buff_logs bl LEFT JOIN users u ON bl.user_id=u.user_id ORDER BY bl.created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


# ─── Broadcasts ──────────────────────────────────────────────────────────────

def add_broadcast(message: str, sent_count: int, failed_count: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO broadcasts (message, sent_count, failed_count) VALUES (?, ?, ?)",
            (message, sent_count, failed_count)
        )


def get_broadcasts(limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM broadcasts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


# ─── Stats ───────────────────────────────────────────────────────────────────

def get_stats() -> dict:
    today = date.today().isoformat()
    with get_conn() as conn:
        total_users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        active_today = conn.execute(
            "SELECT COUNT(*) as c FROM users WHERE last_buff_date=?", (today,)
        ).fetchone()["c"]
        buffs_today = conn.execute(
            "SELECT COALESCE(SUM(buff_count_today),0) as c FROM users WHERE last_buff_date=?", (today,)
        ).fetchone()["c"]
        total_buffs = conn.execute("SELECT COALESCE(SUM(total_buffs),0) as c FROM users").fetchone()["c"]
        banned_users = conn.execute("SELECT COUNT(*) as c FROM users WHERE is_banned=1").fetchone()["c"]
        total_groups = conn.execute("SELECT COUNT(*) as c FROM required_groups").fetchone()["c"]
    return {
        "total_users": total_users,
        "active_today": active_today,
        "buffs_today": buffs_today,
        "total_buffs": total_buffs,
        "banned_users": banned_users,
        "total_groups": total_groups,
    }
