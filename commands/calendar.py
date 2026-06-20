from __future__ import annotations

from datetime import datetime
import re

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


def _event_has_explicit_time(event: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", event.get("description") or ""))


def _format_event_when(event: dict, tz, *, show_dash_when_missing_time: bool = False) -> str:
    local_start = event["start_at"].astimezone(tz)
    if _event_has_explicit_time(event):
        return local_start.strftime("%d %b %Y, %H:%M")
    if show_dash_when_missing_time:
        return f"{local_start.strftime('%d %b %Y')} — -"
    return local_start.strftime("%d %b %Y")


def _assignment_has_explicit_time(assignment: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", assignment.get("description") or ""))


def _format_assignment_when(assignment: dict, tz, *, show_dash_when_missing_time: bool = False) -> str:
    local_due = assignment["due_at"].astimezone(tz)
    if _assignment_has_explicit_time(assignment):
        return local_due.strftime("%d %b %Y, %H:%M")
    if show_dash_when_missing_time:
        return f"{local_due.strftime('%d %b %Y')} — -"
    return local_due.strftime("%d %b %Y")


async def event_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            update,
            "[Schedule /event]\nSave an event:\n  /event DD-MM title\n  /event DD-MM-YYYY HH:MM title\n  /event DD Mon HH:MM title\n\n  /event 19-06 Fireworks\n  /event 19-06 20:00 Fireworks night\n  /event 19 Jun 20:00 Fireworks night\n\n→ Year defaults to current. Time defaults to 09:00.",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    try:
        event = context.application.bot_data["db"].add_event(profile["id"], text)
    except ValueError:
        await safe_reply(
            update,
            "[Schedule /event]\nCouldn't read that. Expected:\n  /event DD-MM title\n  /event 19-06 20:00 Fireworks night\n  /event 19 Jun 20:00 Fireworks night",
        )
        return
    when = _format_event_when(
        event,
        context.application.bot_data["settings"].tzinfo,
    )
    await safe_reply(update, f"📅 Event saved\n{event['title']} — {when}")


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    events = context.application.bot_data["db"].list_upcoming_events(profile["id"])
    if not events:
        await safe_reply(update, "No upcoming events.")
        return
    tz = context.application.bot_data["settings"].tzinfo
    lines = ["[Schedule /events]", "Upcoming events:"]
    for index, event in enumerate(events, start=1):
        when = _format_event_when(event, tz, show_dash_when_missing_time=True)
        lines.append(f"{index}. {when} — {event['title']}")
    await safe_reply(update, "\n".join(lines))


async def calendar_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tz = context.application.bot_data["settings"].tzinfo
    today = datetime.now(tz).date()
    month_text = " ".join(context.args).strip()
    if not month_text:
        month_start = today.replace(day=1)
    else:
        try:
            month_start = datetime.strptime(month_text, "%Y-%m").date().replace(day=1)
        except ValueError:
            await safe_reply(
                update,
                "[Schedule /calendar]\nView a month:\n  /calendar          (current month)\n  /calendar YYYY-MM\n\n  /calendar 2025-08",
            )
            return

    profile = await get_authorized_profile(update, context)
    if not profile:
        return

    month_data = context.application.bot_data["db"].get_calendar_month(profile["id"], month_start)
    lines = [f"[Schedule /calendar]", f"Calendar — {month_start.strftime('%B %Y')}", ""]

    lines.append("Assignments:")
    if month_data["assignments"]:
        for index, assignment in enumerate(month_data["assignments"], start=1):
            due_text = _format_assignment_when(assignment, tz, show_dash_when_missing_time=True)
            lines.append(f"{index}. {due_text} — {assignment['title']}")
    else:
        lines.append("No assignments due this month.")
    lines.append("")

    lines.append("Events:")
    if month_data["events"]:
        for index, event in enumerate(month_data["events"], start=1):
            when = _format_event_when(event, tz, show_dash_when_missing_time=True)
            lines.append(f"{index}. {when} — {event['title']}")
    else:
        lines.append("No events this month.")

    await safe_reply(update, "\n".join(lines))
