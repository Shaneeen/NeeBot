from __future__ import annotations

import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from queue import Empty, LifoQueue
from threading import Lock
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row

from config import Settings

MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


class SimpleConnectionPool:
    def __init__(self, dsn: str, *, max_size: int = 4) -> None:
        self.dsn = dsn
        self.max_size = max_size
        self._idle: LifoQueue[psycopg.Connection] = LifoQueue(maxsize=max_size)
        self._created = 0
        self._lock = Lock()

    def _new_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def acquire(self) -> psycopg.Connection:
        try:
            conn = self._idle.get_nowait()
        except Empty:
            with self._lock:
                if self._created < self.max_size:
                    self._created += 1
                    return self._new_connection()
            conn = self._idle.get()

        if conn.closed:
            with self._lock:
                self._created = max(self._created - 1, 0)
                self._created += 1
            return self._new_connection()
        return conn

    def release(self, conn: psycopg.Connection) -> None:
        if conn.closed:
            with self._lock:
                self._created = max(self._created - 1, 0)
            return
        try:
            self._idle.put_nowait(conn)
        except Exception:
            conn.close()
            with self._lock:
                self._created = max(self._created - 1, 0)

    def close(self) -> None:
        while True:
            try:
                conn = self._idle.get_nowait()
            except Empty:
                break
            conn.close()
        with self._lock:
            self._created = 0


