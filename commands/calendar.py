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
    local_end = event["end_at"].astimezone(tz) if event.get("end_at") else None
    has_time = _event_has_explicit_time(event)

    if local_end and local_end != local_start:
        if has_time:
            if local_start.date() == local_end.date():
                return f"{local_start.strftime('%d %b %Y, %H:%M')} to {local_end.strftime('%H:%M')}"
            return f"{local_start.strftime('%d %b %Y, %H:%M')} to {local_end.strftime('%d %b %Y, %H:%M')}"
        if local_start.date() == local_end.date():
            return local_start.strftime("%d %b %Y")
        return f"{local_start.strftime('%d %b %Y')} to {local_end.strftime('%d %b %Y')}"

    if has_time:
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
            "[ event_ ]\n\nSave an event with a date, time, or date range.\n\n[ formats_ ]\n↳ /event DD-MM Title\n↳ /event DD-MM-YYYY HH:MM Title\n↳ /event DD Mon HH:MM Title\n↳ /event DD-MM to DD-MM Title\n↳ /event DD-MM-YYYY HH:MM to DD-MM-YYYY HH:MM Title\n\n[ examples_ ]\n↳ /event 19-06 Fireworks\n↳ /event 19-06 20:00 Fireworks night\n↳ /event 19 Jun 20:00 Fireworks night\n↳ /event 19-06 to 22-06 Bali trip\n↳ /event 19-06-2026 09:00 to 22-06-2026 18:00 Offsite\n\n[ note_ ]\n↳ Use to for events that span multiple dates.\n↳ The year defaults to the current year.\n↳ The time defaults to 09:00.",
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
            "[Schedule /event]\nCouldn't read that. Expected:\n  /event DD-MM title\n  /event 19-06 20:00 Fireworks night\n  /event 19 Jun 20:00 Fireworks night\n  /event 19-06 to 22-06 Bali trip\n  /event 19-06-2026 09:00 to 22-06-2026 18:00 Offsite",
        )
        return
    when = _format_event_when(
        event,
        context.application.bot_data["settings"].tzinfo,
    )
    await safe_reply(
        update,
        f"[ event_saved_ ]\n\n↳ {event['title']}\n↳ {when}\n\nSaved to your events →",
    )


async def eventdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    event_ref = " ".join(context.args).strip()
    if not event_ref:
        await safe_reply(
            update,
            "[ event_delete_ ]\n\nUse this command to delete an event.\n\n[ format_ ]\n↳ /eventdelete event_number\n\n[ example_ ]\n↳ /eventdelete 1\n\n[ note_ ]\n↳ Use /events to view your event numbers.",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    event = context.application.bot_data["db"].delete_event(profile["id"], event_ref)
    if not event:
        await safe_reply(update, "Event not found. Use /events to view your upcoming event numbers.")
        return
    when = _format_event_when(
        event,
        context.application.bot_data["settings"].tzinfo,
    )
    await safe_reply(
        update,
        f"[ event_deleted_ ]\n\n↳ {event['title']}\n↳ {when}\n\nRemoved from your events →",
    )


async def events_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    events = context.application.bot_data["db"].list_upcoming_events(profile["id"])
    if not events:
        await safe_reply(
            update,
            "[ events_ ]\n\nNo upcoming events.\n\n[ next_ ]\n↳ /event 19-06 Fireworks",
        )
        return
    tz = context.application.bot_data["settings"].tzinfo
    lines = ["[ events_ ]", "", "Your upcoming events:", ""]
    for index, event in enumerate(events, start=1):
        when = _format_event_when(event, tz)
        lines.append(f"↳ {index}. {event['title']}")
        lines.append(f"   {when}")
        lines.append("")
    lines.extend(["[ actions_ ]", "↳ /eventdelete 1 — delete event 1"])
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
