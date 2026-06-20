from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


def _dump_help_message() -> str:
    return (
        "[ brain_dump_ ]\n\n"
        "Save messy thoughts under a clear header.\n\n"
        "[ commands_ ]\n"
        "↳ /dump — create a new brain dump\n"
        "↳ /dumps — view all dump headers\n"
        "↳ /dumpview — view one full dump\n"
        "↳ /dumpedit — update a dump\n"
        "↳ /dumpdelete — delete a dump\n\n"
        "[ format_ ]\n"
        "↳ /dump Header | your thoughts\n\n"
        "[ example_ ]\n"
        "↳ /dump Cubed Project | auth, merchant dashboard, outlet setup, cube assignment\n\n"
        "[ note_ ]\n"
        "Use /dumps to view your saved dump headers →"
    )


def _dump_usage_message() -> str:
    return (
        "[ dump_help_ ]\n\n"
        "Use this format to save a brain dump:\n\n"
        "↳ /dump Header | your thoughts\n\n"
        "[ example_ ]\n"
        "↳ /dump Telegram Bot Ideas | add reminders, better journal view, weekly review"
    )


def _parse_dump_create(raw_text: str) -> tuple[str, str] | None:
    if "|" not in raw_text:
        return None
    header, content = raw_text.split("|", 1)
    header = header.strip()
    content = content.strip()
    if not header or not content:
        return None
    return header, content


def _parse_dump_edit(raw_text: str) -> tuple[str, str] | None:
    if "|" not in raw_text:
        return None
    dump_ref, content = raw_text.split("|", 1)
    dump_ref = dump_ref.strip()
    content = content.strip()
    if not dump_ref or not content:
        return None
    return dump_ref, content


async def dump_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_text = " ".join(context.args).strip()
    if not raw_text:
        await safe_reply(update, _dump_help_message())
        return
    parsed = _parse_dump_create(raw_text)
    if not parsed:
        await safe_reply(update, _dump_usage_message())
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    header, content = parsed
    dump = context.application.bot_data["db"].add_brain_dump(profile["id"], header, content)
    await safe_reply(
        update,
        "[ dump_saved_ ]\n\n"
        f"↳ {dump['header']}\n\n"
        "Saved to your brain dumps →",
    )


async def dumps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    dumps = context.application.bot_data["db"].list_brain_dumps(profile["id"])
    if not dumps:
        await safe_reply(
            update,
            "[ brain_dumps_ ]\n\n"
            "No brain dumps saved yet.\n\n"
            "[ next_ ]\n"
            "↳ /dump Header | your thoughts",
        )
        return
    lines = ["[ brain_dumps_ ]", ""]
    for index, dump in enumerate(dumps, start=1):
        lines.append(f"↳ {index}. {dump['header']}")
    lines.extend(
        [
            "",
            "[ actions_ ]",
            "↳ /dumpview 1 — open dump 1",
            "↳ /dump Header | text — add a new dump",
        ]
    )
    await safe_reply(update, "\n".join(lines))


async def dumpview_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dump_ref = " ".join(context.args).strip()
    if not dump_ref:
        await safe_reply(
            update,
            "[ dump_help_ ]\n\n"
            "Use this command to open one brain dump.\n\n"
            "↳ /dumpview dump_number\n\n"
            "[ example_ ]\n"
            "↳ /dumpview 1",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    dump = context.application.bot_data["db"].get_brain_dump(profile["id"], dump_ref)
    if not dump:
        await safe_reply(update, "Brain dump not found. Use /dumps to view your saved dump headers.")
        return
    await safe_reply(
        update,
        "[ brain_dump_ ]\n\n"
        f"{dump['header']}\n\n"
        f"{dump['content']}\n\n"
        "[ actions_ ]\n"
        f"↳ /dumpedit {dump_ref} | new text — update this dump\n"
        f"↳ /dumpdelete {dump_ref} — delete this dump",
    )


async def dumpedit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw_text = " ".join(context.args).strip()
    parsed = _parse_dump_edit(raw_text)
    if not parsed:
        await safe_reply(
            update,
            "[ dump_help_ ]\n\n"
            "Use this format to update a brain dump:\n\n"
            "↳ /dumpedit dump_number | new text\n\n"
            "[ example_ ]\n"
            "↳ /dumpedit 1 | auth, merchant dashboard, outlet setup",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    dump_ref, content = parsed
    dump = context.application.bot_data["db"].update_brain_dump(profile["id"], dump_ref, content)
    if not dump:
        await safe_reply(update, "Brain dump not found. Use /dumps to view your saved dump headers.")
        return
    await safe_reply(
        update,
        "[ dump_updated_ ]\n\n"
        f"↳ {dump['header']}\n\n"
        "Your brain dump has been updated →",
    )


async def dumpdelete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dump_ref = " ".join(context.args).strip()
    if not dump_ref:
        await safe_reply(
            update,
            "[ dump_help_ ]\n\n"
            "Use this command to delete a brain dump:\n\n"
            "↳ /dumpdelete dump_number\n\n"
            "[ example_ ]\n"
            "↳ /dumpdelete 1",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    dump = context.application.bot_data["db"].delete_brain_dump(profile["id"], dump_ref)
    if not dump:
        await safe_reply(update, "Brain dump not found. Use /dumps to view your saved dump headers.")
        return
    await safe_reply(
        update,
        "[ dump_deleted_ ]\n\n"
        f"↳ {dump['header']}\n\n"
        "Removed from your brain dumps →",
    )
