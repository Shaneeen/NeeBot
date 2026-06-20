from __future__ import annotations

from datetime import datetime
import re

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply
from .date_utils import parse_optional_date_args


def _assignment_has_explicit_time(assignment: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", assignment.get("description") or ""))


def _event_has_explicit_time(event: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", event.get("description") or ""))


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    tzinfo = context.application.bot_data["settings"].tzinfo
    current_date = datetime.now(tzinfo).date()
    target_date, _ = parse_optional_date_args(context.args, current_date)
    summary = context.application.bot_data["db"].get_summary_for_date(profile["id"], target_date)
    tz = context.application.bot_data["settings"].tzinfo

    lines = ["[ today_overview_ ]", summary["date"].strftime("%d %b %Y"), ""]

    lines.append("[ todos_ ]")
    if summary["todos"]:
        for index, todo in enumerate(summary["todos"], start=1):
            lines.append(f"↳ {index}. {todo['title']}")
    else:
        lines.append("No pending todos.")
    lines.append("")

    dated_assignments = [a for a in summary["assignments"] if a["due_at"]]
    unscheduled_assignments = [a for a in summary["assignments"] if not a["due_at"]]

    lines.append("[ assignments_ ]")
    if dated_assignments:
        for index, assignment in enumerate(dated_assignments, start=1):
            due_at = assignment["due_at"].astimezone(tz)
            due_text = due_at.strftime("%d %b %Y")
            if _assignment_has_explicit_time(assignment):
                due_text = f"{due_text}, {due_at.strftime('%H:%M')}"
            lines.append(f"↳ {index}. {assignment['title']} — {due_text}")
    else:
        lines.append("No active assignments.")
    lines.append("")

    if unscheduled_assignments:
        lines.append("[ unscheduled_assignments_ ]")
        for offset, assignment in enumerate(unscheduled_assignments, start=len(dated_assignments) + 1):
            lines.append(f"↳ {offset}. {assignment['title']}")
        lines.append("")

    lines.append("[ events_ ]")
    if summary["events"]:
        for index, event in enumerate(summary["events"], start=1):
            start_at = event["start_at"].astimezone(tz)
            if _event_has_explicit_time(event):
                event_text = f"{start_at.strftime('%d %b %Y, %H:%M')} — {event['title']}"
            else:
                event_text = f"{start_at.strftime('%d %b %Y')} — {event['title']}"
            lines.append(f"↳ {index}. {event_text}")
    else:
        lines.append("No events today.")
    lines.append("")

    lines.append("[ diary_ ]")
    if summary["diary_entry"]:
        entry = summary["diary_entry"]
        if entry["mood_labels"]:
            lines.append(f"mood: {' '.join(entry['mood_labels'])}")
        if entry["content"]:
            lines.append(entry["content"])
        else:
            lines.append("No journal entry yet.")
    else:
        lines.append("No diary entry yet.")
    await safe_reply(update, "\n".join(lines))
