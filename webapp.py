from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from aiohttp import web

from db import Database
from config import get_settings

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).parent / "miniapp"


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if hasattr(obj, "hex"):
        return str(obj)
    raise TypeError(f"Not serializable: {type(obj)}")


def _json_response(data: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(data, default=_json_default),
        status=status,
        content_type="application/json",
    )


def validate_init_data(init_data: str, bot_token: str) -> dict | None:
    if not init_data:
        return None
    parsed = parse_qs(init_data, keep_blank_values=True)
    params = {k: v[0] for k, v in parsed.items()}

    received_hash = params.pop("hash", None)
    if not received_hash:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        return None

    auth_date = int(params.get("auth_date", "0"))
    if time.time() - auth_date > 86400:
        return None

    return json.loads(params.get("user", "{}"))


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.startswith("/api/"):
        db: Database = request.app["db"]
        bot_token: str = request.app["bot_token"]
        dev_mode: bool = request.app.get("dev_mode", False)
        owner_id: int = request.app.get("owner_telegram_user_id", 0)

        init_data = request.headers.get("X-Telegram-Init-Data", "")
        tg_user = validate_init_data(init_data, bot_token)

        if not tg_user and dev_mode:
            tg_user = {"id": owner_id, "first_name": "Dev"}

        if not tg_user:
            return _json_response({"error": "Unauthorized"}, 401)

        telegram_user_id = tg_user["id"]
        profile = db.get_profile_by_telegram_id(telegram_user_id)
        if not profile or not profile.get("is_approved"):
            return _json_response({"error": "Not approved"}, 403)

        request["profile"] = profile
        request["user_id"] = str(profile["id"])
        request["timezone"] = profile.get("timezone", "Asia/Singapore")

    return await handler(request)


@web.middleware
async def cors_middleware(request: web.Request, handler):
    if request.method == "OPTIONS":
        resp = web.Response(status=204)
    else:
        resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Telegram-Init-Data"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return resp


def _serialize_todo(t: dict) -> dict:
    return {
        "id": str(t["id"]),
        "title": t["title"],
        "status": t["status"],
        "priority": t.get("priority", "normal"),
        "due_at": t["due_at"].isoformat() if t.get("due_at") else None,
        "completed_at": t["completed_at"].isoformat() if t.get("completed_at") else None,
        "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
    }


def _serialize_event(e: dict) -> dict:
    has_time = True
    if e.get("description") == "__NO_TIME__":
        has_time = False
    return {
        "id": str(e["id"]),
        "title": e["title"],
        "start_at": e["start_at"].isoformat() if e.get("start_at") else None,
        "end_at": e["end_at"].isoformat() if e.get("end_at") else None,
        "has_time": has_time,
        "description": e.get("description"),
        "created_at": e["created_at"].isoformat() if e.get("created_at") else None,
    }


def _serialize_assignment(a: dict) -> dict:
    return {
        "id": str(a["id"]),
        "title": a["title"],
        "status": a["status"],
        "due_at": a["due_at"].isoformat() if a.get("due_at") else None,
        "progress_percent": a.get("progress_percent", 0),
        "module_name": a.get("module_name"),
    }


def _serialize_diary(d: dict | None) -> dict | None:
    if not d:
        return None
    return {
        "id": str(d["id"]),
        "entry_date": d["entry_date"].isoformat() if d.get("entry_date") else None,
        "content": d.get("content", ""),
        "mood_labels": d.get("mood_labels") or [],
    }


# ---- route handlers ----

