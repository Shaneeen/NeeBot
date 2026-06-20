from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


async def habit_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(
            update,
            "Let's create a habit.\n\nWhat to send:\n/habit <name> [target] [unit]\n\nExample:\n/habit Sleep 7 hours",
        )
        return
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    habit = context.application.bot_data["db"].add_habit(profile["id"], text)
    suffix = ""
    if habit["target_value"] is not None:
        suffix = f" ({habit['target_value']} {habit['unit'] or ''})".rstrip()
    await safe_reply(update, f"Habit saved:\n{habit['name']}{suffix}")


async def habits_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    habits = context.application.bot_data["db"].list_habits(profile["id"])
    if not habits:
        await safe_reply(update, "No active habits.")
        return
    lines = ["Active habits:"]
    for index, habit in enumerate(habits, start=1):
        target = ""
        if habit["target_value"] is not None:
            target = f" — target {habit['target_value']} {habit['unit'] or ''}".rstrip()
        lines.append(f"{index}. {habit['name']}{target}")
    await safe_reply(update, "\n".join(lines))


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await safe_reply(
            update,
            "Let's track a habit.\n\nWhat to send:\n/track <habit name> <value>\n\nExample:\n/track Sleep 6.5",
        )
        return
    try:
        value = float(context.args[-1])
    except ValueError:
        await safe_reply(
            update,
            "Habit value must be a number.\n\nExample:\n/track Sleep 6.5",
        )
        return
    habit_name = " ".join(context.args[:-1]).strip()
    profile = await get_authorized_profile(update, context)
    if not profile:
        return
    tracked = context.application.bot_data["db"].track_habit(profile["id"], habit_name, value)
    if not tracked:
        await safe_reply(update, f"Habit not found: {habit_name}")
        return
    unit = tracked["habit"]["unit"] or ""
    await safe_reply(update, f"Tracked {tracked['habit']['name']}: {tracked['log']['value']} {unit}".rstrip())
