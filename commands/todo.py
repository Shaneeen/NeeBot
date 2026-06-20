from __future__ import annotations

from datetime import datetime, time, timedelta

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply
from .date_utils import format_human_date, parse_todo_date_args, week_bounds


def _todos_help_message() -> str:
    return (
        "[ todos_help_ ]\n\n"
        "Use this command to view your tasks.\n\n"
        "[ options_ ]\n"
        "↳ /todos — show pending tasks\n"
        "↳ /todos week — show this week's tasks\n"
        "↳ /todos today — show today's tasks\n\n"
        "[ next_ ]\n"
        "Try /todos or /todos week →"
    )


async def todo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tz = context.application.bot_data["settings"].tzinfo
    today = datetime.now(tz).date()
    due_date, text = parse_todo_date_args(context.args, today)
    if not text:
        await safe_reply(
            update,
            "[Tasks /todo]\nAdd a task:\n  /todo title\n  /todo date title\n\nDates: today · tomorrow · mon · next fri\n  /todo tomorrow Pick up parcel\n  /todo next wed Submit report",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    due_at = datetime.combine(due_date, time(9, 0), tzinfo=tz)
    todo = context.application.bot_data["db"].add_todo(profile["id"], text, due_at=due_at)
    await safe_reply(
        update,
        f"✅ Todo added — {format_human_date(due_date, today)}\n{todo['title']}",
    )


async def todos_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    tz = context.application.bot_data["settings"].tzinfo
    today = datetime.now(tz).date()
    lowered = [arg.lower() for arg in context.args]

    if not lowered:
        todos = context.application.bot_data["db"].list_pending_todos(profile["id"])
        today_todos = []
        for todo in todos:
            if todo["due_at"] and todo["due_at"].astimezone(tz).date() == today:
                today_todos.append(todo)
        if not today_todos:
            await safe_reply(
                update,
                "[ pending_tasks_ ]\n\n"
                "No pending tasks right now ᵕ̈\n\n"
                "[ next_ ]\n"
                "↳ /todo Task name — add a new task\n"
                "↳ /today — view your daily overview",
            )
            return
        lines = ["[ pending_tasks — today_ ]", ""]
        for index, todo in enumerate(today_todos, start=1):
            lines.append(f"↳ {index}. {todo['title']}")
        lines.append("")
        lines.extend(
            [
                "[ actions_ ]",
                "↳ /done 1 — mark task 1 as completed",
                "↳ /todo Task name — add another task",
            ]
        )
        await safe_reply(update, "\n".join(lines))
        return

    if lowered[:1] == ["week"] or lowered[:2] == ["this", "week"]:
        week_start, week_end = week_bounds(today)
        todos = context.application.bot_data["db"].list_todos_for_range(
            profile["id"],
            datetime.combine(week_start, time.min, tzinfo=tz),
            datetime.combine(week_end + timedelta(days=1), time.min, tzinfo=tz),
        )
        if not todos:
            await safe_reply(
                update,
                "[ pending_tasks — this_week_ ]\n\n"
                "No pending tasks this week ᵕ̈\n\n"
                "[ next_ ]\n"
                "↳ /todo Task name — add a new task\n"
                "↳ /today — view your daily overview",
            )
            return
        grouped: dict[datetime.date, list[dict]] = {}
        for todo in todos:
            if not todo["due_at"]:
                continue
            due_date = todo["due_at"].astimezone(tz).date()
            grouped.setdefault(due_date, []).append(todo)
        if not grouped:
            await safe_reply(
                update,
                "[ pending_tasks — this_week_ ]\n\n"
                "No pending tasks this week ᵕ̈\n\n"
                "[ next_ ]\n"
                "↳ /todo Task name — add a new task\n"
                "↳ /today — view your daily overview",
            )
            return
        lines = [
            "[ pending_tasks — this_week_ ]",
            f"{week_start.strftime('%a %d %b')} → {week_end.strftime('%a %d %b')}",
            "",
        ]
        for due_date in sorted(grouped):
            label = due_date.strftime("%A").lower()
            if due_date == today:
                lines.append(f"[ today — {label}_ ]")
            else:
                lines.append(f"[ {label}_ ]")
            for index, todo in enumerate(grouped[due_date], start=1):
                lines.append(f"↳ {index}. {todo['title']}")
            lines.append("")
        lines.extend(
            [
                "[ actions_ ]",
                "↳ /done 1 — mark task 1 as completed",
                "↳ /todo Task name — add another task",
            ]
        )
        await safe_reply(update, "\n".join(lines))
        return

    if lowered[:1] == ["today"]:
        todos = context.application.bot_data["db"].list_todos_for_range(
            profile["id"],
            datetime.combine(today, time.min, tzinfo=tz),
            datetime.combine(today + timedelta(days=1), time.min, tzinfo=tz),
        )
        if not todos:
            await safe_reply(update, "[ today_tasks_ ]\n\nNo tasks scheduled for today.")
            return
        lines = ["[ today_tasks_ ]", ""]
        for index, todo in enumerate(todos, start=1):
            lines.append(f"↳ {index}. {todo['title']}")
            lines.append("due: today")
            lines.append("")
        await safe_reply(update, "\n".join(lines))
        return

    await safe_reply(update, _todos_help_message())


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    todo_ref = " ".join(context.args).strip()
    if not todo_ref:
        await safe_reply(
            update,
            "[ done_ ]\n"
            "Mark a task as completed.\n\n"
            "[ format_ ]\n"
            "↳ /done task_number\n\n"
            "[ example_ ]\n"
            "↳ /done 2\n\n"
            "[ tip_ ]\n"
            "Task numbers are shown in /todos →",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    todo = context.application.bot_data["db"].mark_todo_done(profile["id"], todo_ref)
    if not todo:
        await safe_reply(update, "Todo not found. Check your list with /todos.")
        return
    await safe_reply(
        update,
        "[ task_completed_ ]\n"
        f"↳ {todo['title']}\n\n"
        "Removed from your pending tasks ᵕ̈",
    )