async def handle_summary(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    today = date.today()
    summary = db.get_summary_for_date(user_id, today)

    return _json_response({
        "date": today.isoformat(),
        "todos": [_serialize_todo(t) for t in summary["todos"]],
        "assignments": [_serialize_assignment(a) for a in summary["assignments"]],
        "events": [_serialize_event(e) for e in summary["events"]],
        "journal": _serialize_diary(summary["diary_entry"]),
        "habit_logs": len(summary["habit_logs"]),
    })


async def handle_todos_list(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    status_filter = request.query.get("filter", "active")
    if status_filter not in ("all", "active", "done"):
        status_filter = "active"
    todos = db.list_todos_filtered(user_id, status_filter)
    return _json_response({"todos": [_serialize_todo(t) for t in todos]})


async def handle_todos_create(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return _json_response({"error": "Title is required"}, 400)

    due_at = None
    if body.get("due_at"):
        try:
            due_at = datetime.fromisoformat(body["due_at"])
        except ValueError:
            pass

    todo = db.add_todo(user_id, title, due_at)
    return _json_response({"todo": _serialize_todo(todo)}, 201)


async def handle_todos_update(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    todo_id = request.match_info["id"]
    body = await request.json()
    action = body.get("action", "done")

    if action == "done":
        todo = db.mark_todo_done(user_id, todo_id)
    elif action == "reopen":
        todo = db.reopen_todo(user_id, todo_id)
    else:
        return _json_response({"error": "Invalid action"}, 400)

    if not todo:
        return _json_response({"error": "Not found"}, 404)
    return _json_response({"todo": _serialize_todo(todo)})


async def handle_todos_delete(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    todo_id = request.match_info["id"]
    todo = db.delete_todo(user_id, todo_id)
    if not todo:
        return _json_response({"error": "Not found"}, 404)
    return _json_response({"deleted": True})


async def handle_events_list(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    events = db.list_upcoming_events(user_id)
    return _json_response({"events": [_serialize_event(e) for e in events]})


async def handle_events_create(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    settings = request.app["settings"]
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        return _json_response({"error": "Title is required"}, 400)

    event_date = body.get("date", date.today().isoformat())
    raw_time = (body.get("time") or "").strip()
    has_time = bool(raw_time)
    event_time = raw_time or "09:00"
    try:
        d = date.fromisoformat(event_date)
        t = datetime.strptime(event_time, "%H:%M").time()
        start_at = datetime.combine(d, t, tzinfo=settings.tzinfo)
    except ValueError:
        return _json_response({"error": "Invalid date/time"}, 400)

    description = None if has_time else "__NO_TIME__"
    event = db.create_event(user_id, title, start_at, description=description)
    return _json_response({"event": _serialize_event(event)}, 201)


async def handle_events_delete(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    event_id = request.match_info["id"]
    event = db.delete_event(user_id, event_id)
    if not event:
        return _json_response({"error": "Not found"}, 404)
    return _json_response({"deleted": True})


async def handle_assignments_list(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    assignments = db.list_active_assignments(user_id)
    return _json_response({"assignments": [_serialize_assignment(a) for a in assignments]})


async def handle_journal_get(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    date_str = request.query.get("date", date.today().isoformat())
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        entry_date = date.today()
    entry = db.get_diary_entry(user_id, entry_date)
    recent_entries = db.list_recent_diary_entries(user_id, 10)
    return _json_response({
        "journal": _serialize_diary(entry),
        "entries": [_serialize_diary(e) for e in recent_entries],
    })


async def handle_journal_save(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    body = await request.json()

    date_str = body.get("date", date.today().isoformat())
    try:
        entry_date = date.fromisoformat(date_str)
    except ValueError:
        entry_date = date.today()

    text = body.get("text")
    moods = body.get("moods")

    entry = None
    if text is not None:
        entry = db.upsert_diary_entry(user_id, text, entry_date)
    if moods is not None:
        entry = db.upsert_journal_moods(user_id, moods[:3], entry_date)

    return _json_response({"journal": _serialize_diary(entry)})


def _serialize_dump(d: dict) -> dict:
    return {
        "id": str(d["id"]),
        "header": d["header"],
        "content": d["content"],
        "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
        "updated_at": d["updated_at"].isoformat() if d.get("updated_at") else None,
    }


async def handle_dumps_list(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    dumps = db.list_brain_dumps(user_id)
    return _json_response({"dumps": [_serialize_dump(d) for d in dumps]})


async def handle_dumps_create(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    body = await request.json()
    header = (body.get("header") or "").strip()
    content = (body.get("content") or "").strip()
    if not header:
        return _json_response({"error": "Header is required"}, 400)
    dump = db.add_brain_dump(user_id, header, content)
    return _json_response({"dump": _serialize_dump(dump)}, 201)


async def handle_dumps_update(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    dump_id = request.match_info["id"]
    body = await request.json()
    content = body.get("content", "")
    header = body.get("header")
    dump = db.update_brain_dump(user_id, dump_id, content, header=header)
    if not dump:
        return _json_response({"error": "Not found"}, 404)
    return _json_response({"dump": _serialize_dump(dump)})


async def handle_dumps_delete(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    dump_id = request.match_info["id"]
    dump = db.delete_brain_dump(user_id, dump_id)
    if not dump:
        return _json_response({"error": "Not found"}, 404)
    return _json_response({"deleted": True})


async def handle_calendar(request: web.Request) -> web.Response:
    db: Database = request.app["db"]
    user_id = request["user_id"]
    try:
        year = int(request.query.get("year", date.today().year))
        month = int(request.query.get("month", date.today().month))
    except ValueError:
        year, month = date.today().year, date.today().month

    month_start = date(year, month, 1)
    data = db.get_calendar_month(user_id, month_start)

    event_days = set()
    month_start_dt = date(year, month, 1)
    month_end_dt = date(year + (1 if month == 12 else 0), (month % 12) + 1, 1)
    for e in data["events"]:
        if e.get("start_at"):
            s = e["start_at"].date() if isinstance(e["start_at"], datetime) else e["start_at"]
            end = s
            if e.get("end_at"):
                end = e["end_at"].date() if isinstance(e["end_at"], datetime) else e["end_at"]
            d = max(s, month_start_dt)
            while d <= end and d < month_end_dt:
                event_days.add(d.day)
                d += timedelta(days=1)
    for a in data["assignments"]:
        if a.get("due_at"):
            due = a["due_at"].date() if isinstance(a["due_at"], datetime) else a["due_at"]
            if month_start_dt <= due < month_end_dt:
                event_days.add(due.day)

    return _json_response({
        "year": year,
        "month": month,
        "assignments": [_serialize_assignment(a) for a in data["assignments"]],
        "events": [_serialize_event(e) for e in data["events"]],
        "event_days": sorted(event_days),
    })


async def serve_miniapp(request: web.Request) -> web.Response:
    index = MINIAPP_DIR / "index.html"
    if not index.exists():
        return web.Response(text="Mini app not found", status=404)
    return web.FileResponse(index)


def create_webapp(settings, db: Database) -> web.Application:
    app = web.Application(middlewares=[cors_middleware, auth_middleware])
    app["db"] = db
    app["bot_token"] = settings.telegram_bot_token
    app["settings"] = settings
    app["owner_telegram_user_id"] = settings.owner_telegram_user_id
    app["dev_mode"] = os.getenv("MINIAPP_DEV_MODE", "").lower() in ("1", "true", "yes")

    app.router.add_get("/", serve_miniapp)
    app.router.add_get("/miniapp", serve_miniapp)
    app.router.add_get("/miniapp/", serve_miniapp)

    app.router.add_get("/api/summary", handle_summary)
    app.router.add_get("/api/todos", handle_todos_list)
    app.router.add_post("/api/todos", handle_todos_create)
    app.router.add_patch("/api/todos/{id}", handle_todos_update)
    app.router.add_delete("/api/todos/{id}", handle_todos_delete)
    app.router.add_get("/api/events", handle_events_list)
    app.router.add_post("/api/events", handle_events_create)
    app.router.add_delete("/api/events/{id}", handle_events_delete)
    app.router.add_get("/api/assignments", handle_assignments_list)
    app.router.add_get("/api/journal", handle_journal_get)
    app.router.add_put("/api/journal", handle_journal_save)
    app.router.add_get("/api/dumps", handle_dumps_list)
    app.router.add_post("/api/dumps", handle_dumps_create)
    app.router.add_patch("/api/dumps/{id}", handle_dumps_update)
    app.router.add_delete("/api/dumps/{id}", handle_dumps_delete)
    app.router.add_get("/api/calendar", handle_calendar)

    return app


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    db = Database(settings)
    app = create_webapp(settings, db)
    web.run_app(app, host="0.0.0.0", port=settings.webapp_port)


if __name__ == "__main__":
    main()
