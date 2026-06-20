from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from .common import get_authorized_profile, safe_reply


async def pending_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner = await get_authorized_profile(update, context, owner_only=True, require_approved=False)
    if not owner:
        return
    pending = context.application.bot_data["db"].list_pending_profiles()
    if not pending:
        await safe_reply(update, "No pending access requests.")
        return
    lines = ["[Admin /pending_users]", "Pending access requests:"]
    for profile in pending:
        name = profile["display_name"] or "Unknown"
        lines.append(f"{profile['telegram_user_id']} — {name}")
    await safe_reply(update, "\n".join(lines))


async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner = await get_authorized_profile(update, context, owner_only=True, require_approved=False)
    if not owner:
        return
    if not context.args:
        await safe_reply(update, "[Admin /approve]\nUsage: /approve <telegram_user_id>")
        return
    try:
        target_telegram_user_id = int(context.args[0])
    except ValueError:
        await safe_reply(update, "Telegram user id must be numeric.")
        return

    approved = context.application.bot_data["db"].approve_profile(
        owner["telegram_user_id"], target_telegram_user_id
    )
    if not approved:
        await safe_reply(update, "User not found. They need to send /start first.")
        return
    await safe_reply(
        update,
        f"✅ Approved {approved['display_name'] or 'user'} ({approved['telegram_user_id']}).",
    )
