from __future__ import annotations

from collections import Counter
import re

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


def _assignment_has_explicit_time(assignment: dict) -> bool:
    return bool(re.search(r"\b\d{2}:\d{2}\b", assignment.get("description") or ""))


def _format_assignment_due(assignment: dict, tz, *, show_dash_when_missing_time: bool = False) -> str:
    local_due = assignment["due_at"].astimezone(tz)
    if _assignment_has_explicit_time(assignment):
        return local_due.strftime("%d %b %Y, %H:%M")
    if show_dash_when_missing_time:
        return f"{local_due.strftime('%d %b %Y')} — -"
    return local_due.strftime("%d %b %Y")


async def assignment_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            update,
            "[Schedule /assignment]\nSave a deadline:\n  /assignment title\n  /assignment DD-MM title\n  /assignment DD Mon title\n  /assignment due DD-MM title\n\n  /assignment 19-06 Submit thesis\n  /assignment 19 Jun Submit thesis\n  /assignment due 19-06 Submit thesis",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    assignment = context.application.bot_data["db"].add_assignment(profile["id"], text)
    due_text = (
        _format_assignment_due(
            assignment,
            context.application.bot_data["settings"].tzinfo,
        )
        if assignment["due_at"]
        else "No due date"
    )
    await safe_reply(
        update,
        "[ assignment_saved_ ]\n"
        f"↳ {assignment['title']}\n"
        f"due: {due_text}\n\n"
        "[ next_ ]\n"
        "↳ /assignments — view active assignments\n"
        "↳ /calendar — view your month",
    )


async def assignments_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    assignments = context.application.bot_data["db"].list_active_assignments(profile["id"])
    if not assignments:
        await safe_reply(
            update,
            "[ active_assignments_ ]\n"
            "No active assignments right now ᵕ̈\n\n"
            "[ next_ ]\n"
            "↳ /assignment Title due YYYY-MM-DD — add an assignment\n"
            "↳ /calendar — view your monthly schedule",
        )
        return
    tz = context.application.bot_data["settings"].tzinfo
    dated: list[dict] = []
    unscheduled: list[dict] = []
    for assignment in assignments:
        if assignment["due_at"]:
            dated.append(assignment)
        else:
            unscheduled.append(assignment)

    date_counts = Counter(
        assignment["due_at"].astimezone(tz).date() for assignment in dated
    )
    has_repeated_dates = any(count >= 2 for count in date_counts.values())

    lines = ["[ active_assignments_ ]", ""]
    item_number = 1

    if dated:
        if has_repeated_dates:
            current_date = None
            for assignment in dated:
                due_at = assignment["due_at"].astimezone(tz)
                due_date = due_at.date()
                if due_date != current_date:
                    lines.append(f"[ {due_at.strftime('%d %b %Y').lower()}_ ]")
                    current_date = due_date
                if _assignment_has_explicit_time(assignment):
                    lines.append(f"↳ {item_number}. {assignment['title']} — {due_at.strftime('%H:%M')}")
                else:
                    lines.append(f"↳ {item_number}. {assignment['title']}")
                item_number += 1
            lines.append("")
        else:
            lines.append("[ due_ ]")
            for assignment in dated:
                lines.append(
                    f"↳ {item_number}. {assignment['title']} — {_format_assignment_due(assignment, tz, show_dash_when_missing_time=True)}"
                )
                item_number += 1
            lines.append("")

    if unscheduled:
        lines.append("[ unscheduled_ ]")
        for assignment in unscheduled:
            lines.append(f"↳ {item_number}. {assignment['title']}")
            item_number += 1
        lines.append("")

    lines.extend(
        [
            "[ actions_ ]",
            "↳ /assignment Title due DD-MM-YYYY — add assignment",
            "↳ /calendar — view monthly schedule",
        ]
    )
    await safe_reply(update, "\n".join(lines))
