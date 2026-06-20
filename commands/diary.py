from __future__ import annotations

from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply
from .date_utils import format_human_date, parse_optional_date_args


def _entry_label(entry_date, current_date) -> str:
    return format_human_date(entry_date, current_date)


async def journal_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today = context.application.bot_data["db"].settings.tzinfo
    current_date = datetime.now(today).date()
    entry_date, text = parse_optional_date_args(context.args, current_date)
    if not text:
        await safe_reply(
            update,
            "[ journal_ ]\n"
            "Write or update a journal entry.\n\n"
            "[ format_ ]\n"
            "↳ /journal your entry\n"
            "↳ /journal yesterday your entry\n"
            "↳ /journal YYYY-MM-DD your entry\n\n"
            "[ examples_ ]\n"
            "↳ /journal Today was productive but tiring.\n"
            "↳ /journal yesterday Had a cozy rest day.\n"
            "↳ /journal 2026-06-25 Felt focused today.\n\n"
            "[ note_ ]\n"
            "Sending /journal again for the same date will update that entry →",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    context.application.bot_data["db"].upsert_diary_entry(profile["id"], text, entry_date)
    await safe_reply(
        update,
        "[ journal_saved_ ]\n"
        f"entry: {_entry_label(entry_date, current_date)}\n"
        "Your journal has been saved ᵕ̈\n\n"
        "[ next_ ]\n"
        "↳ /diary — view today's entry\n"
        "↳ /mood happy tired — add your mood",
    )


async def diary_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    current_date = datetime.now(
        context.application.bot_data["db"].settings.tzinfo
    ).date()
    entry_date, _ = parse_optional_date_args(context.args, current_date)
    entry = context.application.bot_data["db"].get_diary_entry(profile["id"], entry_date)
    if not entry:
        await safe_reply(
            update,
            "[ diary — "
            f"{_entry_label(entry_date, current_date)}_ ]\n\n"
            "No diary entry yet ᵕ̈\n\n"
            "[ next_ ]\n"
            "↳ /journal Today was... — write your journal\n"
            "↳ /mood happy tired — add your mood",
        )
        return
    lines = [f"[ diary — {_entry_label(entry_date, current_date)}_ ]", ""]
    if entry["mood_labels"]:
        lines.extend(
            [
                "[ mood_ ]",
                " ".join(entry["mood_labels"]),
                "",
            ]
        )
    lines.append("[ journal_ ]")
    if entry["content"]:
        lines.append(entry["content"])
        lines.extend(
            [
                "",
                "[ actions_ ]",
                "↳ /journal new text — update today's entry",
                "↳ /mood happy tired — update today's mood",
            ]
        )
    else:
        lines.extend(
            [
                "No journal entry yet.",
                "",
                "[ next_ ]",
                "↳ /journal Today was... — add one",
            ]
        )
    await safe_reply(update, "\n".join(lines))
