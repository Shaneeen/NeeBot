from __future__ import annotations

from typing import Any

from telegram import Update
from telegram.ext import ContextTypes


def display_name_from_user(user: Any) -> str:
    return user.full_name or user.username or "Telegram User"


async def get_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> dict[str, Any]:
    user = update.effective_user
    db = context.application.bot_data["db"]
    profile = db.get_profile_by_telegram_id(user.id)
    if profile:
        return profile
    return db.ensure_profile(user.id, display_name_from_user(user))


async def get_authorized_profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    require_approved: bool = True,
    owner_only: bool = False,
) -> dict[str, Any] | None:
    profile = await get_profile(update, context)

    if owner_only and not profile["is_owner"]:
        await safe_reply(update, "[Admin]\nOnly the bot owner can use this command.")
        return None

    if require_approved and not profile["is_approved"]:
        await safe_reply(
            update,
            "Your access request is still pending.\n\n→ Once approved, send /start again.",
        )
        return None

    return profile


async def safe_reply(update: Update, text: str) -> None:
    if update.message:
        await update.message.reply_text(text)
