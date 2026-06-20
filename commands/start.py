from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_profile, safe_reply


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_profile(update, context)
    if profile["is_owner"]:
        await safe_reply(
            update,
            (
                "Welcome back ᵕ̈\n\n"
                "[ options_ ]\n"
                "↳ /today  — daily summary\n"
                "↳ /help   — commands list\n"
                "↳ /owner  — admin panel\n\n"
                "Pick one to get started →"
            ),
        )
        return

    if not profile["is_approved"]:
        await safe_reply(
            update,
            (
                "This bot is private.\n"
                "Your access request has been sent.\n\n"
                f"[ your_id ]\n{profile['telegram_user_id']}\n\n"
                "↳ Keep this ID handy if you need to share it.\n"
                "↳ Once approved, send /start again."
            ),
        )
        return

    await safe_reply(
        update,
        (
            "Welcome back ᵕ̈\n\n"
            "[ options_ ]\n"
            "↳ /today  — daily summary\n"
            "↳ /help   — commands list\n\n"
            "Pick one to get started →"
        ),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_profile(update, context)
    lines = [
        "[ help_menu_ ]",
        "Here are the commands you can use:",
        "",
        "[ tasks_ ]",
        "↳ /todo — add a task",
        "↳ /todos — view tasks · week · today",
        "↳ /done — complete a task",
        "",
        "[ brain_dump_ ]",
        "↳ /dump — create a brain dump",
        "↳ /dumps — view dump headers",
        "↳ /dumpview — open a dump",
        "↳ /dumpedit — update a dump",
        "↳ /dumpdelete — delete a dump",
        "",
        "[ schedule_ ]",
        "↳ /assignment — add a due item",
        "↳ /event — add an event",
        "↳ /calendar — view the month",
        "",
        "[ journal_ ]",
        "↳ /journal — write today's entry",
        "↳ /mood — save today's moods",
        "↳ /diary — read today's entry",
        "",
        "[ review_ ]",
        "↳ /today — open your daily overview",
    ]
    if profile["is_owner"]:
        lines.extend(
            [
                "",
                "[ owner_ ]",
                "↳ /owner — owner menu",
            ]
        )
    lines.extend(
        [
            "",
            "[ examples_ ]",
            "↳ /todo Finish proposal draft",
            "↳ /assignment Fintech report due 2026-07-01",
            "↳ /event 2026-06-25 09:00 DPTM meeting",
            "",
            "[ tip_ ]",
            "Not sure what to type? Send the command by itself →",
        ]
    )
    await safe_reply(
        update,
        "\n".join(lines),
    )


async def owner_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    profile = await get_profile(update, context)
    if not profile["is_owner"]:
        await safe_reply(update, "[Admin]\nThis menu is only available to the owner.")
        return
    await safe_reply(
        update,
        "\n".join(
            [
                "[Admin]",
                "/pending_users — review access requests",
                "/approve <telegram_user_id> — approve a user",
            ]
        ),
    )