@dataclass
class Database:
    settings: Settings
    pool_size: int = 4

    def __post_init__(self) -> None:
        self._pool = SimpleConnectionPool(
            self.settings.supabase_database_url,
            max_size=self.pool_size,
        )

    @contextmanager
    def connection(self) -> Iterator[psycopg.Connection]:
        conn = self._pool.acquire()
        try:
            yield conn
        except Exception:
            try:
                conn.rollback()
            finally:
                self._pool.release(conn)
            raise
        else:
            self._pool.release(conn)

    def ensure_profile(self, telegram_user_id: int, display_name: str | None) -> dict[str, Any]:
        is_owner = telegram_user_id == self.settings.owner_telegram_user_id
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO profiles (telegram_user_id, display_name, timezone, is_owner, is_approved, approved_at)
                VALUES (%s, %s, %s, %s, %s, CASE WHEN %s THEN NOW() ELSE NULL END)
                ON CONFLICT (telegram_user_id)
                DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    timezone = COALESCE(profiles.timezone, EXCLUDED.timezone),
                    is_owner = profiles.is_owner OR EXCLUDED.is_owner,
                    is_approved = CASE
                        WHEN profiles.is_owner OR EXCLUDED.is_owner THEN TRUE
                        ELSE profiles.is_approved
                    END,
                    approved_at = CASE
                        WHEN profiles.approved_at IS NOT NULL THEN profiles.approved_at
                        WHEN profiles.is_owner OR EXCLUDED.is_owner THEN NOW()
                        ELSE profiles.approved_at
                    END,
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    telegram_user_id,
                    display_name,
                    self.settings.app_timezone,
                    is_owner,
                    is_owner,
                    is_owner,
                ),
            )
            profile = cur.fetchone()
            conn.commit()
            return profile

    def list_pending_profiles(self) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM profiles
                WHERE is_approved = FALSE AND is_owner = FALSE
                ORDER BY created_at ASC
                """
            )
            return list(cur.fetchall())

    def approve_profile(self, owner_telegram_user_id: int, target_telegram_user_id: int) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM profiles
                WHERE telegram_user_id = %s AND is_owner = TRUE
                LIMIT 1
                """,
                (owner_telegram_user_id,),
            )
            owner = cur.fetchone()
            if not owner:
                return None
            cur.execute(
                """
                UPDATE profiles
                SET is_approved = TRUE,
                    approved_at = NOW(),
                    approved_by = %s,
                    updated_at = NOW()
                WHERE telegram_user_id = %s
                RETURNING *
                """,
                (owner["id"], target_telegram_user_id),
            )
            approved = cur.fetchone()
            conn.commit()
            return approved

    def add_todo(self, user_id: str, title: str, due_at: datetime | None = None) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO todos (user_id, title, due_at)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (user_id, title, due_at),
            )
            todo = cur.fetchone()
            conn.commit()
            return todo

    def list_pending_todos(self, user_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM todos
                WHERE user_id = %s
                  AND status IN ('pending', 'in_progress')
                ORDER BY due_at NULLS LAST, created_at ASC
                """,
                (user_id,),
            )
            return list(cur.fetchall())

    def list_todos_for_range(self, user_id: str, start_at: datetime, end_at: datetime) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM todos
                WHERE user_id = %s
                  AND status IN ('pending', 'in_progress')
                  AND due_at >= %s
                  AND due_at < %s
                ORDER BY due_at ASC, created_at ASC
                """,
                (user_id, start_at, end_at),
            )
            return list(cur.fetchall())

    def mark_todo_done(self, user_id: str, todo_ref: str) -> dict[str, Any] | None:
        todo = self.find_todo(user_id, todo_ref)
        if not todo:
            return None
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE todos
                SET status = 'done',
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (todo["id"], user_id),
            )
            updated = cur.fetchone()
            conn.commit()
            return updated

    def find_todo(self, user_id: str, todo_ref: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            if self._looks_like_uuid(todo_ref):
                cur.execute(
                    "SELECT * FROM todos WHERE user_id = %s AND id = %s",
                    (user_id, todo_ref),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM todos
                    WHERE user_id = %s
                    ORDER BY created_at ASC
                    OFFSET %s LIMIT 1
                    """,
                    (user_id, max(int(todo_ref) - 1, 0)),
                )
            return cur.fetchone()

    def upsert_diary_entry(self, user_id: str, content: str, entry_date: date) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE diary_entries
                SET content = %s,
                    updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM diary_entries
                    WHERE user_id = %s AND entry_date = %s
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING *
                """,
                (content, user_id, entry_date),
            )
            entry = cur.fetchone()
            if not entry:
                cur.execute(
                    """
                    INSERT INTO diary_entries (user_id, content, entry_date)
                    VALUES (%s, %s, %s)
                    RETURNING *
                    """,
                    (user_id, content, entry_date),
                )
                entry = cur.fetchone()
            conn.commit()
            return entry

    def get_diary_entry(self, user_id: str, entry_date: date) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM diary_entries
                WHERE user_id = %s AND entry_date = %s
                LIMIT 1
                """,
                (user_id, entry_date),
            )
            return cur.fetchone()

    def upsert_journal_moods(self, user_id: str, mood_labels: list[str], entry_date: date) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE diary_entries
                SET mood_labels = %s,
                    updated_at = NOW()
                WHERE id = (
                    SELECT id
                    FROM diary_entries
                    WHERE user_id = %s AND entry_date = %s
                    ORDER BY created_at ASC
                    LIMIT 1
                )
                RETURNING *
                """,
                (mood_labels, user_id, entry_date),
            )
            entry = cur.fetchone()
            if not entry:
                cur.execute(
                    """
                    INSERT INTO diary_entries (user_id, entry_date, content, mood_labels)
                    VALUES (%s, %s, '', %s)
                    RETURNING *
                    """,
                    (user_id, entry_date, mood_labels),
                )
                entry = cur.fetchone()
            conn.commit()
            return entry

    def add_assignment(self, user_id: str, raw_text: str) -> dict[str, Any]:
        title, due_at = self._parse_title_and_due_date(raw_text)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO assignments (user_id, title, description, due_at)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, title, raw_text, due_at),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def list_active_assignments(self, user_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM assignments
                WHERE user_id = %s
                  AND status NOT IN ('submitted', 'graded', 'cancelled')
                ORDER BY due_at NULLS LAST, created_at ASC
                """,
                (user_id,),
            )
            return list(cur.fetchall())

    def get_assignment(self, user_id: str, assignment_ref: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            if self._looks_like_uuid(assignment_ref):
                cur.execute(
                    "SELECT * FROM assignments WHERE user_id = %s AND id = %s",
                    (user_id, assignment_ref),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM assignments
                    WHERE user_id = %s
                      AND status NOT IN ('submitted', 'graded', 'cancelled')
                    ORDER BY due_at NULLS LAST, created_at ASC
                    OFFSET %s LIMIT 1
                    """,
                    (user_id, max(int(assignment_ref) - 1, 0)),
                )
            return cur.fetchone()

    def delete_assignment(self, user_id: str, assignment_ref: str) -> dict[str, Any] | None:
        assignment = self.get_assignment(user_id, assignment_ref)
        if not assignment:
            return None
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM assignments
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (assignment["id"], user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def add_event(self, user_id: str, raw_text: str) -> dict[str, Any]:
        start_at, end_at, title = self._parse_event_datetime_range(raw_text)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_events (user_id, title, description, start_at, end_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, title, raw_text, start_at, end_at),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def add_brain_dump(self, user_id: str, header: str, content: str) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO brain_dumps (user_id, header, content)
                VALUES (%s, %s, %s)
                RETURNING *
                """,
                (user_id, header, content),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def list_brain_dumps(self, user_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM brain_dumps
                WHERE user_id = %s
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            return list(cur.fetchall())

    def get_brain_dump(self, user_id: str, dump_ref: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            if self._looks_like_uuid(dump_ref):
                cur.execute(
                    "SELECT * FROM brain_dumps WHERE user_id = %s AND id = %s",
                    (user_id, dump_ref),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM brain_dumps
                    WHERE user_id = %s
                    ORDER BY created_at ASC
                    OFFSET %s LIMIT 1
                    """,
                    (user_id, max(int(dump_ref) - 1, 0)),
                )
            return cur.fetchone()

    def update_brain_dump(
        self,
        user_id: str,
        dump_ref: str,
        content: str,
        header: str | None = None,
    ) -> dict[str, Any] | None:
        dump = self.get_brain_dump(user_id, dump_ref)
        if not dump:
            return None
        next_header = header.strip() if header is not None else dump["header"]
        if not next_header:
            next_header = "Untitled"
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE brain_dumps
                SET header = %s,
                    content = %s,
                    updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (next_header, content, dump["id"], user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def delete_brain_dump(self, user_id: str, dump_ref: str) -> dict[str, Any] | None:
        dump = self.get_brain_dump(user_id, dump_ref)
        if not dump:
            return None
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM brain_dumps
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (dump["id"], user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def list_upcoming_events(self, user_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM calendar_events
                WHERE user_id = %s
                  AND COALESCE(end_at, start_at) >= NOW() - INTERVAL '1 day'
                ORDER BY start_at ASC
                LIMIT 20
                """,
                (user_id,),
            )
            return list(cur.fetchall())

    def get_event(self, user_id: str, event_ref: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            if self._looks_like_uuid(event_ref):
                cur.execute(
                    "SELECT * FROM calendar_events WHERE user_id = %s AND id = %s",
                    (user_id, event_ref),
                )
            else:
                cur.execute(
                    """
                    SELECT *
                    FROM calendar_events
                    WHERE user_id = %s
                      AND COALESCE(end_at, start_at) >= NOW() - INTERVAL '1 day'
                    ORDER BY start_at ASC
                    OFFSET %s LIMIT 1
                    """,
                    (user_id, max(int(event_ref) - 1, 0)),
                )
            return cur.fetchone()

    def delete_event(self, user_id: str, event_ref: str) -> dict[str, Any] | None:
        event = self.get_event(user_id, event_ref)
        if not event:
            return None
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM calendar_events
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (event["id"], user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def get_calendar_month(self, user_id: str, month_start: date) -> dict[str, list[dict[str, Any]]]:
        if month_start.month == 12:
            month_end = date(month_start.year + 1, 1, 1)
        else:
            month_end = date(month_start.year, month_start.month + 1, 1)

        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM assignments
                WHERE user_id = %s
                  AND due_at IS NOT NULL
                  AND due_at >= %s
                  AND due_at < %s
                ORDER BY due_at ASC, created_at ASC
                """,
                (
                    user_id,
                    datetime.combine(month_start, time.min, tzinfo=self.settings.tzinfo),
                    datetime.combine(month_end, time.min, tzinfo=self.settings.tzinfo),
                ),
            )
            assignments = list(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM calendar_events
                WHERE user_id = %s
                  AND start_at < %s
                  AND COALESCE(end_at, start_at) >= %s
                ORDER BY start_at ASC, created_at ASC
                """,
                (
                    user_id,
                    datetime.combine(month_end, time.min, tzinfo=self.settings.tzinfo),
                    datetime.combine(month_start, time.min, tzinfo=self.settings.tzinfo),
                ),
            )
            events = list(cur.fetchall())

        return {"assignments": assignments, "events": events}

    def upsert_daily_plan(self, user_id: str, notes: str) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO daily_plans (user_id, plan_date, notes)
                VALUES (%s, CURRENT_DATE, %s)
                ON CONFLICT (user_id, plan_date)
                DO UPDATE SET
                    notes = EXCLUDED.notes,
                    updated_at = NOW()
                RETURNING *
                """,
                (user_id, notes),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def add_habit(self, user_id: str, raw_text: str) -> dict[str, Any]:
        name, target_value, unit = self._parse_habit(raw_text)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO habits (user_id, name, target_value, unit)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, name, target_value, unit),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def list_habits(self, user_id: str) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM habits
                WHERE user_id = %s AND is_active = TRUE
                ORDER BY created_at ASC
                """,
                (user_id,),
            )
            return list(cur.fetchall())

    def track_habit(self, user_id: str, habit_name: str, value: float) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM habits
                WHERE user_id = %s AND LOWER(name) = LOWER(%s) AND is_active = TRUE
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (user_id, habit_name),
            )
            habit = cur.fetchone()
            if not habit:
                return None
            cur.execute(
                """
                INSERT INTO habit_logs (user_id, habit_id, log_date, value)
                VALUES (%s, %s, CURRENT_DATE, %s)
                ON CONFLICT (habit_id, log_date)
                DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                RETURNING *
                """,
                (user_id, habit["id"], value),
            )
            log = cur.fetchone()
            conn.commit()
            return {"habit": habit, "log": log}

    def get_summary_for_date(self, user_id: str, target_date: date) -> dict[str, Any]:
        tz = self.settings.tzinfo
        day_after = target_date + timedelta(days=1)
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM daily_plans
                WHERE user_id = %s AND plan_date = %s
                """,
                (user_id, target_date),
            )
            plan = cur.fetchone()

            cur.execute(
                """
                SELECT *
                FROM todos
                WHERE user_id = %s
                  AND status IN ('pending', 'in_progress')
                  AND (due_at IS NULL OR due_at < %s::date + INTERVAL '1 day')
                ORDER BY due_at NULLS LAST, created_at ASC
                LIMIT 10
                """,
                (user_id, target_date),
            )
            todos = list(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM assignments
                WHERE user_id = %s
                  AND status NOT IN ('submitted', 'graded', 'cancelled')
                ORDER BY due_at NULLS LAST, created_at ASC
                LIMIT 5
                """,
                (user_id,),
            )
            assignments = list(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM calendar_events
                WHERE user_id = %s
                  AND start_at < %s
                  AND COALESCE(end_at, start_at) >= %s
                ORDER BY start_at ASC
                """,
                (
                    user_id,
                    datetime.combine(day_after, time.min, tzinfo=tz),
                    datetime.combine(target_date, time.min, tzinfo=tz),
                ),
            )
            events = list(cur.fetchall())

            cur.execute(
                """
                SELECT *
                FROM diary_entries
                WHERE user_id = %s AND entry_date = %s
                LIMIT 1
                """,
                (user_id, target_date),
            )
            diary_entry = cur.fetchone()

            cur.execute(
                """
                SELECT hl.*, h.name, h.unit
                FROM habit_logs hl
                JOIN habits h ON h.id = hl.habit_id
                WHERE hl.user_id = %s AND hl.log_date = %s
                ORDER BY h.name ASC
                """,
                (user_id, target_date),
            )
            habit_logs = list(cur.fetchall())

        return {
            "date": target_date,
            "plan": plan,
            "todos": todos,
            "assignments": assignments,
            "events": events,
            "diary_entry": diary_entry,
            "habit_logs": habit_logs,
        }

    def list_recent_diary_entries(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM diary_entries
                WHERE user_id = %s
                  AND (content IS NOT NULL AND content != '' OR mood_labels IS NOT NULL AND array_length(mood_labels, 1) > 0)
                ORDER BY entry_date DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return list(cur.fetchall())

    def get_profile_by_telegram_id(self, telegram_user_id: int) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM profiles WHERE telegram_user_id = %s LIMIT 1",
                (telegram_user_id,),
            )
            return cur.fetchone()

    def list_todos_filtered(self, user_id: str, status_filter: str = "active") -> list[dict[str, Any]]:
        if status_filter == "done":
            where = "status = 'done'"
            order = "completed_at DESC NULLS LAST, created_at DESC"
        elif status_filter == "active":
            where = "status IN ('pending', 'in_progress')"
            order = "due_at NULLS LAST, created_at ASC"
        else:
            where = "1=1"
            order = "CASE WHEN status IN ('pending','in_progress') THEN 0 ELSE 1 END, due_at NULLS LAST, created_at ASC"
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT * FROM todos WHERE user_id = %s AND {where} ORDER BY {order} LIMIT 50",
                (user_id,),
            )
            return list(cur.fetchall())

    def delete_todo(self, user_id: str, todo_id: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM todos WHERE id = %s AND user_id = %s RETURNING *",
                (todo_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def reopen_todo(self, user_id: str, todo_id: str) -> dict[str, Any] | None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE todos
                SET status = 'pending', completed_at = NULL, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                RETURNING *
                """,
                (todo_id, user_id),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    def create_event(
        self,
        user_id: str,
        title: str,
        start_at: datetime,
        end_at: datetime | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO calendar_events (user_id, title, description, start_at, end_at)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (user_id, title, description, start_at, end_at),
            )
            row = cur.fetchone()
            conn.commit()
            return row

    @staticmethod
    def _looks_like_uuid(value: str) -> bool:
        return bool(
            re.fullmatch(
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
                value.strip(),
            )
        )

    def _parse_title_and_due_date(self, raw_text: str) -> tuple[str, datetime | None]:
        date_pattern = r"((?:\d{2}-\d{2}(?:-\d{4})?)|(?:\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)|(?:\d{4}-\d{2}-\d{2}))"

        due_match = re.search(rf"\bdue\s+{date_pattern}\b", raw_text, re.IGNORECASE)
        if due_match:
            due_date = self._parse_flexible_date(due_match.group(1))
            due_at = datetime.combine(due_date, time(23, 59), tzinfo=self.settings.tzinfo)
            title = re.sub(
                rf"\bdue\s+{date_pattern}\b",
                "",
                raw_text,
                flags=re.IGNORECASE,
            ).strip(" -")
            return title or raw_text.strip(), due_at

        prefix_match = re.match(rf"^\s*{date_pattern}\s+(.+?)\s*$", raw_text, re.IGNORECASE)
        if prefix_match:
            due_date = self._parse_flexible_date(prefix_match.group(1))
            due_at = datetime.combine(due_date, time(23, 59), tzinfo=self.settings.tzinfo)
            title = prefix_match.group(2).strip()
            return title or raw_text.strip(), due_at

        return raw_text.strip(), None

    def _parse_datetime_prefix(self, raw_text: str) -> tuple[datetime, str]:
        text = raw_text.strip()
        patterns = [
            r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+(\d{2}:\d{2})\s+(.+)$",
            r"^(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+(\d{2}:\d{2})\s+(.+)$",
            r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+(.+)$",
            r"^(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+(.+)$",
        ]

        for index, pattern in enumerate(patterns):
            match = re.match(pattern, text)
            if not match:
                continue
            has_time = index < 2
            raw_date = match.group(1)
            raw_time = match.group(2) if has_time else "09:00"
            title = match.group(3).strip() if has_time else match.group(2).strip()
            parsed_date = self._parse_flexible_date(raw_date)
            parsed = datetime.combine(parsed_date, datetime.strptime(raw_time, "%H:%M").time(), tzinfo=self.settings.tzinfo)
            return parsed, title

        raise ValueError("Expected format: DD-MM[-YYYY] [HH:MM] Title")

    def _parse_event_datetime_range(self, raw_text: str) -> tuple[datetime, datetime | None, str]:
        text = raw_text.strip()
        range_patterns = [
            (
                r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+(\d{2}:\d{2})\s+to\s+"
                r"(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+(\d{2}:\d{2})\s+(.+)$"
            ),
            (
                r"^(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+(\d{2}:\d{2})\s+to\s+"
                r"(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+(\d{2}:\d{2})\s+(.+)$"
            ),
            (
                r"^(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+to\s+"
                r"(\d{4}-\d{2}-\d{2}|\d{2}-\d{2}(?:-\d{4})?)\s+(.+)$"
            ),
            (
                r"^(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+to\s+"
                r"(\d{1,2}\s+[A-Za-z]+(?:\s+\d{4})?)\s+(.+)$"
            ),
        ]

        for pattern in range_patterns:
            match = re.match(pattern, text)
            if not match:
                continue
            if len(match.groups()) == 5:
                start_date = self._parse_flexible_date(match.group(1))
                start_time = datetime.strptime(match.group(2), "%H:%M").time()
                end_date = self._parse_flexible_date(match.group(3))
                end_time = datetime.strptime(match.group(4), "%H:%M").time()
                title = match.group(5).strip()
            else:
                start_date = self._parse_flexible_date(match.group(1))
                start_time = datetime.strptime("09:00", "%H:%M").time()
                end_date = self._parse_flexible_date(match.group(2))
                end_time = datetime.strptime("09:00", "%H:%M").time()
                title = match.group(3).strip()

            start_at = datetime.combine(start_date, start_time, tzinfo=self.settings.tzinfo)
            end_at = datetime.combine(end_date, end_time, tzinfo=self.settings.tzinfo)
            if end_at < start_at:
                raise ValueError("Event range end must be after start")
            return start_at, end_at, title

        start_at, title = self._parse_datetime_prefix(raw_text)
        return start_at, None, title

    def _parse_flexible_date(self, raw_date: str) -> date:
        raw_date = raw_date.strip()
        current_year = datetime.now(self.settings.tzinfo).year

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
            return datetime.strptime(raw_date, "%Y-%m-%d").date()

        if re.fullmatch(r"\d{2}-\d{2}-\d{4}", raw_date):
            return datetime.strptime(raw_date, "%d-%m-%Y").date()

        if re.fullmatch(r"\d{2}-\d{2}", raw_date):
            return datetime.strptime(f"{raw_date}-{current_year}", "%d-%m-%Y").date()

        match = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?", raw_date)
        if match:
            day = int(match.group(1))
            month_name = match.group(2).lower()
            year = int(match.group(3) or current_year)
            month = MONTH_NAME_MAP.get(month_name)
            if not month:
                raise ValueError(f"Unknown month: {month_name}")
            return date(year, month, day)

        raise ValueError(f"Unsupported date: {raw_date}")

    @staticmethod
    def _parse_habit(raw_text: str) -> tuple[str, float | None, str | None]:
        match = re.match(r"^\s*(.+?)\s+(\d+(?:\.\d+)?)\s+(.+?)\s*$", raw_text)
        if not match:
            return raw_text.strip(), None, None
        return match.group(1).strip(), float(match.group(2)), match.group(3).strip()
