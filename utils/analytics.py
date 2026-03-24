import hashlib
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

ANALYTICS_ENABLED = os.getenv("ANALYTICS_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
ANALYTICS_DB_PATH = Path(os.getenv("ANALYTICS_DB_PATH", "analytics/analytics.sqlite3"))
ANALYTICS_HASH_SALT = os.getenv("ANALYTICS_HASH_SALT", "change-me")
ANALYTICS_RETENTION_DAYS_RAW = os.getenv("ANALYTICS_RETENTION_DAYS", "30").strip().lower()
ANALYTICS_IP_MODE = os.getenv("ANALYTICS_IP_MODE", "hash").strip().lower()
DEFAULT_RETENTION_DAYS = 30


def analytics_enabled() -> bool:
    return ANALYTICS_ENABLED


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_session_id() -> str:
    if "analytics_session_id" not in st.session_state:
        st.session_state["analytics_session_id"] = str(uuid.uuid4())
    return str(st.session_state["analytics_session_id"])


def ip_value_for_storage(ip_address: str | None) -> str | None:
    if not ip_address:
        return None
    cleaned = str(ip_address).strip()
    if not cleaned:
        return None
    if ANALYTICS_IP_MODE == "off":
        return None
    if ANALYTICS_IP_MODE == "raw":
        return cleaned
    payload = f"{ANALYTICS_HASH_SALT}:{cleaned}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def retention_days() -> int | None:
    if ANALYTICS_RETENTION_DAYS_RAW in {"", "none", "off", "indefinite", "infinite", "forever"}:
        return None
    try:
        return max(1, int(ANALYTICS_RETENTION_DAYS_RAW))
    except ValueError:
        return DEFAULT_RETENTION_DAYS


def header_value(headers, key: str) -> str | None:
    try:
        value = headers.get(key)
    except Exception:  # noqa: BLE001
        return None
    if value is None:
        return None
    return str(value)


def analytics_connection() -> sqlite3.Connection:
    ANALYTICS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ANALYTICS_DB_PATH, timeout=30)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_sessions (
            session_id TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            ip_value TEXT,
            user_agent TEXT,
            locale TEXT,
            timezone TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            session_id TEXT NOT NULL,
            page TEXT NOT NULL,
            url TEXT,
            FOREIGN KEY (session_id) REFERENCES analytics_sessions(session_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analytics_page_views_session_ts
        ON analytics_page_views(session_id, ts)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_analytics_page_views_page_ts
        ON analytics_page_views(page, ts)
        """
    )
    return conn


def run_retention_cleanup(conn: sqlite3.Connection) -> None:
    keep_days = retention_days()
    if keep_days is None:
        return

    now = datetime.now(timezone.utc)
    last_cleanup = conn.execute(
        "SELECT value FROM analytics_meta WHERE key = 'last_cleanup_at'"
    ).fetchone()
    if last_cleanup is not None:
        try:
            if now - datetime.fromisoformat(last_cleanup[0]) < timedelta(hours=24):
                return
        except ValueError:
            pass

    cutoff = (now - timedelta(days=keep_days)).isoformat()
    conn.execute("DELETE FROM analytics_page_views WHERE ts < ?", (cutoff,))
    conn.execute("DELETE FROM analytics_sessions WHERE last_seen < ?", (cutoff,))
    conn.execute(
        """
        INSERT INTO analytics_meta (key, value)
        VALUES ('last_cleanup_at', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (now.isoformat(),),
    )


def track_page_visit(page_name: str) -> None:
    if not analytics_enabled():
        return

    try:
        session_id = get_session_id()
        ctx = st.context
        now_iso = utc_now_iso()
        ip_value = ip_value_for_storage(getattr(ctx, "ip_address", None))
        user_agent = header_value(getattr(ctx, "headers", {}), "user-agent")
        locale = getattr(ctx, "locale", None)
        timezone_name = getattr(ctx, "timezone", None)
        url = str(getattr(ctx, "url", ""))

        with analytics_connection() as conn:
            conn.execute(
                """
                INSERT INTO analytics_sessions (
                    session_id,
                    first_seen,
                    last_seen,
                    ip_value,
                    user_agent,
                    locale,
                    timezone
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    ip_value = COALESCE(excluded.ip_value, analytics_sessions.ip_value),
                    user_agent = COALESCE(excluded.user_agent, analytics_sessions.user_agent),
                    locale = COALESCE(excluded.locale, analytics_sessions.locale),
                    timezone = COALESCE(excluded.timezone, analytics_sessions.timezone)
                """,
                (
                    session_id,
                    now_iso,
                    now_iso,
                    ip_value,
                    user_agent,
                    locale,
                    timezone_name,
                ),
            )

            last_page = st.session_state.get("analytics_last_logged_page")
            if last_page != page_name:
                conn.execute(
                    """
                    INSERT INTO analytics_page_views (ts, session_id, page, url)
                    VALUES (?, ?, ?, ?)
                    """,
                    (now_iso, session_id, page_name, url),
                )
                st.session_state["analytics_last_logged_page"] = page_name

            run_retention_cleanup(conn)
    except Exception:  # noqa: BLE001
        return
