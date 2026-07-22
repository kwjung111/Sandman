import os
import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_PATH = os.getenv("DB_PATH", "data/app.db")


@contextmanager
def db_conn():
    """커밋/종료까지 책임지는 커넥션 컨텍스트 (블록 정상 종료 시 커밋)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: 읽기-쓰기 잠금 경합 완화 (이벤트 루프에서 동기 호출되므로 블로킹 최소화)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 3000")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db():
    """테이블 생성 + 그룹이 하나도 없으면 기본 그룹(09:00~18:00) 시드"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with db_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                start_hour INTEGER NOT NULL,
                start_minute INTEGER NOT NULL,
                end_hour INTEGER NOT NULL,
                end_minute INTEGER NOT NULL,
                include_weekends INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS server_groups (
                server_instance_no TEXT PRIMARY KEY,
                group_id INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        count = conn.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
        if count == 0:
            conn.execute(
                "INSERT INTO groups (name, start_hour, start_minute, end_hour, end_minute, include_weekends) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("기본 그룹", 9, 0, 18, 0, 0),
            )
            logger.info("[DB] 기본 그룹 생성됨 (09:00~18:00, 주말 제외)")


def list_groups() -> list[dict]:
    with db_conn() as conn:
        rows = conn.execute("SELECT * FROM groups ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def get_group(group_id: int) -> dict | None:
    with db_conn() as conn:
        row = conn.execute("SELECT * FROM groups WHERE id = ?", (group_id,)).fetchone()
        return dict(row) if row else None


def create_group(name: str, start_hour: int, start_minute: int,
                 end_hour: int, end_minute: int, include_weekends: bool) -> dict:
    with db_conn() as conn:
        cur = conn.execute(
            "INSERT INTO groups (name, start_hour, start_minute, end_hour, end_minute, include_weekends) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (name, start_hour, start_minute, end_hour, end_minute, int(include_weekends)),
        )
        new_id = cur.lastrowid
    return get_group(new_id)


def update_group(group_id: int, name: str, start_hour: int, start_minute: int,
                 end_hour: int, end_minute: int, include_weekends: bool) -> dict | None:
    with db_conn() as conn:
        conn.execute(
            "UPDATE groups SET name = ?, start_hour = ?, start_minute = ?, "
            "end_hour = ?, end_minute = ?, include_weekends = ? WHERE id = ?",
            (name, start_hour, start_minute, end_hour, end_minute, int(include_weekends), group_id),
        )
    return get_group(group_id)


def delete_group(group_id: int) -> bool:
    with db_conn() as conn:
        cur = conn.execute("DELETE FROM groups WHERE id = ?", (group_id,))
        return cur.rowcount > 0


def get_setting(key: str, default: str) -> str:
    with db_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with db_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def auto_stop_enabled() -> bool:
    return get_setting("auto_stop_enabled", "1") == "1"


def set_auto_stop_enabled(enabled: bool):
    set_setting("auto_stop_enabled", "1" if enabled else "0")


def get_assignments() -> dict[str, int]:
    """서버 instanceNo -> group_id 매핑"""
    with db_conn() as conn:
        rows = conn.execute("SELECT server_instance_no, group_id FROM server_groups").fetchall()
        return {r["server_instance_no"]: r["group_id"] for r in rows}


def assign_server(server_instance_no: str, group_id: int | None):
    """서버를 그룹에 할당. group_id가 None이면 할당 해제"""
    with db_conn() as conn:
        if group_id is None:
            conn.execute("DELETE FROM server_groups WHERE server_instance_no = ?", (server_instance_no,))
        else:
            conn.execute(
                "INSERT INTO server_groups (server_instance_no, group_id) VALUES (?, ?) "
                "ON CONFLICT(server_instance_no) DO UPDATE SET group_id = excluded.group_id",
                (server_instance_no, group_id),
            )
