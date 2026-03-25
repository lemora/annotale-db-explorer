import hashlib
import ipaddress
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit

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
FORWARDED_IP_HEADER_CANDIDATES = (
    "cf-connecting-ip",
    "true-client-ip",
    "x-real-ip",
    "x-forwarded-for",
    "forwarded",
)


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


def normalized_ip_address(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    # RFC 7239 may wrap IPv6 values in brackets and include a port.
    if cleaned.startswith("[") and "]" in cleaned:
        cleaned = cleaned[1 : cleaned.index("]")]

    try:
        return str(ipaddress.ip_address(cleaned))
    except ValueError:
        return None


def parse_forwarded_header(value: str | None) -> list[str]:
    if not value:
        return []

    addresses: list[str] = []
    for item in value.split(","):
        for part in item.split(";"):
            key, _, raw_value = part.partition("=")
            if key.strip().lower() != "for":
                continue
            candidate = raw_value.strip().strip('"')
            if candidate.lower() == "unknown":
                continue
            normalized = normalized_ip_address(candidate)
            if normalized is not None:
                addresses.append(normalized)
    return addresses


def parse_forwarded_for_header(value: str | None) -> list[str]:
    if not value:
        return []

    addresses: list[str] = []
    for item in value.split(","):
        normalized = normalized_ip_address(item)
        if normalized is not None:
            addresses.append(normalized)
    return addresses


def client_ip_address(ctx) -> str | None:
    headers = getattr(ctx, "headers", {})

    for header_name in FORWARDED_IP_HEADER_CANDIDATES:
        raw_value = header_value(headers, header_name)
        if header_name == "forwarded":
            parsed_values = parse_forwarded_header(raw_value)
        elif header_name == "x-forwarded-for":
            parsed_values = parse_forwarded_for_header(raw_value)
        else:
            parsed_values = [normalized_ip_address(raw_value)] if raw_value else []

        for parsed_value in parsed_values:
            if parsed_value is not None:
                return parsed_value

    return normalized_ip_address(getattr(ctx, "ip_address", None))


def optional_text(value) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def analytics_url_parts(ctx) -> tuple[str, str]:
    base_url = str(getattr(ctx, "url", "") or "")
    params = {}
    try:
        for key, value in st.query_params.items():
            if isinstance(value, list):
                params[key] = [str(item) for item in value]
            else:
                params[key] = str(value)
    except Exception:  # noqa: BLE001
        parts = urlsplit(base_url)
        return parts.path or "", parts.query or ""

    page_path = urlsplit(base_url).path or ""
    query_params = urlencode(params, doseq=True) if params else ""
    return page_path, query_params


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
            page_path TEXT NOT NULL,
            query_params TEXT,
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
        CREATE INDEX IF NOT EXISTS idx_analytics_page_views_path_ts
        ON analytics_page_views(page_path, ts)
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


def track_page_visit() -> None:
    if not analytics_enabled():
        return

    try:
        session_id = get_session_id()
        ctx = st.context
        now_iso = utc_now_iso()
        ip_value = ip_value_for_storage(client_ip_address(ctx))
        user_agent = header_value(getattr(ctx, "headers", {}), "user-agent")
        locale = optional_text(getattr(ctx, "locale", None))
        timezone_name = optional_text(getattr(ctx, "timezone", None))
        page_path, query_params = analytics_url_parts(ctx)
        page_view_key = (page_path, query_params)

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

            last_page_view_key = st.session_state.get("analytics_last_logged_page_view_key")
            if last_page_view_key != page_view_key:
                conn.execute(
                    """
                    INSERT INTO analytics_page_views (
                        ts, session_id, page_path, query_params
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    (now_iso, session_id, page_path, query_params),
                )
                st.session_state["analytics_last_logged_page_view_key"] = page_view_key

            run_retention_cleanup(conn)
    except Exception:  # noqa: BLE001
        return
